import pytest

import rag_embeddings


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResp(self._payload)


async def test_embed_text_parses_embedding_and_builds_payload():
    session = _FakeSession({"data": [{"embedding": [0.1, 0.2, 0.3]}]})
    vec = await rag_embeddings.embed_text("hello", session=session)
    assert vec == [0.1, 0.2, 0.3]
    sent = session.calls[0]["json"]
    assert sent["model"] == "jina-embeddings-v5-text-small"
    assert sent["task"] == "text-matching"
    assert sent["normalized"] is True
    assert sent["input"] == [{"text": "hello"}]


async def test_embed_text_raises_on_bad_shape():
    session = _FakeSession({"unexpected": True})
    with pytest.raises(RuntimeError):
        await rag_embeddings.embed_text("hello", session=session)


async def test_embed_texts_returns_one_vector_per_input():
    session = _FakeSession({"data": [{"embedding": [1.0, 2.0]}]})
    vecs = await rag_embeddings.embed_texts(["a", "b", "c"], session=session)
    assert vecs == [[1.0, 2.0], [1.0, 2.0], [1.0, 2.0]]
