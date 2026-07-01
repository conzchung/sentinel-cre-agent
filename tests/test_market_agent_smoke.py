import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import market_agent as ma

from langchain_core.messages import AIMessage


def test_graph_builds_and_has_nodes():
    builder = ma.build_graph()
    compiled = builder.compile()
    node_names = set(compiled.get_graph().nodes.keys())
    # START/END plus our four nodes
    assert {"fetch_context", "assistant", "tools", "suggest_questions"} <= node_names


def test_tools_list_has_eleven():
    assert len(ma.TOOLS) == 11


def test_update_plan_is_registered():
    names = {getattr(tool, "name", None) for tool in ma.TOOLS}
    assert "update_plan" in names


def test_run_analysis_is_registered():
    names = {getattr(tool, "name", None) for tool in ma.TOOLS}
    assert "run_analysis" in names


def test_format_action_emits_plan_without_action_chip():
    # A lone create_plan drives only the <PLAN> block; the plan tools are kept
    # OUT of the <ACTION> list (the plan card already visualizes them).
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "create_plan", "args": {"objective": "briefing",
                "steps": [{"content": "step 1", "status": "in_progress", "remarks": None}]},
             "id": "1", "type": "tool_call"},
        ],
    )
    out = ma._format_action(ai)
    assert "<PLAN>" in out and "</PLAN>" in out
    assert "<ACTION>" not in out
    assert "create_plan" not in out


def test_format_action_update_plan_emits_plan_block():
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "update_plan", "args": {"objective": "figures done",
                "steps": [{"content": "step 1", "status": "completed", "remarks": None}]},
             "id": "1", "type": "tool_call"},
        ],
    )
    out = ma._format_action(ai)
    assert "<PLAN>" in out and "completed" in out
    assert "<ACTION>" not in out


def test_format_action_plan_tool_batched_with_real_tool():
    # update_plan attached to a real tool call in the same message: <PLAN>
    # renders, and the real tool still shows as an action chip.
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "update_plan", "args": {"objective": "starting analysis",
                "steps": [{"content": "s1", "status": "in_progress", "remarks": None}]},
             "id": "1", "type": "tool_call"},
            {"name": "query_dataset", "args": {"objective": "City rents"},
             "id": "2", "type": "tool_call"},
        ],
    )
    out = ma._format_action(ai)
    assert "<PLAN>" in out
    assert "<ACTION>" in out and "query_dataset" in out
    assert "update_plan" not in out


def test_format_action_plain_tool_has_no_plan():
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "query_dataset", "args": {"objective": "City rents"},
             "id": "2", "type": "tool_call"},
        ],
    )
    out = ma._format_action(ai)
    assert "<ACTION>" in out
    assert "<PLAN>" not in out


def test_all_completed_marks_non_deleted_steps():
    steps = [
        {"content": "a", "status": "in_progress", "remarks": None},
        {"content": "b", "status": "pending", "remarks": None},
        {"content": "c", "status": "deleted", "remarks": None},
    ]
    out = ma._all_completed(steps)
    assert out[0]["status"] == "completed"
    assert out[1]["status"] == "completed"
    assert out[2]["status"] == "deleted"  # deleted steps are left alone
    # original list is not mutated
    assert steps[0]["status"] == "in_progress"


def test_latest_plan_steps_prefers_last_plan_call():
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "create_plan", "args": {"steps": [{"content": "x", "status": "pending"}]},
             "id": "1", "type": "tool_call"},
            {"name": "update_plan", "args": {"steps": [{"content": "x", "status": "completed"}]},
             "id": "2", "type": "tool_call"},
        ],
    )
    steps = ma._latest_plan_steps(ai)
    assert steps == [{"content": "x", "status": "completed"}]


def test_latest_plan_steps_none_without_plan_tool():
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "query_dataset", "args": {"objective": "x"}, "id": "1", "type": "tool_call"},
        ],
    )
    assert ma._latest_plan_steps(ai) is None


def test_extract_actions_returns_non_plan_tools_in_order():
    # Mirrors what _format_action renders as chips: {tool, objective} for every
    # non-plan tool call, in call order. Plan tools are excluded (the plan card
    # already visualizes them) — so the restored chips match the live ones.
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "update_plan", "args": {"objective": "starting",
                "steps": [{"content": "s1", "status": "in_progress"}]},
             "id": "1", "type": "tool_call"},
            {"name": "query_dataset", "args": {"objective": "City rents"},
             "id": "2", "type": "tool_call"},
            {"name": "render_chart", "args": {"objective": "rent trend"},
             "id": "3", "type": "tool_call"},
        ],
    )
    assert ma._extract_actions(ai) == [
        {"tool": "query_dataset", "objective": "City rents"},
        {"tool": "render_chart", "objective": "rent trend"},
    ]


def test_extract_actions_empty_when_only_plan_tool():
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "create_plan", "args": {"objective": "briefing",
                "steps": [{"content": "s1", "status": "pending"}]},
             "id": "1", "type": "tool_call"},
        ],
    )
    assert ma._extract_actions(ai) == []


def test_extract_actions_defaults_missing_objective_to_empty_string():
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "list_skills", "args": {}, "id": "1", "type": "tool_call"},
        ],
    )
    assert ma._extract_actions(ai) == [{"tool": "list_skills", "objective": ""}]
