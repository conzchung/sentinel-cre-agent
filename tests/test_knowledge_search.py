import pytest

import market_agent_tools as t
import rag_embeddings
import rag_store


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    async def fake_embed_text(query, session=None):
        return [0.1, 0.2, 0.3]
    monkeypatch.setattr(rag_embeddings, "embed_text", fake_embed_text)


async def test_knowledge_search_formats_like_web_search(monkeypatch):
    async def fake_search(vector, top_k=4):
        return [
            {"payload": {"text": "Flight to quality is strong.", "source": "Illustrative analyst commentary", "as_of": "2025Q2"}, "score": 0.9},
            {"payload": {"text": "ESG pressure is rising.", "source": "Illustrative analyst commentary", "as_of": "2025Q1"}, "score": 0.8},
        ]
    monkeypatch.setattr(rag_store, "search", fake_search)

    out = await t.knowledge_search.ainvoke(
        {"objective": "find qualitative drivers", "query": "flight to quality"}
    )
    assert "Flight to quality is strong.[1]" in out["content"]
    assert "ESG pressure is rising.[2]" in out["content"]
    assert "=====" in out["content"]
    assert out["citations"] == [
        {"1": "Illustrative analyst commentary, 2025Q2"},
        {"2": "Illustrative analyst commentary, 2025Q1"},
    ]


async def test_knowledge_search_empty_results_is_graceful(monkeypatch):
    async def fake_search(vector, top_k=4):
        return []
    monkeypatch.setattr(rag_store, "search", fake_search)
    out = await t.knowledge_search.ainvoke({"objective": "x", "query": "nothing"})
    assert out == {"content": "No matching research notes found.", "citations": []}


async def test_knowledge_search_swallows_errors(monkeypatch):
    async def boom(vector, top_k=4):
        raise RuntimeError("qdrant down")
    monkeypatch.setattr(rag_store, "search", boom)
    out = await t.knowledge_search.ainvoke({"objective": "x", "query": "q"})
    assert out == {"content": "No matching research notes found.", "citations": []}


async def test_knowledge_search_swallows_embed_errors(monkeypatch):
    async def embed_boom(query, session=None):
        raise RuntimeError("jina 401")
    monkeypatch.setattr(rag_embeddings, "embed_text", embed_boom)
    out = await t.knowledge_search.ainvoke({"objective": "x", "query": "q"})
    assert out == {"content": "No matching research notes found.", "citations": []}
