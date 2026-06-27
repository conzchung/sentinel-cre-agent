"""Shared async Cosmos DB client and backend constants."""

import os
import pytz
from azure.cosmos.aio import CosmosClient
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# ─────────────────────── Constants ───────────────────────

hong_kong_tz = pytz.timezone("Asia/Hong_Kong")

DATABASE_NAME = "agentMemory"

# Sentinel (market agent) containers — same agentMemory database.
SENTINEL_CONVO_CONTAINER_NAME = "sentinelConvo"        # user-facing dialog
SENTINEL_CHECKPOINT_CONTAINER_NAME = "sentinelChatbot"  # CosmosDBSaver state

# ─────────────────────── Cosmos client ───────────────────

AGENT_COSMOS_URL = os.getenv("AGENT_COSMOS_URL")
AGENT_COSMOS_KEY = os.getenv("AGENT_COSMOS_KEY")

# bridge naming for langgraph_checkpoint_cosmosdb, which reads COSMOSDB_ENDPOINT/COSMOSDB_KEY
os.environ.setdefault("COSMOSDB_ENDPOINT", AGENT_COSMOS_URL or "")
os.environ.setdefault("COSMOSDB_KEY", AGENT_COSMOS_KEY or "")

cosmos_client: CosmosClient = CosmosClient(
    AGENT_COSMOS_URL, credential=AGENT_COSMOS_KEY
)

database = cosmos_client.get_database_client(DATABASE_NAME)

sentinel_convo_container = database.get_container_client(SENTINEL_CONVO_CONTAINER_NAME)
