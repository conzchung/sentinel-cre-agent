import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import plotly.io as pio

import market_agent_tools as t


def _spec(chart_type="line"):
    return {
        "type": chart_type,
        "title": "Prime City Rent",
        "x_label": "Quarter",
        "y_label": "£/sq ft",
        "series": [
            {"name": "City", "x": ["2025Q1", "2025Q2"], "y": [80.0, 82.5]},
            {"name": "West End", "x": ["2025Q1", "2025Q2"], "y": [115.0, 117.0]},
        ],
    }


def test_build_figure_line_has_one_scatter_per_series():
    fig = t._build_figure(_spec("line"))
    assert len(fig.data) == 2
    assert all(trace.type == "scatter" for trace in fig.data)


def test_build_figure_grouped_bar_is_grouped():
    fig = t._build_figure(_spec("grouped_bar"))
    assert len(fig.data) == 2
    assert all(trace.type == "bar" for trace in fig.data)
    assert fig.layout.barmode == "group"


def test_build_figure_bar_uses_first_series_only():
    fig = t._build_figure(_spec("bar"))
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"


def test_build_figure_unsupported_type_raises():
    import pytest
    with pytest.raises(ValueError):
        t._build_figure(_spec("pie"))


class _Collector:
    def __init__(self):
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(payload)


async def test_render_chart_emits_to_side_channel_and_returns_string(monkeypatch):
    collector = _Collector()
    monkeypatch.setattr(t, "get_stream_writer", lambda: collector)

    out = await t.render_chart.ainvoke(
        {"objective": "trend", "chart_spec": _spec("line")}
    )

    assert isinstance(out, str)
    assert out.startswith("Chart ")
    assert "rendered: Prime City Rent" in out

    assert len(collector.payloads) == 1
    chart = collector.payloads[0]["chart"]
    assert chart["title"] == "Prime City Rent"
    assert chart["id"] in out
    # figure_json round-trips back to a real figure
    fig = pio.from_json(chart["figure_json"])
    assert len(fig.data) == 2


async def test_render_chart_empty_series_emits_nothing(monkeypatch):
    collector = _Collector()
    monkeypatch.setattr(t, "get_stream_writer", lambda: collector)
    spec = _spec("line")
    spec["series"] = []
    out = await t.render_chart.ainvoke({"objective": "x", "chart_spec": spec})
    assert out.startswith("Could not render chart")
    assert collector.payloads == []


async def test_render_chart_survives_missing_side_channel(monkeypatch):
    def boom():
        raise RuntimeError("Called get_config outside of a runnable context")
    monkeypatch.setattr(t, "get_stream_writer", boom)
    out = await t.render_chart.ainvoke(
        {"objective": "x", "chart_spec": _spec("line")}
    )
    # Still returns the confirmation string; does not raise.
    assert out.startswith("Chart ")
