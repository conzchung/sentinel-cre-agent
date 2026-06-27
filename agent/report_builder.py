# agent/report_builder.py
"""Pure layout/render helpers for Sentinel PDF reports.

No LangChain here — these are deterministic, unit-testable functions:
  chart_spec_to_png  — one chart_spec dict -> static PNG bytes (matplotlib)
  render_report_html — title/sections/charts -> a self-contained HTML string
  build_report_pdf   — title/sections -> PDF bytes (WeasyPrint)

The chart_spec contract is identical to render_chart's, so the agent uses one
chart format for both the interactive chat chart (Plotly) and the static PDF
chart (matplotlib).
"""

from __future__ import annotations

import base64
import io
from typing import Any, Dict, List, Optional

import markdown as _markdown
import matplotlib

matplotlib.use("Agg")  # non-interactive backend — no display in a server process

import matplotlib.pyplot as plt

_CHART_STYLE = "seaborn-v0_8-whitegrid"


def chart_spec_to_png(chart_spec: Dict[str, Any]) -> bytes:
    """Render a chart_spec (line | bar | grouped_bar) to PNG bytes via matplotlib.

    Raises ValueError for an unsupported chart type.
    """
    chart_type = chart_spec.get("type", "line")
    series = chart_spec.get("series", [])

    with plt.style.context(_CHART_STYLE):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        try:
            if chart_type == "line":
                for s in series:
                    ax.plot(s["x"], s["y"], marker="o", label=s.get("name", ""))
            elif chart_type == "bar":
                s = series[0]
                ax.bar(s["x"], s["y"], label=s.get("name", ""))
            elif chart_type == "grouped_bar":
                _grouped_bar(ax, series)
            else:
                raise ValueError(f"Unsupported chart type '{chart_type}'.")

            ax.set_title(chart_spec.get("title", ""))
            ax.set_xlabel(chart_spec.get("x_label", ""))
            ax.set_ylabel(chart_spec.get("y_label", ""))
            if len(series) > 1 or chart_type == "line":
                ax.legend()
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150)
            return buf.getvalue()
        finally:
            plt.close(fig)


def _grouped_bar(ax, series: List[Dict[str, Any]]) -> None:
    """Draw a grouped bar chart: one cluster of bars per x category."""
    import numpy as np

    categories = series[0]["x"] if series else []
    n_series = len(series)
    x = np.arange(len(categories))
    width = 0.8 / max(n_series, 1)
    for i, s in enumerate(series):
        offset = (i - (n_series - 1) / 2) * width
        ax.bar(x + offset, s["y"], width, label=s.get("name", ""))
    ax.set_xticks(x)
    ax.set_xticklabels(categories)


_REPORT_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: "Helvetica Neue", Arial, sans-serif; color: #1a1a1a; font-size: 11pt; line-height: 1.45; }
.cover { border-bottom: 3px solid #1f4e79; padding-bottom: 12px; margin-bottom: 24px; }
.cover h1 { color: #1f4e79; font-size: 22pt; margin: 0; }
.cover .subtitle { color: #555; font-size: 13pt; margin-top: 4px; }
.cover .generated { color: #888; font-size: 9pt; margin-top: 8px; }
h2 { color: #1f4e79; font-size: 14pt; border-bottom: 1px solid #d0d7de; padding-bottom: 4px; margin-top: 22px; }
img.chart { width: 100%; max-width: 640px; display: block; margin: 12px auto; }
.chart-missing { color: #b00; font-style: italic; font-size: 10pt; }
.footer { margin-top: 32px; border-top: 1px solid #d0d7de; padding-top: 8px; color: #888; font-size: 8.5pt; }
ul { margin: 6px 0 6px 18px; }
"""

_FOOTER_TEXT = "ILLUSTRATIVE — market commentary, not investment advice."


def render_report_html(
    title: str,
    subtitle: Optional[str],
    sections: List[Dict[str, Any]],
    *,
    generated_at: str,
) -> str:
    """Assemble a self-contained HTML document (charts inlined as base64)."""
    parts: List[str] = []
    parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    parts.append(f"<style>{_REPORT_CSS}</style></head><body>")

    parts.append("<div class='cover'>")
    parts.append(f"<h1>{_escape(title)}</h1>")
    if subtitle:
        parts.append(f"<div class='subtitle'>{_escape(subtitle)}</div>")
    parts.append(f"<div class='generated'>Generated {_escape(generated_at)} (Asia/Hong_Kong)</div>")
    parts.append("</div>")

    for section in sections:
        heading = section.get("heading", "")
        parts.append(f"<h2>{_escape(heading)}</h2>")
        body_html = _markdown.markdown(
            section.get("body_markdown", ""), extensions=["extra"]
        )
        parts.append(body_html)
        chart_png = section.get("chart_png")
        if chart_png:
            b64 = base64.b64encode(chart_png).decode("ascii")
            parts.append(f"<img class='chart' src='data:image/png;base64,{b64}' />")
        elif section.get("chart_error"):
            parts.append("<p class='chart-missing'>[chart unavailable]</p>")

    parts.append(f"<div class='footer'>{_escape(_FOOTER_TEXT)} Generated {_escape(generated_at)}.</div>")
    parts.append("</body></html>")
    return "".join(parts)


def _escape(text: str) -> str:
    """Minimal HTML escaping for text inserted outside markdown bodies."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_report_pdf(
    title: str,
    subtitle: Optional[str],
    sections: List[Dict[str, Any]],
    *,
    generated_at: str,
) -> bytes:
    """Render charts, assemble HTML, and produce PDF bytes via WeasyPrint.

    Raises ValueError on empty sections. A single chart failure is non-fatal:
    that section renders a '[chart unavailable]' note and the rest still builds.
    """
    if not sections:
        raise ValueError("Cannot build a report with no sections.")

    try:
        from weasyprint import HTML
    except OSError as exc:  # native libs (pango/cairo) missing
        raise RuntimeError(
            "WeasyPrint native libraries are missing. On macOS run "
            "`brew install pango`. Original error: " + str(exc)
        ) from exc

    html_sections: List[Dict[str, Any]] = []
    for section in sections:
        rendered = {
            "heading": section.get("heading", ""),
            "body_markdown": section.get("body_markdown", ""),
            "chart_png": None,
            "chart_error": False,
        }
        spec = section.get("chart_spec")
        if spec:
            try:
                rendered["chart_png"] = chart_spec_to_png(spec)
            except Exception:  # noqa: BLE001 — one bad chart must not sink the report
                rendered["chart_error"] = True
        html_sections.append(rendered)

    html = render_report_html(
        title, subtitle, html_sections, generated_at=generated_at
    )
    return HTML(string=html).write_pdf()
