"""Jina embeddings client for Sentinel RAG.

Wraps the Jina REST embeddings endpoint. Used by both the ingestion CLI
(batch, one shared session) and the knowledge_search tool (single call).
"""

from __future__ import annotations

import asyncio
import os
from typing import List, Optional

import aiohttp

_JINA_URL = "https://api.jina.ai/v1/embeddings"
_MODEL = "jina-embeddings-v5-text-small"

_EMBED_SEMAPHORE: Optional[asyncio.Semaphore] = None


def _get_embed_semaphore() -> asyncio.Semaphore:
    """Bound concurrent Jina calls (lazily created on the running loop)."""
    global _EMBED_SEMAPHORE
    if _EMBED_SEMAPHORE is None:
        _EMBED_SEMAPHORE = asyncio.Semaphore(8)
    return _EMBED_SEMAPHORE


async def embed_text(text: str, session: Optional[aiohttp.ClientSession] = None) -> List[float]:
    """Return the Jina embedding vector for `text`.

    Pass an existing `session` in batch loops to amortize TLS/handshake cost.
    If `session` is None, opens a fresh one for this single call.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('JINA_API_KEY')}",
    }
    payload = {
        "model": _MODEL,
        "task": "text-matching",
        "normalized": True,
        "input": [{"text": text}],
    }

    async def _post(s) -> List[float]:
        async with _get_embed_semaphore():
            async with s.post(_JINA_URL, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
                try:
                    return data["data"][0]["embedding"]
                except (KeyError, IndexError, TypeError) as e:
                    raise RuntimeError(f"Unexpected Jina response shape: {data!r}") from e

    if session is None:
        async with aiohttp.ClientSession() as s:
            return await _post(s)
    return await _post(session)


async def embed_texts(
    texts: List[str], session: Optional[aiohttp.ClientSession] = None
) -> List[List[float]]:
    """Embed many texts, reusing ONE session across the batch."""
    if session is None:
        async with aiohttp.ClientSession() as s:
            return await asyncio.gather(*[embed_text(t, s) for t in texts])
    return await asyncio.gather(*[embed_text(t, session) for t in texts])
