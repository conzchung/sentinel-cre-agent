"""One-off ingestion: embed the research corpus and upsert it into Qdrant.

Idempotent — recreates the collection each run, so re-running yields the same
end state. Run: python scripts/ingest_research_corpus.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import find_dotenv, load_dotenv

# Make agent/ modules importable (same convention as main.py).
_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "agent"))

load_dotenv(find_dotenv(), override=True)

import rag_corpus
import rag_embeddings
import rag_store


async def main() -> None:
    notes = rag_corpus.load_corpus()
    print(f"Loaded {len(notes)} notes; embedding via Jina...")
    vectors = await rag_embeddings.embed_texts([n["text"] for n in notes])
    vector_size = len(vectors[0])
    print(f"Embedded; vector dim = {vector_size}. Recreating collection...")
    await rag_store.ensure_collection(vector_size, recreate=True)
    await rag_store.upsert_notes(notes, vectors)
    print(
        f"Upserted {len(notes)} notes into "
        f"'{rag_store.COLLECTION_NAME}' (dim={vector_size})."
    )


if __name__ == "__main__":
    asyncio.run(main())
