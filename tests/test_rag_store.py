import uuid

import pytest

import rag_store


class _FakeHit:
    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


class _FakeQueryResponse:
    def __init__(self, points):
        self.points = points


class _FakeClient:
    def __init__(self):
        self.upserted = None
        self.created = None
        self.deleted = False
        self._exists = False

    async def collection_exists(self, name):
        return self._exists

    async def create_collection(self, collection_name, vectors_config):
        self.created = {"name": collection_name, "config": vectors_config}
        self._exists = True

    async def delete_collection(self, collection_name):
        self.deleted = True
        self._exists = False

    async def upsert(self, collection_name, points):
        self.upserted = {"name": collection_name, "points": points}

    async def query_points(self, collection_name, query, limit, with_payload):
        points = [
            _FakeHit({"text": "note a", "source": "S", "as_of": "2025Q2"}, 0.9),
            _FakeHit({"text": "note b", "source": "S", "as_of": "2025Q1"}, 0.8),
        ][:limit]
        return _FakeQueryResponse(points)


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(rag_store, "_get_client", lambda: client)
    return client


def test_point_id_is_deterministic_uuid():
    a = rag_store._point_id("note-001")
    b = rag_store._point_id("note-001")
    assert a == b
    uuid.UUID(a)  # parses as a valid UUID


async def test_ensure_collection_creates_when_absent(fake_client):
    await rag_store.ensure_collection(3)
    assert fake_client.created["name"] == rag_store.COLLECTION_NAME
    assert fake_client.created["config"].size == 3


async def test_ensure_collection_recreate_deletes_first(fake_client):
    fake_client._exists = True
    await rag_store.ensure_collection(5, recreate=True)
    assert fake_client.deleted is True
    assert fake_client.created["config"].size == 5


async def test_upsert_notes_builds_points_with_uuid_ids(fake_client):
    notes = [{"id": "note-001", "text": "x"}]
    await rag_store.upsert_notes(notes, [[0.1, 0.2]])
    pts = fake_client.upserted["points"]
    assert len(pts) == 1
    assert pts[0].id == rag_store._point_id("note-001")
    assert pts[0].payload["id"] == "note-001"


async def test_search_maps_payload_and_score(fake_client):
    hits = await rag_store.search([0.1, 0.2], top_k=2)
    assert hits[0] == {"payload": {"text": "note a", "source": "S", "as_of": "2025Q2"}, "score": 0.9}
    assert len(hits) == 2
