import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pandas as pd

import code_sandbox


def test_groupby_mean_returns_correct_numbers():
    df = pd.DataFrame(
        {"submarket": ["City", "City", "West End"], "rent": [80.0, 82.0, 120.0]}
    )
    code = (
        "g = datasets['rents'].groupby('submarket')['rent'].mean().round(1)\n"
        "result = g.reset_index()"
    )
    out = code_sandbox.run(code, {"rents": df})
    assert out["ok"] is True
    assert out["kind"] in ("dataframe", "series")
    # to_markdown strips trailing-zero decimals: 81.0 -> "81", 120.0 -> "120".
    assert "81" in out["table"]  # mean of 80 and 82
    assert "120" in out["table"]
    assert "West End" in out["table"]


def test_cross_dataset_merge():
    rents = pd.DataFrame({"q": ["Q1"], "submarket": ["City"], "rent": [80.0]})
    vac = pd.DataFrame({"q": ["Q1"], "submarket": ["City"], "vac": [8.0]})
    code = (
        "m = datasets['rents'].merge(datasets['vac'], on=['q', 'submarket'])\n"
        "m['ratio'] = (m['rent'] / m['vac']).round(1)\n"
        "result = m[['submarket', 'ratio']]"
    )
    out = code_sandbox.run(code, {"rents": rents, "vac": vac})
    assert out["ok"] is True
    assert "10" in out["table"]  # 80 / 8 = 10.0, rendered as "10"


def test_scalar_result():
    df = pd.DataFrame({"rent": [10, 20, 30]})
    out = code_sandbox.run("result = int(datasets['d']['rent'].sum())", {"d": df})
    assert out["ok"] is True
    assert out["kind"] == "scalar"
    assert out["scalar"] == 60


def test_no_result_assigned_is_clean():
    out = code_sandbox.run("x = 1 + 1", {})
    assert out["ok"] is True
    assert out["kind"] == "none"


def test_user_code_exception_is_clean_and_parent_survives():
    out = code_sandbox.run("result = 1 / 0", {})
    assert out["ok"] is False
    assert "ZeroDivision" in out["error"]
    # parent still works afterwards
    again = code_sandbox.run("result = 2", {})
    assert again["ok"] is True and again["scalar"] == 2


def test_open_is_blocked():
    out = code_sandbox.run("result = open('/etc/hosts').read()", {})
    assert out["ok"] is False
    assert "NameError" in out["error"] or "not defined" in out["error"]


def test_import_is_blocked():
    out = code_sandbox.run("result = __import__('os').getcwd()", {})
    assert out["ok"] is False
    assert "NameError" in out["error"] or "not defined" in out["error"]


def test_child_spawned_without_parent_environment(monkeypatch):
    captured = {}

    class _FakePopen:
        def __init__(self, *args, **kwargs):
            captured["env"] = kwargs.get("env")
            self.returncode = 0

        def communicate(self, input=None, timeout=None):
            self.returncode = 0
            return (
                json.dumps(
                    {"ok": True, "kind": "scalar", "result": 1,
                     "stdout": "", "n_rows": None}
                ),
                "",
            )

        def kill(self):
            pass

    monkeypatch.setenv("SENTINEL_SECRET", "do-not-leak")
    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    code_sandbox.run("result = 1", {})
    assert captured["env"] == code_sandbox._CHILD_ENV
    assert captured["env"]["PYTHONPATH"] == code_sandbox._AGENT_DIR
    assert "SENTINEL_SECRET" not in captured["env"]


def test_oversized_result_is_rejected():
    code = "result = pd.DataFrame({'a': range(200000)})"
    out = code_sandbox.run(code, {})
    assert out["ok"] is False
    assert "too large" in out["error"]


def test_timeout_kills_child_and_parent_survives():
    out = code_sandbox.run("\nwhile True:\n    pass\n", {}, wall_s=2)
    assert out["ok"] is False
    assert "timed out" in out["error"].lower()
    again = code_sandbox.run("result = 3", {})
    assert again["ok"] is True and again["scalar"] == 3
