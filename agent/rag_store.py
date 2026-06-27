"""Async Qdrant wrapper for the Sentinel research corpus."""

from __future__ import annotations

import os
import uuid
from typing import List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

COLLECTION_NAME = "sentinel_research"
_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "sentinel_research")

_client: Optional[AsyncQdrantClient] = None


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
    return _client


def _point_id(note_id: str) -> str:
    """Deterministic UUID for a note id (Qdrant needs int or UUID ids)."""
    return str(uuid.uuid5(_NAMESPACE, note_id))


async def ensure_collection(vector_size: int, recreate: bool = False) -> None:
    """Create the collection if absent. If recreate, drop and recreate it."""
    client = _get_client()
    exists = await client.collection_exists(COLLECTION_NAME)
    if exists and recreate:
        await client.delete_collection(COLLECTION_NAME)
        exists = False
    if not exists:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


async def upsert_notes(notes: List[dict], vectors: List[List[float]]) -> None:
    """Upsert one Qdrant point per note (payload = the full note dict)."""
    client = _get_client()
    points = [
        PointStruct(id=_point_id(note["id"]), vector=vector, payload=note)
        for note, vector in zip(notes, vectors)
    ]
    await client.upsert(collection_name=COLLECTION_NAME, points=points)


async def search(query_vector: List[float], top_k: int = 4) -> List[dict]:
    """Top-k cosine search; returns [{'payload': dict, 'score': float}, ...]."""
    client = _get_client()
    response = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    return [{"payload": p.payload, "score": p.score} for p in response.points]
