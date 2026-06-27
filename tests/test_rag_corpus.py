import json
from pathlib import Path

import pytest

import rag_corpus


def test_required_fields_constant():
    assert rag_corpus.REQUIRED_FIELDS == (
        "id", "title", "text", "source", "as_of", "theme",
    )


def test_load_corpus_returns_all_notes_with_required_fields():
    notes = rag_corpus.load_corpus()
    assert len(notes) >= 24
    for note in notes:
        for field in rag_corpus.REQUIRED_FIELDS:
            assert field in note, f"{note.get('id')} missing {field}"
        assert note["text"].strip(), f"{note['id']} has empty text"


def test_load_corpus_ids_are_unique():
    notes = rag_corpus.load_corpus()
    ids = [n["id"] for n in notes]
    assert len(ids) == len(set(ids))


def test_load_corpus_raises_on_missing_field(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"id": "x", "title": "t"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rag_corpus.load_corpus(bad)


def test_load_corpus_raises_on_empty_text(tmp_path):
    bad = tmp_path / "empty_text.jsonl"
    note = {
        "id": "x", "title": "t", "text": "   ",
        "source": "s", "as_of": "2025Q2", "theme": "macro",
    }
    bad.write_text(json.dumps(note) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rag_corpus.load_corpus(bad)
