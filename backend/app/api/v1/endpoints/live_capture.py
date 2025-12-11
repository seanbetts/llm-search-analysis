"""Live network capture API endpoints."""

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.v1.schemas.requests import LiveCaptureStartRequest
from app.api.v1.schemas.responses import (
  LiveCaptureListResponse,
  LiveCaptureRecord,
  LiveCaptureStartResponse,
)
from app.dependencies import get_live_capture_manager
from app.services.network_capture.live_capture import ISOFORMAT, LiveCaptureManager

router = APIRouter(prefix="/live_capture", tags=["live_capture"])


@router.post("/start", response_model=LiveCaptureStartResponse)
async def start_live_capture(
  request: LiveCaptureStartRequest,
  manager: LiveCaptureManager = Depends(get_live_capture_manager),
):
  """Launch a backend-managed ChatGPT capture run."""
  session = await manager.start(prompt=request.prompt, headless=request.headless)
  return LiveCaptureStartResponse(
    capture_id=session.capture_id,
    status=session.status,
    headless=session.headless,
    started_at=session.started_at.strftime(ISOFORMAT),
  )


@router.get("/recent", response_model=LiveCaptureListResponse)
async def list_recent_captures(
  limit: int = Query(20, ge=1, le=100, description="Maximum captures to return"),
  manager: LiveCaptureManager = Depends(get_live_capture_manager),
):
  """List recent live capture runs."""
  return LiveCaptureListResponse(captures=manager.list_recent(limit=limit))


@router.get("/{capture_id}", response_model=LiveCaptureRecord)
async def get_live_capture(
  capture_id: str,
  manager: LiveCaptureManager = Depends(get_live_capture_manager),
):
  """Return metadata and persisted events for a capture."""
  return manager.get_record(capture_id)


@router.get("/{capture_id}/stream")
async def stream_live_capture(
  capture_id: str,
  manager: LiveCaptureManager = Depends(get_live_capture_manager),
):
  """Server-sent events endpoint streaming live capture events."""
  # Validate capture exists (active or persisted)
  manager.get_metadata(capture_id)

  async def event_iterator() -> AsyncIterator[str]:
    async for event in manager.stream_events(capture_id):
      yield f"data: {json.dumps(event)}\n\n"

  return StreamingResponse(
    event_iterator(),
    media_type="text/event-stream",
    headers={
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  )
