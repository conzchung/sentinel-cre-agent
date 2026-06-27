"""One-shot setup for the Sentinel app: ensure the conversation container exists.

The single demo account is configured in the frontend session layer
(frontend/lib/session.ts) via AUTH_USERNAME / AUTH_PASSWORD, so there is no
account store to seed. Conversations live in db.py's Cosmos namespace
(agentMemory). CosmosDBSaver creates its own `sentinelChatbot` checkpoint
container on first use, so this script only needs to create `sentinelConvo`.

Usage:
    python scripts/bootstrap_sentinel.py
"""

import asyncio
import os
import sys


def container_spec():
    """Return (container_name, partition_key_path) for the dialog container.
    Pure — lazy-imports db only when needed so unit tests stay offline."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
    import db
    return db.SENTINEL_CONVO_CONTAINER_NAME, "/thread_id"


async def ensure_containers():
    """Create the sentinelConvo container if it does not yet exist."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
    from azure.cosmos import PartitionKey
    import db
    name, partition_path = container_spec()
    await db.database.create_container_if_not_exists(
        id=name,
        partition_key=PartitionKey(path=partition_path),
    )


def main():
    print("Ensuring sentinelConvo container exists ...")
    asyncio.run(ensure_containers())
    print("Bootstrap complete. Log in to the Sentinel app with the demo account.")


if __name__ == "__main__":
    main()
