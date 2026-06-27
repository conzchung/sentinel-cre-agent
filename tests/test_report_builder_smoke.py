# tests/test_report_builder_smoke.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pytest

import report_builder as rb


def _has_weasyprint():
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_weasyprint(), reason="WeasyPrint native libs not available")
def test_real_pdf_round_trip_with_chart():
    sections = [
        {
            "heading": "Prime Rents",
            "body_markdown": "City prime rents rose to **£82.5/sq ft** in 2025Q2.\n\n"
                             "- City: £82.5\n- West End: £117.0",
            "chart_spec": {
                "type": "line",
                "title": "Prime rent trend",
                "x_label": "Quarter",
                "y_label": "£/sq ft",
                "series": [
                    {"name": "City", "x": ["2025Q1", "2025Q2"], "y": [80.0, 82.5]},
                    {"name": "West End", "x": ["2025Q1", "2025Q2"], "y": [115.0, 117.0]},
                ],
            },
        },
        {
            "heading": "Vacancy",
            "body_markdown": "Vacancy held broadly stable.",
            "chart_spec": {
                "type": "bar",
                "title": "Vacancy by submarket",
                "x_label": "Submarket",
                "y_label": "%",
                "series": [{"name": "Vacancy", "x": ["City", "West End"], "y": [8.2, 5.1]}],
            },
        },
    ]
    pdf = rb.build_report_pdf(
        "London Office Market Briefing",
        "Q2 2025 — ILLUSTRATIVE",
        sections,
        generated_at="2026/06/27 10:00:00",
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000  # a real multi-section PDF with two charts
