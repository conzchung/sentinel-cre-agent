# tests/test_report_builder.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pytest

import report_builder as rb


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


def test_chart_spec_to_png_line_returns_png_bytes():
    out = rb.chart_spec_to_png(_spec("line"))
    assert isinstance(out, bytes)
    assert out.startswith(b"\x89PNG")
    assert len(out) > 1000  # a real image, not an empty buffer


def test_chart_spec_to_png_bar_returns_png_bytes():
    out = rb.chart_spec_to_png(_spec("bar"))
    assert out.startswith(b"\x89PNG")


def test_chart_spec_to_png_grouped_bar_returns_png_bytes():
    out = rb.chart_spec_to_png(_spec("grouped_bar"))
    assert out.startswith(b"\x89PNG")


def test_chart_spec_to_png_unsupported_type_raises():
    with pytest.raises(ValueError):
        rb.chart_spec_to_png(_spec("pie"))


def _sections_for_html():
    return [
        {
            "heading": "Prime Rents",
            "body_markdown": "City rents rose.\n\n- City: £82.5\n- West End: £117",
            "chart_png": b"\x89PNG\r\n\x1a\n" + b"0" * 50,  # fake but non-empty
        },
        {
            "heading": "Vacancy",
            "body_markdown": "Vacancy **stable**.",
            "chart_png": None,
        },
    ]


def test_render_report_html_includes_title_and_sections():
    html = rb.render_report_html(
        "London Office Briefing",
        "Q2 2025 snapshot",
        _sections_for_html(),
        generated_at="2026/06/27 10:00:00",
    )
    assert "London Office Briefing" in html
    assert "Q2 2025 snapshot" in html
    assert "Prime Rents" in html
    assert "Vacancy" in html
    # markdown converted: bullet list and bold became HTML tags
    assert "<li>" in html
    assert "<strong>stable</strong>" in html


def test_render_report_html_embeds_chart_as_base64_img():
    html = rb.render_report_html(
        "T", None, _sections_for_html(), generated_at="2026/06/27 10:00:00"
    )
    assert "data:image/png;base64," in html


def test_render_report_html_has_illustrative_footer_and_timestamp():
    html = rb.render_report_html(
        "T", None, _sections_for_html(), generated_at="2026/06/27 10:00:00"
    )
    assert "ILLUSTRATIVE" in html
    assert "not investment advice" in html
    assert "2026/06/27 10:00:00" in html


def test_render_report_html_shows_chart_unavailable_note():
    sections = [
        {"heading": "Broken", "body_markdown": "x", "chart_png": None, "chart_error": True}
    ]
    html = rb.render_report_html("T", None, sections, generated_at="t")
    assert "[chart unavailable]" in html


def _sections_for_pdf():
    return [
        {
            "heading": "Prime Rents",
            "body_markdown": "City rents rose to £82.5.",
            "chart_spec": _spec("line"),
        },
        {
            "heading": "Outlook",
            "body_markdown": "Stable demand expected.",
            "chart_spec": None,
        },
    ]


def test_build_report_pdf_returns_pdf_bytes():
    out = rb.build_report_pdf(
        "London Office Briefing",
        "Q2 2025",
        _sections_for_pdf(),
        generated_at="2026/06/27 10:00:00",
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    assert len(out) > 1000


def test_build_report_pdf_empty_sections_raises():
    with pytest.raises(ValueError):
        rb.build_report_pdf("T", None, [], generated_at="t")


def test_build_report_pdf_bad_chart_is_non_fatal(monkeypatch):
    def boom(spec):
        raise RuntimeError("chart engine exploded")

    monkeypatch.setattr(rb, "chart_spec_to_png", boom)
    out = rb.build_report_pdf(
        "T", None, _sections_for_pdf(), generated_at="t"
    )
    # Report still builds despite the chart failure.
    assert out.startswith(b"%PDF")
