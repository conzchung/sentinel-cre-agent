import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import market_agent_tools as t


async def test_dataframe_result_renders_table():
    code = (
        "result = datasets['prime_rents'].groupby('submarket')"
        "['prime_rent_psf'].mean().round(1).reset_index()"
    )
    out = await t.run_analysis.ainvoke(
        {
            "objective": "mean prime rent by submarket",
            "code": code,
            "datasets": [
                {"skill_id": "rent_vacancy_trends", "dataset": "prime_rents.csv"}
            ],
        }
    )
    assert "submarket" in out
    assert "City" in out


async def test_scalar_result_renders_inline():
    out = await t.run_analysis.ainvoke(
        {
            "objective": "row count",
            "code": "result = int(len(datasets['vacancy']))",
            "datasets": [{"skill_id": "rent_vacancy_trends", "dataset": "vacancy.csv"}],
        }
    )
    assert "Result:" in out


async def test_custom_handle_via_as():
    out = await t.run_analysis.ainvoke(
        {
            "objective": "use a custom handle",
            "code": "result = int(datasets['v']['vacancy_rate_pct'].count())",
            "datasets": [
                {"skill_id": "rent_vacancy_trends", "dataset": "vacancy.csv", "as": "v"}
            ],
        }
    )
    assert "Result:" in out


async def test_unknown_skill_is_graceful():
    out = await t.run_analysis.ainvoke(
        {
            "objective": "bad skill",
            "code": "result = 1",
            "datasets": [{"skill_id": "nope", "dataset": "x.csv"}],
        }
    )
    assert "Could not run analysis" in out
    assert "nope" in out


async def test_unknown_dataset_is_graceful():
    out = await t.run_analysis.ainvoke(
        {
            "objective": "bad dataset",
            "code": "result = 1",
            "datasets": [{"skill_id": "rent_vacancy_trends", "dataset": "missing.csv"}],
        }
    )
    assert "Could not run analysis" in out


async def test_empty_datasets_is_graceful():
    out = await t.run_analysis.ainvoke(
        {"objective": "no data", "code": "result = 1", "datasets": []}
    )
    assert "Could not run analysis" in out


async def test_no_result_message():
    out = await t.run_analysis.ainvoke(
        {
            "objective": "forgot result",
            "code": "x = 1",
            "datasets": [{"skill_id": "rent_vacancy_trends", "dataset": "vacancy.csv"}],
        }
    )
    assert "did not assign" in out
