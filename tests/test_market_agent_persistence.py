import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from langchain_core.messages import AIMessage

import market_agent as m
from test_run_agent_custom_stream import _FakeBuilder  # reuse the offline fake graph


async def _run(events, monkeypatch, calls):
    async def fake_upsert(container, *, thread_id, message, user_id=None, token_usage=None):
        calls.append(message)
    monkeypatch.setattr(m, "_upsert_chat_document", fake_upsert)
    monkeypatch.setattr(m, "_make_checkpointer", lambda: None)
    monkeypatch.setattr(m, "build_graph", lambda: _FakeBuilder(events))
    async for _ in m.run_agent(message="hi", thread_id="t1", user_id="alice"):
        pass


async def test_persists_user_then_assistant_with_figures(monkeypatch):
    calls = []
    events = [
        ("messages", (AIMessage(content="Hello"), {"langgraph_node": "assistant"})),
        ("custom", {"chart": {"id": "x", "title": "T", "figure_json": '{"data": [], "layout": {}}'}}),
    ]
    await _run(events, monkeypatch, calls)

    assert calls[0]["role"] == "user"
    assert calls[0]["content"] == "hi"
    assert calls[-1]["role"] == "assistant"
    assert calls[-1]["content"] == "Hello"
    assert calls[-1]["figures"] == ['{"data": [], "layout": {}}']


def _plan_msg(steps):
    # A distinct message-level id so run_agent's per-message dedup set treats it
    # as its own turn-step (LangGraph assigns these in production).
    return AIMessage(
        id="msg-plan",
        content="",
        tool_calls=[{"name": "create_plan", "args": {"objective": "briefing", "steps": steps},
                     "id": "p1", "type": "tool_call"}],
    )


def _tool_msg(name, objective, msg_id):
    return AIMessage(
        id=f"msg-{msg_id}",
        content="",
        tool_calls=[{"name": name, "args": {"objective": objective}, "id": msg_id, "type": "tool_call"}],
    )


async def test_run_agent_persists_accumulated_plan_and_actions(monkeypatch):
    calls = []
    plan_msg = _plan_msg([
        {"content": "pull figures", "status": "in_progress", "remarks": None},
        {"content": "chart it", "status": "pending", "remarks": None},
    ])
    action_msg = _tool_msg("query_dataset", "City prime rents", "a1")
    events = [
        ("values", {"messages": [plan_msg], "suggested_questions": None}),
        ("values", {"messages": [plan_msg, action_msg], "suggested_questions": None}),
        ("messages", (AIMessage(content="Rents are firm."), {"langgraph_node": "assistant"})),
    ]
    await _run(events, monkeypatch, calls)

    assistant = calls[-1]
    assert assistant["role"] == "assistant"
    # Actions accumulate in call order (plan tool excluded).
    assert assistant["actions"] == [{"tool": "query_dataset", "objective": "City prime rents"}]
    # Persisted plan is the terminal all-completed snapshot the user saw live.
    assert [s["status"] for s in assistant["plan"]] == ["completed", "completed"]
    assert [s["content"] for s in assistant["plan"]] == ["pull figures", "chart it"]


async def test_run_agent_omits_plan_actions_for_plain_answer(monkeypatch):
    # A turn with no plan and no tool calls persists neither key (backward-compat).
    calls = []
    events = [("messages", (AIMessage(content="Just an answer."), {"langgraph_node": "assistant"}))]
    await _run(events, monkeypatch, calls)

    assistant = calls[-1]
    assert assistant["content"] == "Just an answer."
    assert "plan" not in assistant
    assert "actions" not in assistant


async def test_persist_message_stores_plan_and_actions_when_present(monkeypatch):
    calls = []

    async def fake_upsert(container, *, thread_id, message, user_id=None, token_usage=None):
        calls.append(message)

    monkeypatch.setattr(m, "_upsert_chat_document", fake_upsert)
    plan = [{"content": "step 1", "status": "completed", "remarks": None}]
    actions = [{"tool": "query_dataset", "objective": "City rents"}]
    await m._persist_message("t1", "assistant", "answer", "alice", plan=plan, actions=actions)

    assert calls[0]["plan"] == plan
    assert calls[0]["actions"] == actions


async def test_persist_message_omits_plan_and_actions_when_empty(monkeypatch):
    # Backward-compat: user turns and plain text answers get neither key, so the
    # stored shape is unchanged for those (old messages restore as empty arrays).
    calls = []

    async def fake_upsert(container, *, thread_id, message, user_id=None, token_usage=None):
        calls.append(message)

    monkeypatch.setattr(m, "_upsert_chat_document", fake_upsert)
    await m._persist_message("t1", "user", "hi", "alice", plan=[], actions=[])

    assert "plan" not in calls[0]
    assert "actions" not in calls[0]


async def test_persist_error_does_not_break_stream(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("cosmos down")
    monkeypatch.setattr(m, "_upsert_chat_document", boom)
    monkeypatch.setattr(m, "_make_checkpointer", lambda: None)
    events = [("messages", (AIMessage(content="Hi"), {"langgraph_node": "assistant"}))]
    monkeypatch.setattr(m, "build_graph", lambda: _FakeBuilder(events))

    out = [c["ai_response"] async for c in m.run_agent(message="hi", thread_id="t", user_id="u")]
    assert any("Hi" in chunk for chunk in out)  # stream still produced output
