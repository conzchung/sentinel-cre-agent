# tests/test_generate_report_tool.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import market_agent_tools as t


class _FakeBlobClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _sections():
    return [
        {
            "heading": "Prime Rents",
            "body_markdown": "City rents rose.",
            "chart_spec": {
                "type": "line",
                "title": "Rent",
                "x_label": "Q",
                "y_label": "£",
                "series": [{"name": "City", "x": ["2025Q1", "2025Q2"], "y": [80, 82]}],
            },
        }
    ]


async def test_generate_report_returns_ready_string(monkeypatch):
    captured = {}

    async def fake_upload(container_name, blob_name, data, blob_service_client, **kwargs):
        captured["container"] = container_name
        captured["blob_name"] = blob_name
        captured["data_head"] = data[:4]
        return "https://blob.example/" + blob_name + "?sig=fake"

    # Avoid building a real Azure client and a real PDF engine.
    monkeypatch.setattr(t, "_blob_service_client", lambda: _FakeBlobClient())
    monkeypatch.setattr(t, "upload_blob_and_get_url", fake_upload)
    monkeypatch.setattr(
        t, "build_report_pdf", lambda *a, **k: b"%PDF-1.7 fake bytes"
    )

    out = await t.generate_report.ainvoke(
        {
            "objective": "user asked for a PDF",
            "title": "London Office Briefing",
            "sections": _sections(),
            "subtitle": "Q2 2025",
            "config": {"configurable": {"thread_id": "th1", "user_id": "demo-user"}},
        }
    )

    assert isinstance(out, str)
    assert out.startswith("Report ready:")
    assert "https://blob.example/" in out
    assert captured["container"] == "aiagentdocs"
    assert captured["blob_name"].startswith("sentinel_reports/")
    assert captured["blob_name"].endswith(".pdf")
    assert captured["data_head"] == b"%PDF"


async def test_generate_report_empty_sections_returns_friendly_string(monkeypatch):
    monkeypatch.setattr(t, "_blob_service_client", lambda: _FakeBlobClient())
    out = await t.generate_report.ainvoke(
        {
            "objective": "x",
            "title": "Empty",
            "sections": [],
            "config": {"configurable": {"thread_id": "th1", "user_id": "demo-user"}},
        }
    )
    assert "no sections" in out.lower() or "nothing to report" in out.lower()


async def test_generate_report_upload_failure_returns_error_string(monkeypatch):
    async def boom_upload(*a, **k):
        raise RuntimeError("blob down")

    monkeypatch.setattr(t, "_blob_service_client", lambda: _FakeBlobClient())
    monkeypatch.setattr(t, "upload_blob_and_get_url", boom_upload)
    monkeypatch.setattr(t, "build_report_pdf", lambda *a, **k: b"%PDF fake")

    out = await t.generate_report.ainvoke(
        {
            "objective": "x",
            "title": "T",
            "sections": _sections(),
            "config": {"configurable": {"thread_id": "th1", "user_id": "demo-user"}},
        }
    )
    assert out.lower().startswith("could not generate report")
