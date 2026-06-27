"""Integration test for run_agent's custom-mode → <CHART> glue.

Drives run_agent's real streaming loop offline (no LLM) by monkeypatching
build_graph to return a fake graph whose astream yields the mode/chunk tuples
we choose. This pins the contract between LangGraph's `custom` stream mode and
the <CHART> wire format, which a future LangGraph payload-shape change could
otherwise break silently.
"""

import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import market_agent as m

from langchain_core.messages import AIMessage


class _FakeCompiledGraph:
    def __init__(self, events):
        self._events = events

    async def astream(self, _input, _config, stream_mode=None):
        for mode, chunk in self._events:
            yield mode, chunk


class _FakeBuilder:
    def __init__(self, events):
        self._events = events

    def compile(self, checkpointer=None):
        return _FakeCompiledGraph(self._events)


async def _noop(*a, **k):
    return None


async def _collect(events, monkeypatch):
    monkeypatch.setattr(m, "build_graph", lambda: _FakeBuilder(events))
    monkeypatch.setattr(m, "_make_checkpointer", lambda: None)
    monkeypatch.setattr(m, "_persist_message", _noop)
    out = []
    async for chunk in m.run_agent(message="hi", thread_id="t1"):
        out.append(chunk["ai_response"])
    return out


async def test_custom_chart_payload_becomes_chart_tag(monkeypatch):
    figure_json = '{"data": [], "layout": {"title": {"text": "Prime Rent"}}}'
    events = [("custom", {"chart": {"id": "abc123", "title": "Prime Rent", "figure_json": figure_json}})]
    out = await _collect(events, monkeypatch)

    joined = "".join(out)
    assert "<CHART>" in joined and "</CHART>" in joined
    body = joined[joined.index("<CHART>\n") + len("<CHART>\n"):joined.index("\n</CHART>")]
    assert base64.b64decode(body.encode("ascii")).decode("utf-8") == figure_json


async def test_chart_is_flushed_after_response_block(monkeypatch):
    # render_chart emits its custom chart payload DURING tool execution — before
    # the assistant streams its answer. run_agent must buffer the chart and flush
    # it only AFTER </RESPONSE>, so the chart never strands above empty prose.
    figure_json = '{"data": [], "layout": {"title": {"text": "Prime Rent"}}}'
    events = [
        ("custom", {"chart": {"id": "c1", "title": "Prime Rent", "figure_json": figure_json}}),
        ("messages", (AIMessage(content="Prime City rents rose."), {"langgraph_node": "assistant"})),
    ]
    out = await _collect(events, monkeypatch)

    joined = "".join(out)
    assert "<RESPONSE>" in joined and "</RESPONSE>" in joined and "<CHART>" in joined
    # The chart tag must come strictly after the response block closes.
    assert joined.index("<CHART>") > joined.index("</RESPONSE>")
    # And the answer text is present inside the response block, above the chart.
    assert joined.index("Prime City rents rose.") < joined.index("<CHART>")


async def test_non_chart_custom_payload_is_ignored(monkeypatch):
    events = [("custom", {"progress": "thinking"})]
    out = await _collect(events, monkeypatch)
    assert all("<CHART>" not in chunk for chunk in out)


async def test_custom_payload_with_empty_figure_json_emits_nothing(monkeypatch):
    events = [("custom", {"chart": {"id": "x", "title": "T", "figure_json": ""}})]
    out = await _collect(events, monkeypatch)
    assert all("<CHART>" not in chunk for chunk in out)


def _plan_msg(steps):
    return AIMessage(
        content="",
        tool_calls=[{"name": "create_plan", "args": {"objective": "briefing", "steps": steps},
                     "id": "p1", "type": "tool_call"}],
    )


async def test_plan_turn_ends_with_all_completed_plan(monkeypatch):
    # A create_plan with steps still pending/in_progress should, at the end of the
    # turn, get a deterministic terminal <PLAN> marking every step completed — even
    # though the model never emitted an update_plan.
    steps = [
        {"content": "step 1", "status": "in_progress", "remarks": None},
        {"content": "step 2", "status": "pending", "remarks": None},
    ]
    events = [("values", {"messages": [_plan_msg(steps)], "suggested_questions": None})]
    out = await _collect(events, monkeypatch)

    joined = "".join(out)
    plan_blocks = joined.count("<PLAN>")
    assert plan_blocks >= 2  # the initial plan, plus the terminal completed one
    # The LAST plan block has no remaining pending/in_progress steps.
    last_plan = joined.rsplit("<PLAN>", 1)[1]
    assert "'status': 'completed'" in last_plan
    assert "'status': 'pending'" not in last_plan
    assert "'status': 'in_progress'" not in last_plan


async def test_no_plan_turn_emits_no_terminal_plan(monkeypatch):
    # A turn whose only tool call is a normal tool must not synthesize a <PLAN>.
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "query_dataset", "args": {"objective": "City rents"},
                     "id": "q1", "type": "tool_call"}],
    )
    events = [("values", {"messages": [msg], "suggested_questions": None})]
    out = await _collect(events, monkeypatch)
    assert all("<PLAN>" not in chunk for chunk in out)
