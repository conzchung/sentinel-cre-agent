"""Parent-side driver for the data-analysis sandbox.

``run()`` spawns the ``sandbox_runner`` child with a minimal environment, pipes
the code and DataFrames in, and parses the typed result envelope back out. Pure
module — no LangChain imports. Never raises; all failures return an error dict.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

# agent/ directory — added to the child's PYTHONPATH so ``-m sandbox_runner``
# resolves regardless of the service's working dir or PATH.
_AGENT_DIR = str(Path(__file__).resolve().parent)

# The child's ENTIRE environment. A fixed allowlist, never os.environ, so the
# .env secrets (Azure/Cosmos/Tavily/Blob/Jina/Qdrant) cannot reach sandboxed
# code. The single-threaded BLAS vars keep numpy's *virtual* memory footprint
# small and predictable so RLIMIT_AS is reliable on Linux (multithreaded BLAS
# reserves huge per-thread virtual arenas that can defeat the cap).
_CHILD_ENV = {
    "PYTHONPATH": _AGENT_DIR,
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}

MAX_DISPLAY_ROWS = 50


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


def _err(message: str) -> Dict[str, Any]:
    return {
        "ok": False, "kind": "error", "table": None, "scalar": None,
        "stdout": "", "error": message, "truncated": False, "n_rows": None,
    }


def _normalize(envelope: dict) -> Dict[str, Any]:
    kind = envelope.get("kind", "none")
    out: Dict[str, Any] = {
        "ok": True, "kind": kind, "table": None, "scalar": None,
        "stdout": envelope.get("stdout", "") or "", "error": None,
        "truncated": False, "n_rows": envelope.get("n_rows"),
    }
    if kind in ("dataframe", "series"):
        split = envelope.get("result") or {"columns": [], "data": []}
        df = pd.DataFrame(data=split.get("data", []), columns=split.get("columns", []))
        if len(df) > MAX_DISPLAY_ROWS:
            df = df.head(MAX_DISPLAY_ROWS)
            out["truncated"] = True
        out["table"] = df.to_markdown(index=False)
    elif kind in ("dict", "scalar"):
        out["scalar"] = envelope.get("result")
    return out


def run(
    code: str,
    dataframes: Dict[str, pd.DataFrame],
    *,
    wall_s: int = 10,
    cpu_s: int = 10,
    mem_mb: int = 2048,
) -> Dict[str, Any]:
    data = {handle: df.to_dict(orient="split") for handle, df in dataframes.items()}
    payload = json.dumps(
        {"code": code, "data": data,
         "limits": {"wall_s": wall_s, "cpu_s": cpu_s, "mem_mb": mem_mb}},
        default=_json_default,
    )

    workdir = tempfile.mkdtemp(prefix="sentinel_analysis_")
    try:
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "sandbox_runner"],
                env=_CHILD_ENV,
                cwd=workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            return _err(f"could not start sandbox: {exc}")

        try:
            out, err = proc.communicate(payload, timeout=wall_s + 3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return _err(f"Analysis timed out after {wall_s}s.")

        if proc.returncode != 0:
            detail = (err or "").strip()[:300] or f"exit code {proc.returncode}"
            return _err(detail)

        try:
            envelope = json.loads(out)
        except json.JSONDecodeError:
            detail = (err or out or "").strip()[:300]
            return _err(f"sandbox returned no parseable result: {detail}")

        if not envelope.get("ok"):
            return _err(envelope.get("error", "unknown sandbox error"))
        return _normalize(envelope)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


_MEMORY_CAP_ENFORCED: bool | None = None


def memory_cap_enforced() -> bool:
    """True if RLIMIT_AS can be tightened to a finite value on this platform.

    Linux: True. macOS: False (setrlimit(RLIMIT_AS, finite) raises even when the
    hard limit is unlimited). Probed once in a child process so the parent's own
    address-space limit is never altered. Result cached.
    """
    global _MEMORY_CAP_ENFORCED
    if _MEMORY_CAP_ENFORCED is not None:
        return _MEMORY_CAP_ENFORCED
    probe = (
        "import resource, sys\n"
        "try:\n"
        "    cap = 512 * 1024 * 1024\n"
        "    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))\n"
        "    sys.stdout.write('yes')\n"
        "except Exception:\n"
        "    sys.stdout.write('no')\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, timeout=10,
        )
        _MEMORY_CAP_ENFORCED = result.stdout.strip() == "yes"
    except Exception:  # noqa: BLE001 — if the probe itself fails, assume not enforced
        _MEMORY_CAP_ENFORCED = False
    return _MEMORY_CAP_ENFORCED
