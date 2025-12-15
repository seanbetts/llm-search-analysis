# Live Network Log Tab – Implementation Plan

This document captures the approach for adding a “Live Network Log” experience to the Streamlit app. The goal is to let users:

1. Run ChatGPT network capture entirely from the backend (using the existing Chrome/Playwright stack).
2. Stream normalized network events to the frontend so users can watch the model’s searches, tool use, and response-building in real time.
3. Persist a clean JSON log for every run so it can be downloaded or replayed later.

All work for this feature will land on the `feat/frontend-refactor-live-logs` branch (based off `feat/frontend-refactor`) to avoid conflicts with ongoing refactoring.

---

## Objectives

- **Live visibility** – Expose the browser automation process in real time instead of waiting for a single blob of parsed data.
- **Structured logging** – Define a stable event schema that captures search queries, retrieved sources, citations, assistant messages, browser status, and any parser metadata.
- **Safe persistence** – Store every run’s metadata and event list in `data/network_logs/live/` (or the database) so the History tab can surface them later.
- **Non-breaking** – Keep existing Interactive/Batch/History tabs working exactly as before; the new tab is additive.

---

## Architecture Overview

```
Streamlit (new Live tab)
  └─ calls API client extensions (start/stream/list/download live captures)
        └─ FastAPI live capture endpoints
              └─ Live capture manager (wraps ChatGPTCapturer)
                     └─ Chrome/Playwright capture + NetworkLogParser events
                          └─ Structured JSON written to data/network_logs/live/
```

### Event Schema

Every emitted event should share the same base structure so the frontend can format it generically:

```jsonc
{
  "capture_id": "2025-03-14T03:30:05Z-abc123",
  "timestamp": "2025-03-14T03:30:05.231Z",
  "phase": "browser_status" | "search_query" | "search_result" |
           "citation" | "assistant_delta" | "tool_use" | "error",
  "data": {
    "...": "phase-specific payload"
  }
}
```

The parser should emit events for:
- Browser lifecycle (`browser_started`, `authentication`, `search_toggle`, etc.).
- Each search query/text the model issues.
- Each search result entry (URL, rank, snippet, internal score).
- Extra links / citations the assistant references.
- Assistant text deltas or milestones (“response started”, “response complete”).
- Errors or timeouts.

---

## Backend Work

### 1. Live Capture Manager

- New module: `backend/app/services/network_capture/live_capture.py`.
- Responsibilities:
  - Wrap `ChatGPTCapturer` with an event callback hook.
  - Provide an async generator that yields structured events as soon as they arrive.
  - Buffer events in memory and write them to `data/network_logs/live/<capture_id>.json` after completion.
  - Expose high-level metadata (prompt, duration, headless flag, status).
- Interface sketch:

```python
class LiveCaptureManager:
    async def start(self, prompt: str, headless: bool) -> LiveCaptureSession:
        ...

    async def stream_events(self, capture_id: str) -> AsyncIterator[dict]:
        ...

    def get_metadata(self, capture_id: str) -> LiveCaptureMetadata:
        ...

    def list_recent(self, limit: int = 20) -> List[LiveCaptureSummary]:
        ...
```

### 2. FastAPI Endpoints (`backend/app/api/v1/endpoints/live_capture.py`)

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/live_capture/start` | Launch Chrome capture; returns `capture_id`. |
| `GET /api/v1/live_capture/{capture_id}/stream` | Server-Sent Events (SSE) endpoint streaming JSON events. |
| `GET /api/v1/live_capture/{capture_id}` | Fetch metadata + stored JSON after completion. |
| `GET /api/v1/live_capture/recent` | List completed captures for the “history” panel. |
| `DELETE /api/v1/live_capture/{capture_id}` (optional) | Remove stored log if needed. |

Implementation notes:
- **SSE vs WebSockets** – SSE keeps dependencies light and plays nicely with Streamlit (`httpx.stream()` can consume it). Each chunk contains a JSON line serialized via `json.dumps` and prefixed with `data:`.
- **Background tasks** – Starting a capture should hand off the blocking Playwright work to a thread executor. The SSE endpoint simply subscribes to the event queue.
- **Error handling** – Map Playwright/browser errors to an SSE `phase="error"` event before tearing down the session.

### 3. Persistence

- Store logs under `data/network_logs/live/<capture_id>.json`.
- File structure:

```json
{
  "metadata": {
    "capture_id": "...",
    "prompt": "...",
    "model": "chatgpt-free",
    "started_at": "...",
    "finished_at": "...",
    "status": "completed" | "failed" | "aborted",
    "headless": true,
    "event_count": 123
  },
  "events": [ ... ]
}
```

- Optionally, insert a lightweight row into the existing `responses` table with `data_source='network_log_live'` and a pointer to the JSON file so the Query History tab can reference it later without duplicating storage.

### 4. Tests

- Unit tests mocking the capturer to verify event streaming, SSE framing, and persistence.
- Contract tests validating the schemas for `start`, `stream`, `get`, and `recent`.
- Ensure Playwright-specific pieces are behind interfaces so tests don’t launch Chrome.

### 5. Documentation

- Update `docs/DEVELOPMENT_PLAN.md` with an “In progress” section for this feature.
- Add API reference snippets to `backend/API_DOCUMENTATION.md`.
- Mention the new data source in `docs/operations/ENVIRONMENT_VARIABLES.md` if extra env vars are introduced (e.g., for storage locations).

---

## Frontend Work (Streamlit)

### 1. API Client Extensions (`frontend/api_client.py`)

- `start_live_capture(prompt: str, headless: bool) -> dict`
- `stream_live_capture(capture_id: str) -> Iterator[dict]`
- `get_live_capture(capture_id: str) -> dict`
- `list_live_captures(limit: int = 20) -> List[dict]`
- `download_live_log(capture_id: str) -> str` (raw JSON to feed `st.download_button`)

### 2. New Tab Module (`frontend/tabs/live.py`)

Layout idea:

1. **Control panel** – Input prompt, headless toggle, Start button.
2. **Live feed** – Two-column layout:
   - Left: chronological list of events (with icons per phase).
   - Right: summary widgets (current search queries, sources found, assistant status, browser status).
3. **Session metadata** – Timer, capture ID, ability to stop/abort the run.
4. **Saved captures** – Table showing recent captures with “View” / “Download JSON” buttons.

Implementation tips:
- Store `capture_id`, `live_events`, and `live_status` in `st.session_state`.
- Use `httpx.stream` inside `with st.spinner` or `st.empty()` to pull SSE events and update the layout. Consider wrapping the streaming loop in `st.thread` (when available) or non-blocking `asyncio` with `asyncio.run` to avoid freezing the UI.
- Provide a “Reconnect” button if the SSE stream drops (reuse the existing `capture_id`).
- Normalize event formatting in a helper so each `phase` maps to friendly text and colors.

### 3. Download + Replay

- When a capture finishes, show a download button that fetches the stored JSON via `GET /live_capture/{capture_id}`.
- Optional: allow the user to replay a past capture by loading the JSON events back into the live feed component.

### 4. Integration with History Tab (optional follow-up)

- If we log captures as `responses` records with `data_source='network_log_live'`, the Query History tab could surface them automatically.
- Alternatively, add a sub-table in the new tab that lists live captures only.

### 5. Frontend Tests

- Update or add tests under `frontend/tests/` that mock the API client streaming generator and verify the tab renders event logs without crashing.
- Snapshot test for the new tab layout (if the existing suite supports it).

---

## Deployment & Ops Considerations

- Live capture still requires Chrome on the host (same as current network mode). Document that the backend now launches Chrome directly; for Docker deployments, the hybrid setup remains recommended.
- Ensure the backend can launch multiple captures sequentially but gate concurrent runs (e.g., deny `start` while one is active) to avoid Playwright conflicts.
- Log file cleanup: consider a maintenance script or retention policy so `data/network_logs/live/` doesn’t grow without bound.

---

## Rollout Steps

1. **Backend groundwork**
   - Implement live capture manager + endpoints.
   - Add tests and docs.
2. **Frontend tab**
   - Add API client hooks and the new tab UI.
   - Wire the tab into `app.py` and `frontend/tabs/__init__.py`.
3. **Persistence & history**
   - Ensure saved logs are discoverable (file list or DB entries).
4. **Manual QA**
   - Run through both API and network modes to confirm nothing regressed.
   - Validate real-time streaming with headless on/off.
5. **Docs & README**
   - Highlight the feature and note any prerequisites.

Once merged into `feat/frontend-refactor`, we can dogfood the feature before bringing it to `main`.
