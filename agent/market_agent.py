"""Sentinel market-monitoring agent: LangGraph assembly and streaming runner."""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, AsyncIterator, Dict, Optional

from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES, RemoveMessage
from langgraph.checkpoint.memory import MemorySaver

import skills_registry as sr
from market_agent_prompts import build_system_prompt, SUGGEST_QUESTIONS_PROMPT
from market_agent_tools import (
    list_skills,
    read_skill,
    read_skill_file,
    query_dataset,
    render_chart,
    web_search,
    knowledge_search,
    create_plan,
    update_plan,
    generate_report,
    run_analysis,
)
from agent_utils import (
    repair_missing_tool_messages,
    summarize_conversation,
    create_tool_node_with_fallback,
    _upsert_chat_document,
)
from models import init_llm, GPT54_args
from db import hong_kong_tz, sentinel_convo_container, SENTINEL_CHECKPOINT_CONTAINER_NAME

logger = logging.getLogger(__name__)


def _make_checkpointer():
    """Persistent Cosmos checkpointer for real cross-turn memory; falls back to
    in-memory if Cosmos / the saver package is unavailable (e.g. offline tests)."""
    try:
        from langgraph_checkpoint_cosmosdb import CosmosDBSaver
        return CosmosDBSaver(
            database_name="agentMemory",
            container_name=SENTINEL_CHECKPOINT_CONTAINER_NAME,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("CosmosDBSaver unavailable, using in-memory: %s", exc)
        return MemorySaver()


async def _persist_message(thread_id, role, content, user_id, figures=None):
    """Best-effort upsert of one dialog turn into sentinelConvo. Never raises —
    persistence must not block or break the response stream."""
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(hong_kong_tz).strftime("%Y/%m/%d %H:%M:%S"),
    }
    if figures is not None:
        message["figures"] = figures
    try:
        await _upsert_chat_document(
            sentinel_convo_container,
            thread_id=thread_id,
            message=message,
            user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("persist %s message failed: %s", role, exc)

TOOLS = [
    list_skills,
    read_skill,
    read_skill_file,
    query_dataset,
    render_chart,
    web_search,
    knowledge_search,
    create_plan,
    update_plan,
    generate_report,
    run_analysis,
]


class OverallState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    suggested_questions: str


async def fetch_context(state, config: RunnableConfig) -> dict:
    """Repair tool messages, summarize if huge, and refresh nothing else.

    The skills catalog and date are injected via the system prompt at model
    binding time, so this node only manages message hygiene.
    """
    messages = repair_missing_tool_messages(state.get("messages") or [])
    total_tokens = count_tokens_approximately(messages)
    if len(messages) > 10 and total_tokens > 100_000:
        try:
            messages = await summarize_conversation(messages, messages_to_keep=10)
        except Exception as exc:  # noqa: BLE001
            logger.error("summarize failed: %s", exc)
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages]}


def _today() -> str:
    return datetime.now(hong_kong_tz).strftime("%Y/%m/%d")


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    async def __call__(self, state: OverallState, config: RunnableConfig):
        result = await self.runnable.ainvoke(state)
        # Guard against empty responses (mirrors the base agent).
        if not result.tool_calls and not (result.content or "").strip():
            result = await self.runnable.ainvoke(
                {**state, "messages": state["messages"] + [("user", "Respond with a real answer.")]}
            )
        return {"messages": result}


def _tools_or_suggest(state) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "suggest_questions"


def _tools_used_this_turn(messages: list) -> str:
    """Collect the tool names called since the most recent human message, so the
    suggestion prompt can steer the user to a step they have NOT done yet."""
    names: list[str] = []
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            break
        for tc in getattr(m, "tool_calls", None) or []:
            name = tc.get("name")
            if name and name not in names:
                names.append(name)
    names.reverse()  # restore call order
    return ", ".join(names) if names else "(none)"


async def suggest_questions(state) -> dict:
    messages = state["messages"]
    human = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    ai = next((m.content for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), "")
    tools_used = _tools_used_this_turn(messages)
    llm = init_llm(GPT54_args)
    prompt = PromptTemplate(
        template=SUGGEST_QUESTIONS_PROMPT,
        input_variables=["human_message", "ai_message", "tools_used"],
    )
    chain = prompt | llm | StrOutputParser()
    try:
        out = await chain.ainvoke(
            {"human_message": human, "ai_message": ai, "tools_used": tools_used}
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("suggest_questions failed: %s", exc)
        out = ""
    return {"suggested_questions": out}


def build_graph() -> StateGraph:
    skills_catalog = sr.build_catalog(sr.discover_skills())
    system_prompt = build_system_prompt(skills_catalog, _today())

    llm = init_llm(GPT54_args)
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("placeholder", "{messages}")]
    )
    assistant_runnable = prompt | llm.bind_tools(TOOLS)

    builder = StateGraph(OverallState)
    builder.add_node("fetch_context", fetch_context)
    builder.add_node("assistant", Assistant(assistant_runnable))
    builder.add_node("tools", create_tool_node_with_fallback(TOOLS))
    builder.add_node("suggest_questions", suggest_questions)

    builder.add_edge(START, "fetch_context")
    builder.add_edge("fetch_context", "assistant")
    builder.add_conditional_edges(
        "assistant", _tools_or_suggest, {"tools": "tools", "suggest_questions": "suggest_questions"}
    )
    builder.add_edge("tools", "assistant")
    builder.add_edge("suggest_questions", END)
    return builder


def _format_action(ai_message: AIMessage) -> str:
    """Render an AIMessage's tool calls as an <ACTION> block, and surface a
    <PLAN> block when the model called create_plan or update_plan.

    The plan tools (create_plan/update_plan) only drive the <PLAN> block and are
    kept OUT of the <ACTION> list — the plan card already visualizes them, so a
    "Create Plan"/"Update Plan" chip would just be noise. update_plan re-emits
    <PLAN> with advanced statuses; the frontend replaces the plan on each one."""
    action_lines = []
    plan_block = ""
    for tc in ai_message.tool_calls:
        name = tc["name"]
        args = tc.get("args", {})
        objective = args.get("objective", "")
        if name in ("create_plan", "update_plan"):
            steps = args.get("steps", [])
            # A later update in the same message wins (latest status snapshot).
            plan_block = f"<PLAN>\n{steps}\n</PLAN>\n\n"
            continue
        action_lines.append(f"Action: {name}\nDetails: {objective}\n")
    if not action_lines:
        return plan_block
    action = "<ACTION>\n\n" + "\n".join(action_lines) + "</ACTION>\n\n"
    return plan_block + action


def _latest_plan_steps(ai_message: AIMessage) -> Optional[list]:
    """Return the steps list from the last create_plan/update_plan call in this
    message, or None if it has no plan tool call. A later call in the same
    message wins, mirroring _format_action's last-write semantics."""
    steps = None
    for tc in ai_message.tool_calls:
        if tc["name"] in ("create_plan", "update_plan"):
            steps = tc.get("args", {}).get("steps", [])
    return steps


def _all_completed(steps: list) -> list:
    """Mark every non-deleted step completed — the deterministic terminal state
    once the turn finishes, so the plan never freezes mid-progress even if the
    model forgot to emit a final update_plan."""
    out = []
    for s in steps or []:
        step = dict(s) if isinstance(s, dict) else {"content": str(s)}
        if step.get("status") != "deleted":
            step["status"] = "completed"
        out.append(step)
    return out


def _format_chart(figure_json: str) -> str:
    """Wrap a Plotly figure JSON as an atomic, base64-encoded <CHART> block.

    Base64 keeps the payload opaque to the frontend's tag regex, so braces,
    quotes, or even a literal </RESPONSE> inside the figure cannot corrupt
    stream parsing.
    """
    encoded = base64.b64encode(figure_json.encode("utf-8")).decode("ascii")
    return f"<CHART>\n{encoded}\n</CHART>\n\n"


async def run_agent(
    message: str,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream the agent's response as tagged chunks.

    Yields dicts {"thread_id": str, "ai_response": str} where ai_response holds
    <ACTION>/<PLAN>/<RESPONSE>/<SUGGESTION> blocks.
    """
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}, "recursion_limit": 50}

    graph = build_graph().compile(checkpointer=_make_checkpointer())

    # Persist the user's message up front (best-effort).
    await _persist_message(thread_id, "user", message, user_id)

    streamed_action_ids: set = set()
    response_open = False
    response_parts: list[str] = []
    figure_jsons: list[str] = []
    latest_plan_steps: Optional[list] = None  # last plan snapshot seen this turn

    async for mode, chunk in graph.astream(
        {"messages": [HumanMessage(content=message)], "suggested_questions": None},
        config,
        stream_mode=["messages", "values", "custom"],
    ):
        if mode == "messages":
            msg_chunk, meta = chunk
            # Stream ONLY the assistant node's answer tokens (no tool calls).
            # Without the node guard, the suggest_questions node's LLM tokens
            # would leak into the open <RESPONSE> block.
            if (
                meta.get("langgraph_node") == "assistant"
                and isinstance(msg_chunk, AIMessage)
                and not msg_chunk.tool_calls
            ):
                text = msg_chunk.content
                if text:
                    if not response_open:
                        response_open = True
                        yield {"thread_id": thread_id, "ai_response": "<RESPONSE>\n"}
                    yield {"thread_id": thread_id, "ai_response": text}
                    response_parts.append(text)
        elif mode == "custom":
            # Chart payloads pushed by render_chart via get_stream_writer. render_chart
            # runs DURING tool execution — i.e. before the assistant streams its answer
            # tokens — so emitting the <CHART> here would strand the chart above (or
            # mid-) an empty answer. Buffer it instead and flush after </RESPONSE>.
            if isinstance(chunk, dict) and "chart" in chunk:
                figure_json = chunk["chart"].get("figure_json", "")
                if figure_json:
                    figure_jsons.append(figure_json)
        elif mode == "values":
            messages = chunk.get("messages") or []
            last = messages[-1] if messages else None
            # Emit ACTION/PLAN once per assistant message that has tool calls.
            if isinstance(last, AIMessage) and last.tool_calls and last.id not in streamed_action_ids:
                streamed_action_ids.add(last.id)
                plan_steps = _latest_plan_steps(last)
                if plan_steps is not None:
                    latest_plan_steps = plan_steps
                yield {"thread_id": thread_id, "ai_response": _format_action(last)}
            # Emit suggestions when present.
            sq = chunk.get("suggested_questions")
            if sq and "suggestions" not in streamed_action_ids:
                streamed_action_ids.add("suggestions")
                if response_open:
                    yield {"thread_id": thread_id, "ai_response": "\n</RESPONSE>\n\n"}
                    response_open = False
                yield {"thread_id": thread_id, "ai_response": f"<SUGGESTION>\n{sq}\n</SUGGESTION>\n\n"}

    if response_open:
        yield {"thread_id": thread_id, "ai_response": "\n</RESPONSE>\n\n"}

    # Flush buffered charts AFTER the answer text, so every client sees the chart
    # described by prose that already arrived above it — never stranded over an
    # empty answer mid-stream (render_chart emits during tool execution).
    for figure_json in figure_jsons:
        yield {"thread_id": thread_id, "ai_response": _format_chart(figure_json)}

    # Deterministic terminal state: if this turn had a plan, re-emit it with every
    # non-deleted step completed. Guarantees the plan never freezes mid-progress
    # even when the model skips a final update_plan. The frontend replaces the
    # plan on this last <PLAN>, so it lands after the answer text.
    if latest_plan_steps:
        final_steps = _all_completed(latest_plan_steps)
        yield {"thread_id": thread_id, "ai_response": f"<PLAN>\n{final_steps}\n</PLAN>\n\n"}

    await _persist_message(
        thread_id, "assistant", "".join(response_parts), user_id, figures=figure_jsons
    )
