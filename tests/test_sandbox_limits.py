import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pytest

import pandas as pd

import code_sandbox

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX resource limits only")


def test_memory_cap_enforced_returns_bool():
    # The platform probe must exist and return a bool (True on Linux, False on
    # macOS). This is the cross-platform deliverable of this task.
    assert isinstance(code_sandbox.memory_cap_enforced(), bool)


@posix_only
def test_cpu_bound_loop_is_killed_by_cpu_limit_not_wall_clock():
    # RLIMIT_CPU fires SIGXCPU after ~1s of CPU and kills the child on its own.
    # wall_s is set high (parent timeout = wall_s + 3 = 33s) so that finishing
    # FAST proves the CPU limit — not the parent's wall-clock fallback — did the
    # work. Against the no-op stub the loop runs until the 33s parent timeout.
    start = time.time()
    out = code_sandbox.run("\nwhile True:\n    x = 1 * 1\n", {}, wall_s=30, cpu_s=1)
    elapsed = time.time() - start
    assert out["ok"] is False
    assert elapsed < 10  # CPU-killed in ~1s, NOT the 33s parent timeout


@posix_only
def test_file_write_is_blocked_by_fsize_limit():
    # df.to_csv bypasses the stripped `open` (pandas C path); RLIMIT_FSIZE=0 is
    # what stops it. Proves the file-write limit is a real, independent layer.
    df = pd.DataFrame({"a": [1, 2, 3]})
    out = code_sandbox.run("datasets['d'].to_csv('leak.csv')\nresult = 1", {"d": df})
    assert out["ok"] is False  # OSError: File too large surfaces as a clean error


@posix_only
def test_legitimate_analysis_still_works_under_limits():
    # The default memory cap (where enforced) must leave headroom for pandas/numpy.
    df = pd.DataFrame({"x": list(range(1000)), "g": ["a", "b"] * 500})
    code = "result = datasets['d'].groupby('g')['x'].sum().reset_index()"
    out = code_sandbox.run(code, {"d": df})
    assert out["ok"] is True
    assert out["table"] is not None


@posix_only
def test_memory_bomb_is_contained():
    # Linux-only: skip where RLIMIT_AS cannot be tightened (macOS). The runtime
    # skip keeps the multi-GB allocation from ever running where nothing would
    # contain it. Under a 256 MB cap the allocation dies; the parent stays alive.
    if not code_sandbox.memory_cap_enforced():
        pytest.skip("RLIMIT_AS not enforceable on this platform (e.g. macOS)")
    out = code_sandbox.run("result = [0] * (10 ** 9)", {}, mem_mb=256)
    assert out["ok"] is False
    again = code_sandbox.run("result = 1", {})
    assert again["ok"] is True and again["scalar"] == 1


def test_sandbox_cannot_read_local_files_via_pandas():
    # pd.read_csv on an absolute path must be blocked (defense-in-depth: pandas
    # bypasses the stripped `open`). Use this repo's own committed plan file as a
    # guaranteed-present absolute path to attempt to read.
    import pathlib
    target = str(pathlib.Path(__file__).resolve().parent.parent / "requirements.txt")
    out = code_sandbox.run(f"result = pd.read_csv({target!r}, sep='\\0', header=None)", {})
    assert out["ok"] is False
    assert "disabled" in (out["error"] or "").lower()


def test_sandbox_cannot_open_socket():
    out = code_sandbox.run(
        "import_blocked = True\nresult = pd.read_csv('http://192.0.2.1/x.csv')", {}, wall_s=8
    )
    # Either the socket block fires (RuntimeError 'disabled') or, if anything slips
    # through, the wall clock kills it — both are non-leaks. The key assertion is it
    # did NOT return data.
    assert out["ok"] is False


def test_injected_data_analysis_still_works_after_hardening():
    import pandas as pd
    df = pd.DataFrame({"g": ["a", "b", "a"], "x": [1, 2, 3]})
    out = code_sandbox.run(
        "result = int(datasets['d'].groupby('g')['x'].sum()['a'])", {"d": df}
    )
    assert out["ok"] is True
    assert out["scalar"] == 4  # 1 + 3
