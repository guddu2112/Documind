"""Real-time pipeline status — WebSocket and SSE endpoints.

Routes:
    WS  /documents/{id}/ws     — WebSocket for live pipeline updates.
    GET /documents/{id}/events — SSE fallback for corporate proxies.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from documind.api.schemas import PipelineEvent
from documind.core.models.base import ProcessingStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# Polling interval for status checks (seconds)
_POLL_INTERVAL = 2.0
# Maximum time to keep a connection open (seconds)
_MAX_DURATION = 300.0


async def _poll_status(document_id: str, doc_type: str | None = None):
    """Poll Cosmos DB for status changes.

    Yields PipelineEvent dicts whenever the status changes.
    Uses cross-partition query when doc_type is unknown.
    """
    from documind.services.cosmos import CosmosService

    cosmos = CosmosService()
    last_status = None
    elapsed = 0.0

    while elapsed < _MAX_DURATION:
        try:
            record = None
            if doc_type:
                try:
                    record = cosmos.get_record(document_id, doc_type)
                except Exception:
                    pass
            if record is None:
                items = list(cosmos._container.query_items(
                    query="SELECT * FROM c WHERE c.document_id = @id",
                    parameters=[{"name": "@id", "value": document_id}],
                    enable_cross_partition_query=True,
                ))
                if items:
                    record = items[0]
            if record is None:
                await asyncio.sleep(_POLL_INTERVAL)
                elapsed += _POLL_INTERVAL
                continue
            current = record.get("status", "pending")

            if current != last_status:
                last_status = current
                event = PipelineEvent(
                    document_id=document_id,
                    stage=current,
                    status=current,
                    timestamp=datetime.utcnow(),
                    detail=record.get("error_message", ""),
                )
                yield event

                # Terminal states — stop polling
                if current in (
                    ProcessingStatus.COMPLETED.value,
                    ProcessingStatus.FAILED.value,
                ):
                    return

        except Exception as exc:
            logger.warning("Status poll error for %s: %s", document_id, exc)

        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL


# ── WebSocket ──────────────────────────────────────────────────────


@router.websocket("/documents/{document_id}/ws")
async def document_ws(websocket: WebSocket, document_id: str):
    """WebSocket endpoint for live pipeline status updates.

    Sends JSON messages with PipelineEvent schema on status changes.
    Closes when processing completes/fails or after timeout.
    """
    await websocket.accept()
    logger.info("WS connected: %s", document_id)

    try:
        async for event in _poll_status(document_id):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", document_id)
    except Exception as exc:
        logger.error("WS error for %s: %s", document_id, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── SSE (Server-Sent Events) ───────────────────────────────────────


@router.get(
    "/documents/{document_id}/events",
    summary="SSE stream of pipeline status updates",
)
async def document_sse(document_id: str):
    """SSE fallback for environments where WebSockets are blocked.

    Returns ``text/event-stream`` with JSON-encoded PipelineEvent data.
    """

    async def event_generator():
        async for event in _poll_status(document_id):
            data = event.model_dump_json()
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx compatibility
        },
    )
