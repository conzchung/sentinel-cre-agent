import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pytest
import market_agent_tools as t


async def test_list_skills_returns_catalog():
    out = await t.list_skills.ainvoke({"objective": "see what I can do"})
    assert "rent_vacancy_trends" in out
    assert "market_news" in out


async def test_read_skill_returns_body():
    out = await t.read_skill.ainvoke(
        {"objective": "load rent skill", "skill_id": "rent_vacancy_trends"}
    )
    assert "## How to analyze" in out


async def test_read_skill_file_returns_csv():
    out = await t.read_skill_file.ainvoke(
        {
            "objective": "inspect raw data",
            "skill_id": "rent_vacancy_trends",
            "filename": "prime_rents.csv",
        }
    )
    assert "prime_rent_psf" in out


async def test_read_skill_unknown_id_is_graceful():
    out = await t.read_skill.ainvoke(
        {"objective": "oops", "skill_id": "nope"}
    )
    assert "Error" in out


async def test_query_dataset_filters_by_submarket():
    out = await t.query_dataset.ainvoke(
        {
            "objective": "City rents",
            "skill_id": "rent_vacancy_trends",
            "dataset": "prime_rents.csv",
            "filters": {"submarket": "City"},
        }
    )
    assert "City" in out
    assert "West End" not in out
    assert "82.5" in out  # 2025Q2 City prime rent


async def test_query_dataset_no_filter_returns_all():
    out = await t.query_dataset.ainvoke(
        {
            "objective": "all vacancy",
            "skill_id": "rent_vacancy_trends",
            "dataset": "vacancy.csv",
            "filters": None,
        }
    )
    assert "City" in out and "West End" in out and "Canary Wharf" in out


async def test_query_dataset_unknown_dataset_graceful():
    out = await t.query_dataset.ainvoke(
        {
            "objective": "bad",
            "skill_id": "rent_vacancy_trends",
            "dataset": "nope.csv",
            "filters": None,
        }
    )
    assert "Error" in out


async def test_create_plan_returns_confirmation():
    steps = [
        {"content": "Load rent_vacancy_trends skill", "status": "in_progress", "remarks": None},
        {"content": "Compare City vs West End", "status": "pending", "remarks": None},
    ]
    out = await t.create_plan.ainvoke({"objective": "multi-step briefing", "steps": steps})
    assert "2" in out  # mentions step count
    assert "plan" in out.lower()


def test_generate_report_is_registered_in_tools():
    import market_agent as ma
    tool_names = {t.name for t in ma.TOOLS}
    assert "generate_report" in tool_names
