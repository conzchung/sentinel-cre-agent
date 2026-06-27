import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import skills_registry as sr

REPO = Path(__file__).resolve().parent.parent


def test_discover_finds_all_four_skills():
    skills = sr.discover_skills()
    ids = {s.id for s in skills}
    assert ids == {"rent_vacancy_trends", "supply_pipeline", "macro_demand", "market_news"}


def test_skillmeta_fields_parsed():
    skills = {s.id: s for s in sr.discover_skills()}
    rv = skills["rent_vacancy_trends"]
    assert rv.name == "Rent & Vacancy Trends"
    assert "prime" in rv.when_to_use.lower()
    assert "prime_rents.csv" in rv.datasets


def test_build_catalog_lists_skills():
    catalog = sr.build_catalog(sr.discover_skills())
    assert "rent_vacancy_trends" in catalog
    assert "market_news" in catalog
    assert "Rent & Vacancy Trends" in catalog


def test_read_skill_body_excludes_frontmatter():
    body = sr.read_skill_body("rent_vacancy_trends")
    assert "## How to analyze" in body
    assert "id: rent_vacancy_trends" not in body  # frontmatter stripped


def test_read_skill_data_file_returns_csv_text():
    text = sr.read_skill_data_file("rent_vacancy_trends", "prime_rents.csv")
    assert "prime_rent_psf" in text
    assert "City" in text


def test_get_skill_unknown_returns_none():
    assert sr.get_skill("does_not_exist") is None
