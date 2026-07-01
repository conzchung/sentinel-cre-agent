"""Mid-run disconnect safety for run_agent.

If the client disconnects while a slow tool is still running, the streaming
response is cancelled — CancelledError is thrown into run_agent's astream loop.
Without a shielded finally, the "persist assistant turn" line never runs and the
whole turn is lost. These tests pin that the turn is saved exactly once on
cancellation (with the partial content) and exactly once on normal completion.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pytest
from langchain_core.messages import AIMessage

import market_agent as m
from test_run_agent_custom_stream import _FakeBuilder  # non-blocking fake graph


class _BlockingGraph:
    """astream yields the given events, then blocks forever — simulating a slow
    tool still running when the client disconnects."""

    def __init__(self, events):
        self._events = events

    async def astream(self, _input, _config, stream_mode=None):
        for mode, chunk in self._events:
            yield mode, chunk
        await asyncio.Event().wait()  # never set → blocks until cancelled


class _BlockingBuilder:
    def __init__(self, events):
        self._events = events

    def compile(self, checkpointer=None):
        return _BlockingGraph(self._events)


def _install(monkeypatch, builder, calls):
    async def fake_upsert(container, *, thread_id, message, user_id=None, token_usage=None):
        calls.append(message)

    monkeypatch.setattr(m, "_upsert_chat_document", fake_upsert)
    monkeypatch.setattr(m, "_make_checkpointer", lambda: None)
    monkeypatch.setattr(m, "build_graph", lambda: builder)


async def test_persist_on_cancel_saves_partial_turn_exactly_once(monkeypatch):
    calls = []
    events = [("messages", (AIMessage(content="Partial answer."), {"langgraph_node": "assistant"}))]
    _install(monkeypatch, _BlockingBuilder(events), calls)

    received = []

    async def consume():
        async for chunk in m.run_agent(message="hi", thread_id="t1", user_id="u"):
            received.append(chunk["ai_response"])

    task = asyncio.create_task(consume())
    # Let the partial answer stream out while the graph stays blocked mid-tool.
    for _ in range(200):
        await asyncio.sleep(0.01)
        if any("Partial answer." in r for r in received):
            break
    assert any("Partial answer." in r for r in received), "stream never produced the partial answer"

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The assistant turn survived the cancellation — persisted once, with the
    # partial content the user had already seen.
    assistant = [c for c in calls if c["role"] == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["content"] == "Partial answer."


async def test_normal_completion_persists_assistant_exactly_once(monkeypatch):
    # The shielded finally must not double-write on the happy path.
    calls = []
    events = [("messages", (AIMessage(content="Done."), {"langgraph_node": "assistant"}))]
    _install(monkeypatch, _FakeBuilder(events), calls)

    async for _ in m.run_agent(message="hi", thread_id="t1", user_id="u"):
        pass

    assistant = [c for c in calls if c["role"] == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["content"] == "Done."
