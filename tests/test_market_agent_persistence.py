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


async def test_persist_error_does_not_break_stream(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("cosmos down")
    monkeypatch.setattr(m, "_upsert_chat_document", boom)
    monkeypatch.setattr(m, "_make_checkpointer", lambda: None)
    events = [("messages", (AIMessage(content="Hi"), {"langgraph_node": "assistant"}))]
    monkeypatch.setattr(m, "build_graph", lambda: _FakeBuilder(events))

    out = [c["ai_response"] async for c in m.run_agent(message="hi", thread_id="t", user_id="u")]
    assert any("Hi" in chunk for chunk in out)  # stream still produced output
