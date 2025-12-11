"""Live network capture manager for ChatGPT browser runs."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from app.config import settings
from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.services.providers.base_provider import ProviderResponse

try:
  # The existing ChatGPT capturer lives alongside the Streamlit client.
  from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer
except ImportError as exc:  # pragma: no cover - import path verified in runtime env
  raise RuntimeError("ChatGPTCapturer is unavailable. Ensure frontend dependencies are installed.") from exc


ISOFORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _utc_now() -> datetime:
  """Return timezone-aware UTC timestamp."""
  return datetime.now(timezone.utc)


@dataclass
class LiveCaptureEvent:
  """Structured event emitted during a capture session."""

  capture_id: str
  phase: str
  data: Dict[str, Any] = field(default_factory=dict)
  timestamp: str = field(default_factory=lambda: _utc_now().strftime(ISOFORMAT))

  def to_dict(self) -> Dict[str, Any]:
    """Convert to JSON-serializable dictionary."""
    return {
      "capture_id": self.capture_id,
      "timestamp": self.timestamp,
      "phase": self.phase,
      "data": self.data,
    }


@dataclass
class LiveCaptureSession:
  """In-memory session state for a capture run."""

  capture_id: str
  prompt: str
  headless: bool
  loop: asyncio.AbstractEventLoop
  queue: asyncio.Queue = field(default_factory=asyncio.Queue)
  events: List[Dict[str, Any]] = field(default_factory=list)
  started_at: datetime = field(default_factory=_utc_now)
  finished_at: Optional[datetime] = None
  status: str = "starting"
  model: str = "chatgpt-free"
  provider: str = "openai"
  error: Optional[str] = None
  duration_ms: Optional[int] = None
  event_count: int = 0
  response: Optional[ProviderResponse] = None

  def enqueue(self, event: LiveCaptureEvent) -> None:
    """Push an event onto the async queue in a thread-safe way."""
    loop = self.loop
    if not loop or loop.is_closed():
      return

    try:
      running_loop = asyncio.get_running_loop()
    except RuntimeError:
      running_loop = None

    if running_loop is loop:
      self.queue.put_nowait(event.to_dict())
    else:
      loop.call_soon_threadsafe(self.queue.put_nowait, event.to_dict())

  def close_queue(self) -> None:
    """Signal completion to stream listeners."""
    loop = self.loop
    if not loop or loop.is_closed():
      return

    try:
      running_loop = asyncio.get_running_loop()
    except RuntimeError:
      running_loop = None

    sentinel: Optional[Dict[str, Any]] = None
    if running_loop is loop:
      self.queue.put_nowait(sentinel)
    else:
      loop.call_soon_threadsafe(self.queue.put_nowait, sentinel)


class LiveCaptureManager:
  """Coordinates backend-run ChatGPT captures and event streaming."""

  def __init__(self, storage_root: Optional[Path] = None):
    """Create manager with storage directory for persisted logs."""
    base_dir = Path(storage_root or settings.NETWORK_LOGS_DIR)
    self.storage_dir = base_dir / "live"
    self.storage_dir.mkdir(parents=True, exist_ok=True)
    self.sessions: Dict[str, LiveCaptureSession] = {}

  async def start(self, prompt: str, headless: Optional[bool] = None) -> LiveCaptureSession:
    """Start a live capture run and return session metadata."""
    headless = headless if headless is not None else settings.BROWSER_HEADLESS

    if self._has_active_session():
      raise ConflictError("Another live capture is already running", details={"active_capture_id": self._current_capture_id()})

    capture_id = self._generate_capture_id()
    session = LiveCaptureSession(
      capture_id=capture_id,
      prompt=prompt,
      headless=headless,
      loop=asyncio.get_running_loop(),
    )
    self.sessions[capture_id] = session
    self._emit_event(session, "browser_status", {"message": "Starting ChatGPT browser capture"})
    asyncio.create_task(self._run_capture(session))
    return session

  async def stream_events(self, capture_id: str) -> AsyncIterator[Dict[str, Any]]:
    """Yield events for a capture, replaying from disk when necessary."""
    session = self.sessions.get(capture_id)
    if session:
      while True:
        event = await session.queue.get()
        if event is None:
          break
        yield event
      return

    record = self._load_from_disk(capture_id)
    if not record:
      raise ResourceNotFoundError("live_capture", capture_id)

    for event in record.get("events", []):
      yield event

  def get_metadata(self, capture_id: str) -> Dict[str, Any]:
    """Return metadata for active or completed capture."""
    session = self.sessions.get(capture_id)
    if session:
      return self._build_metadata(session)

    record = self._load_from_disk(capture_id)
    if not record:
      raise ResourceNotFoundError("live_capture", capture_id)
    return record.get("metadata", {})

  def get_record(self, capture_id: str) -> Dict[str, Any]:
    """Return metadata + events for capture."""
    session = self.sessions.get(capture_id)
    if session:
      return {
        "metadata": self._build_metadata(session),
        "events": session.events,
      }

    record = self._load_from_disk(capture_id)
    if not record:
      raise ResourceNotFoundError("live_capture", capture_id)
    return record

  def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent capture summaries, including active session if present."""
    summaries: List[Dict[str, Any]] = []

    active_session = self._active_session()
    if active_session:
      summaries.append(self._build_metadata(active_session))

    files = sorted(
      self.storage_dir.glob("*.json"),
      key=lambda path: path.stat().st_mtime,
      reverse=True,
    )
    for path in files:
      if len(summaries) >= limit:
        break
      record = self._load_from_disk(path.stem, path_override=path)
      if record and record.get("metadata"):
        summaries.append(record["metadata"])
    return summaries[:limit]

  # ---------------------------------------------------------------------------
  # Internal helpers
  # ---------------------------------------------------------------------------

  async def _run_capture(self, session: LiveCaptureSession) -> None:
    """Launch ChatGPT capturer in executor and stream structured events."""
    session.status = "running"
    loop = asyncio.get_running_loop()
    try:
      response = await loop.run_in_executor(None, self._execute_capture, session)
      session.response = response
      session.duration_ms = response.response_time_ms
      session.status = "completed"
      session.finished_at = _utc_now()
      self._emit_response_events(session, response)
      self._emit_event(
        session,
        "assistant_delta",
        {"message": response.response_text, "complete": True},
      )
      self._emit_event(
        session,
        "browser_status",
        {"message": "Live capture completed successfully"},
      )
    except Exception as exc:  # pragma: no cover - Playwright stack is integration tested manually
      session.status = "failed"
      session.error = str(exc)
      session.finished_at = _utc_now()
      self._emit_event(
        session,
        "error",
        {"message": str(exc)},
      )
    finally:
      self._emit_event(session, "capture_complete", self._build_metadata(session))
      self._persist_session(session)
      session.close_queue()
      self.sessions.pop(session.capture_id, None)

  def _execute_capture(self, session: LiveCaptureSession) -> ProviderResponse:
    """Run synchronous ChatGPT capture."""
    def status_callback(message: str) -> None:
      self._emit_event(session, "browser_status", {"message": message})

    capturer = ChatGPTCapturer(
      storage_state_path=settings.CHATGPT_SESSION_FILE,
      status_callback=status_callback,
    )

    try:
      capturer.start_browser(headless=session.headless)
      capturer.authenticate()
      response = capturer.send_prompt(session.prompt, session.model)
      response.data_source = "network_log"
      return response
    finally:
      try:
        capturer.stop_browser()
      except Exception:
        # Browser teardown failures are logged via status callback; continue.
        pass

  def _emit_response_events(self, session: LiveCaptureSession, response: ProviderResponse) -> None:
    """Convert ProviderResponse fields into discrete event payloads."""
    for query in response.search_queries:
      self._emit_event(
        session,
        "search_query",
        {
          "query": query.query,
          "order_index": query.order_index,
          "timestamp": query.timestamp,
          "source_count": len(query.sources),
        },
      )
      for source in query.sources:
        self._emit_event(
          session,
          "search_result",
          {
            "query": query.query,
            "url": source.url,
            "title": source.title,
            "rank": source.rank,
            "domain": source.domain,
            "snippet": source.snippet_text,
          },
        )

    for citation in response.citations:
      self._emit_event(
        session,
        "citation",
        {
          "url": citation.url,
          "title": citation.title,
          "snippet": citation.snippet_used or citation.text_snippet,
          "rank": citation.rank,
        },
      )

  def _emit_event(self, session: LiveCaptureSession, phase: str, data: Dict[str, Any]) -> None:
    """Append and dispatch an event."""
    event = LiveCaptureEvent(capture_id=session.capture_id, phase=phase, data=data)
    session.events.append(event.to_dict())
    session.event_count = len(session.events)
    session.enqueue(event)

  def _build_metadata(self, session: LiveCaptureSession) -> Dict[str, Any]:
    """Construct metadata payload for session."""
    return {
      "capture_id": session.capture_id,
      "prompt": session.prompt,
      "model": session.model,
      "provider": session.provider,
      "status": session.status,
      "headless": session.headless,
      "started_at": session.started_at.strftime(ISOFORMAT),
      "finished_at": session.finished_at.strftime(ISOFORMAT) if session.finished_at else None,
      "event_count": session.event_count,
      "duration_ms": session.duration_ms,
      "error": session.error,
    }

  def _persist_session(self, session: LiveCaptureSession) -> None:
    """Write capture metadata and events to disk."""
    payload = {
      "metadata": self._build_metadata(session),
      "events": session.events,
    }
    output_path = self.storage_dir / f"{session.capture_id}.json"
    with output_path.open("w", encoding="utf-8") as handle:
      json.dump(payload, handle, indent=2)

  def _load_from_disk(self, capture_id: str, path_override: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load persisted capture data."""
    path = path_override or (self.storage_dir / f"{capture_id}.json")
    if not path.exists():
      return None
    try:
      with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
    except json.JSONDecodeError:
      return None

  def _has_active_session(self) -> bool:
    """Return True if a capture is currently running."""
    return any(session.status in {"starting", "running"} for session in self.sessions.values())

  def _current_capture_id(self) -> Optional[str]:
    """Return capture_id of active session if present."""
    active = self._active_session()
    return active.capture_id if active else None

  def _active_session(self) -> Optional[LiveCaptureSession]:
    """Return active session (if exactly one)."""
    for session in self.sessions.values():
      if session.status in {"starting", "running"}:
        return session
    return None

  @staticmethod
  def _generate_capture_id() -> str:
    """Generate sortable capture identifier."""
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"
