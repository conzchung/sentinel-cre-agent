"""Child-process entrypoint for the data-analysis sandbox.

Run as ``python -m sandbox_runner``. Reads a JSON payload from stdin, rebuilds
the injected DataFrames, executes the agent-written code in a restricted
namespace, and writes a typed JSON envelope to stdout. This module runs in an
isolated child process — never import it into the agent process.
"""

from __future__ import annotations

# Heavy libs imported at module load — BEFORE _apply_limits() clamps memory.
# RLIMIT_AS counts the import's virtual allocation, so clamping first would
# break the import (see Global Constraints / import order).
import pandas as pd
import numpy as np

import builtins as _builtins
import contextlib
import io
import json
import sys

# Result serialized larger than this (bytes) is rejected inside the child so the
# giant object never crosses the pipe.
MAX_RESULT_BYTES = 1_000_000

# Names exposed to user code. Excludes open, __import__, eval, exec, compile,
# input, getattr, setattr, globals, locals, vars (see Global Constraints).
_ALLOWED_BUILTINS = (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "int", "isinstance", "len", "list", "map",
    "max", "min", "print", "range", "reversed", "round", "set", "sorted",
    "str", "sum", "tuple", "zip",
)


def _safe_builtins() -> dict:
    return {name: getattr(_builtins, name) for name in _ALLOWED_BUILTINS}


def _blocked(*args, **kwargs):
    raise RuntimeError("file and network access are disabled in the analysis sandbox")


def _harden_runtime() -> None:
    """Neuter pandas/numpy/socket I/O entry points so sandboxed code cannot read
    local files (e.g. .env) or reach the network. Defense-in-depth, not a hard
    boundary — a true boundary needs an OS sandbox (see the design spec's upgrade
    path). Pure in-memory analysis on the injected ``datasets`` is unaffected.
    """
    # Network: block socket creation (covers pandas-URL reads, urllib, requests).
    try:
        import socket
        socket.socket = _blocked
        socket.create_connection = _blocked
    except Exception:  # noqa: BLE001 — best-effort hardening, never fatal
        pass

    # pandas readers: pd.read_csv / read_json / read_excel / read_pickle / ... all
    # do their own C-level file/URL I/O, bypassing the stripped ``open`` builtin.
    try:
        for name in [n for n in dir(pd) if n.startswith("read_")]:
            setattr(pd, name, _blocked)
    except Exception:  # noqa: BLE001
        pass

    # numpy readers.
    try:
        for name in ("load", "fromfile", "genfromtxt", "loadtxt"):
            if hasattr(np, name):
                setattr(np, name, _blocked)
    except Exception:  # noqa: BLE001
        pass


def _apply_limits(limits: dict) -> None:
    """Apply POSIX resource limits. No-op where ``resource`` is unavailable.

    Called AFTER pandas/numpy are imported (module load) so RLIMIT_AS governs
    the user computation, not the library load.
    """
    try:
        import resource
    except ImportError:
        return

    cpu_s = int(limits.get("cpu_s", 10))
    mem_bytes = int(limits.get("mem_mb", 2048)) * 1024 * 1024

    for name, soft in (
        ("RLIMIT_CPU", cpu_s),
        ("RLIMIT_AS", mem_bytes),
        ("RLIMIT_FSIZE", 0),  # no file writes (defense-in-depth; open is blocked)
    ):
        if hasattr(resource, name):
            try:
                resource.setrlimit(getattr(resource, name), (soft, soft))
            except (ValueError, OSError):
                pass  # cannot tighten below an existing hard limit; best-effort

    # Belt-and-braces wall clock (the parent also enforces a timeout+kill).
    try:
        import signal

        def _on_alarm(signum, frame):
            raise TimeoutError("execution exceeded wall-clock limit")

        signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(int(limits.get("wall_s", 10)))
    except (ImportError, ValueError, OSError):
        pass


def _cancel_alarm() -> None:
    try:
        import signal

        signal.alarm(0)
    except (ImportError, ValueError, OSError):
        pass


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _rebuild_datasets(data: dict) -> dict:
    out = {}
    for handle, split in data.items():
        out[handle] = pd.DataFrame(
            data=split["data"],
            columns=split["columns"],
            index=split.get("index"),
        )
    return out


def _classify(result):
    """Return (kind, json-serializable payload, n_rows)."""
    if result is None:
        return "none", None, None
    if isinstance(result, pd.DataFrame):
        return "dataframe", result.to_dict(orient="split"), len(result)
    if isinstance(result, pd.Series):
        frame = result.reset_index()
        return "series", frame.to_dict(orient="split"), len(result)
    if isinstance(result, bool):
        return "scalar", result, None
    if isinstance(result, (int, float, str)):
        return "scalar", result, None
    if isinstance(result, dict):
        return "dict", {str(k): v for k, v in result.items()}, None
    return "scalar", str(result), None


def _emit(envelope: dict) -> None:
    sys.stdout.write(json.dumps(envelope, default=_json_default))
    sys.stdout.flush()


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        _emit({"ok": False, "error": f"bad payload: {exc}"})
        return

    code = payload.get("code", "")
    data = payload.get("data", {})
    limits = payload.get("limits", {})

    try:
        datasets = _rebuild_datasets(data)
    except Exception as exc:  # noqa: BLE001
        _emit({"ok": False, "error": f"could not load datasets: {exc}"})
        return

    _apply_limits(limits)
    _harden_runtime()

    namespace = {
        "__builtins__": _safe_builtins(),
        "pd": pd,
        "np": np,
        "datasets": datasets,
    }
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, namespace)  # noqa: S102 — sandboxed; see module docstring
    except TimeoutError:
        _emit({"ok": False, "error": "Analysis timed out."})
        return
    except MemoryError:
        _emit({"ok": False, "error": "Analysis exceeded the memory limit."})
        return
    except BaseException as exc:  # noqa: BLE001 — report any failure cleanly
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return

    _cancel_alarm()
    kind, payload_result, n_rows = _classify(namespace.get("result"))
    envelope = {
        "ok": True,
        "kind": kind,
        "result": payload_result,
        "stdout": buf.getvalue(),
        "n_rows": n_rows,
    }
    try:
        serialized = json.dumps(envelope, default=_json_default)
    except (TypeError, ValueError) as exc:
        _emit({"ok": False, "error": f"result not serializable: {exc}"})
        return

    if len(serialized.encode("utf-8")) > MAX_RESULT_BYTES:
        _emit({"ok": False, "error": "result too large; aggregate further"})
        return

    sys.stdout.write(serialized)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
