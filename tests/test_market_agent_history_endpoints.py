import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import FastAPI
from fastapi.testclient import TestClient

import market_agent_api as api


class _FakeAsyncIter:
    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        async def gen():
            for it in self._items:
                yield it
        return gen()


class _FakeContainer:
    def __init__(self, docs=None, summaries=None):
        self._docs = docs or {}
        self._summaries = summaries or []

    def query_items(self, query=None, parameters=None):
        return _FakeAsyncIter(self._summaries)

    async def read_item(self, item, partition_key):
        if item in self._docs:
            return self._docs[item]
        raise CosmosResourceNotFoundError(message="not found")

    async def delete_item(self, item, partition_key):
        if item in self._docs:
            del self._docs[item]
            return
        raise CosmosResourceNotFoundError(message="not found")


def _client(container, monkeypatch):
    monkeypatch.setattr(api, "sentinel_convo_container", container)
    app = FastAPI()
    app.include_router(api.market_agent_router, prefix="/market_agent")
    app.dependency_overrides[api.get_api_key] = lambda: "test"
    return TestClient(app)


def test_list_returns_summaries(monkeypatch):
    container = _FakeContainer(summaries=[
        {"thread_id": "a", "convo_title": "City rents", "updated_at": "2026/06/26 10:00:00"},
        {"thread_id": "b", "convo_title": None, "updated_at": None},
    ])
    client = _client(container, monkeypatch)
    resp = client.get("/market_agent/user-thread-ids/alice")
    assert resp.status_code == 200
    data = resp.json()
    assert [c["thread_id"] for c in data] == ["a", "b"]
    assert data[0]["convo_title"] == "City rents"


def test_fetch_strips_meta_and_404s(monkeypatch):
    container = _FakeContainer(docs={"a": {
        "id": "a", "thread_id": "a", "_rid": "xyz", "convo_title": "T",
        "dialog": [{"role": "user", "content": "hi"}],
    }})
    client = _client(container, monkeypatch)

    ok = client.get("/market_agent/fetch-dialog/a")
    assert ok.status_code == 200
    body = ok.json()
    assert "id" not in body and "_rid" not in body
    assert body["dialog"][0]["content"] == "hi"

    missing = client.get("/market_agent/fetch-dialog/nope")
    assert missing.status_code == 404


def test_delete_returns_status_and_404s(monkeypatch):
    container = _FakeContainer(docs={"a": {"id": "a", "thread_id": "a"}})
    client = _client(container, monkeypatch)

    ok = client.delete("/market_agent/delete-dialog/a")
    assert ok.status_code == 200
    assert ok.json() == {"status": "deleted", "thread_id": "a"}

    missing = client.delete("/market_agent/delete-dialog/a")
    assert missing.status_code == 404
