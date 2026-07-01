"""Shared tools for the Sentinel London office market agent.

Every tool takes a leading ``objective`` parameter: a short, human-readable
label for the call (a few words, shown to the user in the action log). Keep it
concise — a chip caption, not a sentence.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langgraph.config import get_stream_writer

import skills_registry as sr
import rag_embeddings
import rag_store
import code_sandbox
from report_builder import build_report_pdf
from agent_utils import upload_blob_and_get_url
from db import hong_kong_tz

logger = logging.getLogger(__name__)

_REPORT_CONTAINER = "aiagentdocs"
_REPORT_PREFIX = "sentinel_reports"


@tool
async def list_skills(objective: str) -> str:
    """List the market-monitoring skills available to you, with their ids and
    when to use each. Call this when deciding which skill applies to the user's
    request.

    Args:
        objective: Short label for this call (a few words), shown to the user.
    """
    return sr.build_catalog(sr.discover_skills())


@tool
async def read_skill(objective: str, skill_id: str) -> str:
    """Load the full instructions (the SKILL.md body) for one skill. Call this
    after you have picked a skill from `list_skills`, before doing the work.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        skill_id: The skill id, e.g. "rent_vacancy_trends".
    """
    return sr.read_skill_body(skill_id)


@tool
async def read_skill_file(objective: str, skill_id: str, filename: str) -> str:
    """Read a raw reference or data file inside a skill's data/ folder. Use this
    to inspect a dataset directly; for filtered analysis prefer `query_dataset`.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        skill_id: The skill id that owns the file.
        filename: The bare filename, e.g. "prime_rents.csv".
    """
    return sr.read_skill_data_file(skill_id, filename)


@tool
async def query_dataset(
    objective: str,
    skill_id: str,
    dataset: str,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """Load a skill's seed CSV and return the rows (optionally filtered) as a
    markdown table. Use this for quantitative questions and to get rows you will
    pass to `render_chart`.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        skill_id: The skill that owns the dataset, e.g. "rent_vacancy_trends".
        dataset: The CSV filename, e.g. "prime_rents.csv".
        filters: Optional column -> value (or list of values) filters, e.g.
            {"submarket": "City"} or {"quarter": ["2025Q1", "2025Q2"]}.
    """
    skill = sr.get_skill(skill_id)
    if skill is None:
        return f"Error: no skill with id '{skill_id}'."
    safe_dataset = Path(dataset).name
    csv_path = skill.path / "data" / safe_dataset
    if not csv_path.exists():
        return f"Error: dataset '{dataset}' not found in skill '{skill_id}'."

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:  # noqa: BLE001
        return f"Error reading dataset '{dataset}': {exc}"

    if filters:
        for col, val in filters.items():
            if col not in df.columns:
                return (
                    f"Error: column '{col}' not in {dataset}. "
                    f"Available columns: {', '.join(df.columns)}."
                )
            values = val if isinstance(val, list) else [val]
            df = df[df[col].isin(values)]

    if df.empty:
        return f"No rows matched filters {filters} in {dataset}."

    table = df.to_markdown(index=False)
    return f"{len(df)} row(s) from {skill_id}/{dataset}:\n\n{table}"


def _build_figure(chart_spec: Dict[str, Any]) -> go.Figure:
    """Build a Plotly figure from a chart_spec. Raises ValueError on bad type."""
    chart_type = chart_spec.get("type", "line")
    series = chart_spec.get("series", [])
    fig = go.Figure()

    if chart_type == "line":
        for s in series:
            fig.add_trace(
                go.Scatter(x=s["x"], y=s["y"], mode="lines+markers", name=s.get("name", ""))
            )
    elif chart_type == "bar":
        s = series[0]
        fig.add_trace(go.Bar(x=s["x"], y=s["y"], name=s.get("name", "")))
    elif chart_type == "grouped_bar":
        for s in series:
            fig.add_trace(go.Bar(x=s["x"], y=s["y"], name=s.get("name", "")))
        fig.update_layout(barmode="group")
    else:
        raise ValueError(f"Unsupported chart type '{chart_type}'.")

    fig.update_layout(
        title=chart_spec.get("title", ""),
        xaxis_title=chart_spec.get("x_label", ""),
        yaxis_title=chart_spec.get("y_label", ""),
        showlegend=len(series) > 1 or chart_type == "line",
        template="plotly_white",
        margin=dict(l=60, r=30, t=50, b=50),
    )
    return fig


@tool
async def render_chart(objective: str, chart_spec: Dict[str, Any]) -> str:
    """Render an INTERACTIVE chart (line, bar, or grouped_bar) from series data.

    The chart is sent to the UI automatically and appears below your answer —
    do NOT write a markdown image link. Just refer to the chart in your prose.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        chart_spec: {
            "type": "line" | "bar" | "grouped_bar",
            "title": str, "x_label": str, "y_label": str,
            "series": [{"name": str, "x": [...], "y": [...]}, ...]
        }
    """
    series = chart_spec.get("series", [])
    title = chart_spec.get("title", "")
    if not series:
        return "Could not render chart: chart_spec.series is empty."

    try:
        fig = _build_figure(chart_spec)
    except (ValueError, KeyError, IndexError) as exc:
        return f"Could not render chart: {exc}"

    chart_id = uuid.uuid4().hex[:12]
    try:
        writer = get_stream_writer()
        writer({"chart": {"id": chart_id, "title": title, "figure_json": fig.to_json()}})
    except Exception as exc:  # noqa: BLE001 — side channel may be absent (e.g. outside a graph run)
        logger.warning("render_chart could not emit chart to stream: %s", exc)

    return f"Chart {chart_id} rendered: {title}"


async def _tavily_search(question: str, search_context_size: str = "low") -> dict:
    """Run a Tavily web search and format results with citation indices."""
    search_depth = "basic" if search_context_size == "low" else "advanced"
    try:
        searcher = TavilySearch(max_results=5, topic="general", search_depth=search_depth)
        results = await searcher.ainvoke({"query": question})
        content = ""
        citations = []
        for idx, result in enumerate(results["results"], start=1):
            citations.append({str(idx): result["url"]})
            content += result["content"] + f"[{idx}]\n\n=====\n\n"
        return {"content": content, "citations": citations}
    except Exception as exc:  # noqa: BLE001
        logger.error("web_search failed: %s", exc)
        return {"content": f"Error during web search: {exc}", "citations": []}


@tool
async def web_search(objective: str, user_query: str) -> dict:
    """Search the live web for current London office market information, news,
    and figures. Use to supplement seed data with up-to-date facts and to get
    citations.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        user_query: A concise, specific search query.
    """
    return await _tavily_search(user_query, search_context_size="low")


@tool
async def knowledge_search(objective: str, query: str, top_k: int = 4) -> dict:
    """Semantic search over Sentinel's internal analyst-commentary corpus
    (qualitative market drivers: flight-to-quality, ESG/EPC, hybrid working,
    submarket color). Use this for the *why / so-what* behind the numbers; use
    `query_dataset` for figures and `web_search` for live news. Returns the
    same {content, citations} shape as web_search — cite results with [n].

    Args:
        objective: Short label for this call (a few words), shown to the user.
        query: A concise natural-language query describing what you need.
        top_k: How many notes to retrieve (default 4).
    """
    try:
        vector = await rag_embeddings.embed_text(query)
        hits = await rag_store.search(vector, top_k=top_k)
    except Exception as exc:  # noqa: BLE001 — never raise into the stream
        logger.error("knowledge_search failed: %s", exc)
        return {"content": "No matching research notes found.", "citations": []}

    if not hits:
        return {"content": "No matching research notes found.", "citations": []}

    content = ""
    citations = []
    for idx, hit in enumerate(hits, start=1):
        payload = hit.get("payload", {})
        text = payload.get("text", "")
        content += text + f"[{idx}]\n\n=====\n\n"
        citations.append({str(idx): f"{payload.get('source', '')}, {payload.get('as_of', '')}"})
    return {"content": content, "citations": citations}


@tool
async def create_plan(objective: str, steps: List[Dict[str, Any]]) -> str:
    """Record a step-by-step plan for a MULTI-STEP request (e.g. a full market
    briefing across submarkets). Only call this when the task genuinely needs
    several steps; for a single direct question, just answer.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        steps: A list of {"content": str, "status":
            "pending"|"in_progress"|"completed"|"deleted", "remarks": str|None}.
    """
    return f"Recorded a plan with {len(steps)} step(s). Proceed to execute them."


@tool
async def update_plan(objective: str, steps: List[Dict[str, Any]]) -> str:
    """Update the progress of the plan you created with `create_plan`. Call this
    AS YOU GO to reflect true progress: mark finished steps "completed" and the
    one you are starting "in_progress". To avoid extra latency, include this call
    IN THE SAME turn as the next tool you run (you may emit several tool calls at
    once) — the plan re-renders with your updated statuses.

    Pass the FULL steps list every time (same content and order as `create_plan`),
    not just the changed step.

    Args:
        objective: Short label for this call (a few words, e.g. "figures done,
            starting analysis"), shown to the user.
        steps: The complete list of {"content": str, "status":
            "pending"|"in_progress"|"completed"|"deleted", "remarks": str|None},
            same length and order as the original plan, with statuses advanced.
    """
    completed = sum(1 for s in steps if (s or {}).get("status") == "completed")
    return f"Plan updated: {completed}/{len(steps)} step(s) completed."


def _blob_service_client():
    """Build the async BlobServiceClient lazily so a missing connection string
    never breaks tool-module import (the other Sentinel tools must still load)."""
    from azure.storage.blob.aio import BlobServiceClient

    conn = os.getenv("BLOB_CONNECTION_STRING")
    if not conn:
        raise RuntimeError("BLOB_CONNECTION_STRING is not set.")
    return BlobServiceClient.from_connection_string(conn)


@tool
async def generate_report(
    objective: str,
    title: str,
    sections: List[Dict[str, Any]],
    config: RunnableConfig,
    subtitle: Optional[str] = None,
) -> str:
    """Generate a downloadable PDF report (text + charts) from sections YOU
    compose, upload it, and return a download link to embed in your answer.

    Use this when the user wants to take the discussion away as a document
    (e.g. "make me a PDF", "put this in a report", "send me a briefing I can
    share"). Compose the prose yourself from what you have already discussed —
    this tool only lays it out; it does not write content for you.

    The tool returns a short confirmation containing a URL. Put that URL in your
    answer as a markdown link like `[Download the report](URL)`. Do NOT paste
    the whole report back into chat.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        title: The report title, e.g. "London Office Market Briefing".
        sections: Ordered list of sections. Each is a dict:
            {"heading": str,
             "body_markdown": str,   # the section prose, markdown allowed
             "chart_spec": dict | None}  # same shape as render_chart, or omit
            The chart_spec, when present, is rendered as a static chart image in
            the PDF. Reuse the exact chart_spec you would pass to render_chart.
        subtitle: Optional subtitle / as-of line, e.g. "Q2 2025 snapshot".
    """
    if not sections:
        return "There is nothing to report yet — no sections were provided."

    thread_id = config.get("configurable", {}).get("thread_id", "nothread")
    try:
        generated_at = datetime.now(hong_kong_tz).strftime("%Y/%m/%d %H:%M:%S")
        pdf_bytes = build_report_pdf(
            title, subtitle, sections, generated_at=generated_at
        )
    except Exception as exc:  # noqa: BLE001 — never raise into the stream
        logger.error("generate_report build failed: %s", exc)
        return f"Could not generate report: {exc}"

    try:
        timestamp = datetime.now(hong_kong_tz).strftime("%Y%m%d_%H%M%S")
        report_id = uuid.uuid4().hex[:8]
        blob_name = f"{_REPORT_PREFIX}/{thread_id}_{timestamp}_{report_id}.pdf"
        async with _blob_service_client() as client:
            url = await upload_blob_and_get_url(
                container_name=_REPORT_CONTAINER,
                blob_name=blob_name,
                data=pdf_bytes,
                blob_service_client=client,
                content_type="application/pdf",
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("generate_report upload failed: %s", exc)
        return f"Could not generate report: upload failed: {exc}"

    return f"Report ready: {url}"


def _format_analysis_result(result: Dict[str, Any]) -> str:
    """Turn code_sandbox.run's normalized dict into a markdown string for the
    agent. Caps total length so a fat result cannot blow up model context."""
    if not result.get("ok"):
        return f"Could not run analysis: {result.get('error', 'unknown error')}"

    kind = result.get("kind")
    parts: List[str] = []
    if kind in ("dataframe", "series"):
        parts.append(result.get("table") or "(empty result)")
        if result.get("truncated"):
            parts.append(
                f"\n_Showing first {code_sandbox.MAX_DISPLAY_ROWS} of "
                f"{result.get('n_rows')} rows._"
            )
    elif kind == "dict":
        scalar = result.get("scalar") or {}
        if scalar:
            rows = "\n".join(f"| {k} | {v} |" for k, v in scalar.items())
            parts.append("| key | value |\n| --- | --- |\n" + rows)
        else:
            parts.append("(empty result)")
    elif kind == "scalar":
        parts.append(f"Result: {result.get('scalar')}")
    else:  # "none" / unset
        return "Your code ran but did not assign `result`."

    stdout = (result.get("stdout") or "").strip()
    if stdout:
        parts.append(f"\n--- output ---\n{stdout}")

    out = "\n".join(parts)
    if len(out) > 4000:
        out = out[:4000] + "\n…(truncated)"
    return out


@tool
async def run_analysis(
    objective: str,
    code: str,
    datasets: List[Dict[str, str]],
) -> str:
    """Run real pandas/numpy on the seed datasets for ACTUAL computation —
    joins across datasets, group-by, growth rates, ratios, statistics.

    Write Python that reads `datasets["<handle>"]` (a pandas DataFrame per CSV
    you name) and assigns the answer to a top-level variable `result`. Available
    names: `pd`, `np`, `datasets`. No imports, no file or network access. Make
    `result` a DataFrame (rendered as a table), a dict, or a number.

    Prefer this over doing arithmetic yourself. Use `query_dataset` only for a
    simple filtered view of ONE csv. After you get the computed numbers back,
    you may chart them with `render_chart` using a chart_spec built from them.

    Args:
        objective: Short label for this call (a few words), shown to the user.
        code: Python that assigns `result`. Example:
            rents = datasets["prime_rents"]
            vac = datasets["vacancy"]
            m = rents.merge(vac, on=["quarter", "submarket"])
            m["ratio"] = (m["prime_rent_psf"] / m["vacancy_rate_pct"]).round(2)
            result = m.groupby("submarket")["ratio"].mean().round(2).reset_index()
        datasets: Which seed CSVs to load. Each entry is
            {"skill_id": str, "dataset": str, "as": str (optional handle)}.
            Without "as", the handle defaults to the filename stem
            (prime_rents.csv -> datasets["prime_rents"]).
    """
    if not code or not code.strip():
        return "Could not run analysis: no code was provided."
    if not datasets:
        return (
            "Could not run analysis: name at least one dataset to load, e.g. "
            '[{"skill_id": "rent_vacancy_trends", "dataset": "prime_rents.csv"}].'
        )

    frames: Dict[str, pd.DataFrame] = {}
    for entry in datasets:
        skill_id = entry.get("skill_id")
        dataset = entry.get("dataset")
        if not skill_id or not dataset:
            return "Could not run analysis: each dataset needs 'skill_id' and 'dataset'."
        skill = sr.get_skill(skill_id)
        if skill is None:
            return f"Could not run analysis: no skill with id '{skill_id}'."
        safe_dataset = Path(dataset).name
        csv_path = skill.path / "data" / safe_dataset
        if not csv_path.exists():
            return (
                f"Could not run analysis: dataset '{dataset}' not found in "
                f"skill '{skill_id}'."
            )
        handle = entry.get("as") or Path(safe_dataset).stem
        try:
            frames[handle] = pd.read_csv(csv_path)
        except Exception as exc:  # noqa: BLE001
            return f"Could not run analysis: error reading '{dataset}': {exc}"

    try:
        result = await asyncio.to_thread(code_sandbox.run, code, frames)
    except Exception as exc:  # noqa: BLE001 — never raise into the stream
        logger.error("run_analysis sandbox call failed: %s", exc)
        return f"Could not run analysis: {exc}"

    return _format_analysis_result(result)
