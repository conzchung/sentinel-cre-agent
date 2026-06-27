"""FastAPI router for the Sentinel market agent (streaming)."""

import hmac
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from db import sentinel_convo_container
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from market_agent import run_agent

logger = logging.getLogger(__name__)

market_agent_router = APIRouter()

AGENT_API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str = Depends(api_key_header)):
    if api_key and AGENT_API_KEY and hmac.compare_digest(api_key, AGENT_API_KEY):
        return api_key
    raise HTTPException(status_code=403, detail="Could not validate API Key")


class ExecutionRequest(BaseModel):
    message: str
    thread_id: str
    user_id: Optional[str] = None


@market_agent_router.get("/health", tags=["Sentinel"])
async def health():
    return {"status": "ok"}


@market_agent_router.post("/execution-agent-stream", tags=["Sentinel"])
async def execution_agent_stream(req: ExecutionRequest, api_key: str = Depends(get_api_key)):
    async def event_generator():
        try:
            async for chunk in run_agent(
                message=req.message, thread_id=req.thread_id, user_id=req.user_id
            ):
                yield chunk["ai_response"]
        except Exception as exc:  # noqa: BLE001
            logger.error("stream error: %s", exc, exc_info=True)
            yield "An unexpected error occurred. Please try again later."

    return StreamingResponse(event_generator(), media_type="text/plain")


def strip_cosmos_meta(doc: dict) -> dict:
    """Drop CosmosDB system properties and the internal id from a document."""
    if not doc:
        return doc
    return {k: v for k, v in doc.items() if not k.startswith("_") and k != "id"}


class ConversationSummary(BaseModel):
    thread_id: str
    convo_title: Optional[str] = None
    updated_at: Optional[str] = None


@market_agent_router.get(
    "/user-thread-ids/{user_id}",
    response_model=List[ConversationSummary],
    tags=["Sentinel"],
)
async def get_user_thread_ids(user_id: str, api_key: str = Depends(get_api_key)):
    """All conversation summaries for a user, most-recent first."""
    query = (
        "SELECT c.thread_id, c.convo_title, c.updated_at "
        "FROM c WHERE c.user_id = @user_id ORDER BY c.updated_at DESC"
    )
    parameters = [{"name": "@user_id", "value": user_id}]
    try:
        items_iter = sentinel_convo_container.query_items(query=query, parameters=parameters)
        conversations: List[ConversationSummary] = []
        async for item in items_iter:
            tid = item.get("thread_id")
            if not tid:
                continue
            conversations.append(
                ConversationSummary(
                    thread_id=tid,
                    convo_title=item.get("convo_title"),
                    updated_at=item.get("updated_at"),
                )
            )
        return conversations
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching thread ids: {exc}",
        )


@market_agent_router.get("/fetch-dialog/{thread_id}", tags=["Sentinel"])
async def fetch_dialog(thread_id: str, api_key: str = Depends(get_api_key)):
    """Full dialog document for a thread (Cosmos meta stripped)."""
    try:
        doc = await sentinel_convo_container.read_item(item=thread_id, partition_key=thread_id)
        return strip_cosmos_meta(doc)
    except CosmosResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No dialog found for thread_id: {thread_id}",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dialog: {exc}",
        )


@market_agent_router.delete("/delete-dialog/{thread_id}", tags=["Sentinel"])
async def delete_dialog(thread_id: str, api_key: str = Depends(get_api_key)):
    """Permanently delete a conversation document by thread_id."""
    try:
        await sentinel_convo_container.delete_item(item=thread_id, partition_key=thread_id)
        return {"status": "deleted", "thread_id": thread_id}
    except CosmosResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No dialog found for thread_id: {thread_id}",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting dialog: {exc}",
        )
