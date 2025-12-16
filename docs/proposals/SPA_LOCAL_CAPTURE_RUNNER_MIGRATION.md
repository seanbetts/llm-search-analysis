# SPA + Local Capture Runner Migration Plan

## Summary

Replace the Streamlit UI with a custom SPA (React/TypeScript) while keeping the FastAPI backend as the source of truth. Preserve “Web capture” (Playwright + local Chrome) by moving it out of the UI into a **local capture runner** process that the SPA can control and observe. The runner posts normalized capture results to the backend using the existing `POST /api/v1/interactions/save-network-log` contract.

This approach keeps the app fully usable during the transition and avoids trying to run Playwright in a browser-only SPA environment.

## Goals

- Ship a first-class SPA for the four current “tabs”: Web, API, Batch, History.
- Keep backend contracts stable and typed (OpenAPI → generated TS client).
- Preserve web capture capabilities via a local runner with live progress streaming.
- Avoid blocking a future cloud migration (runner can remain local initially; later capture can move server-side if desired).

## Non-Goals (for the first migration)

- Multi-user authentication/authorization.
- Full “cloud capture” (running Playwright in backend/worker infrastructure).
- Perfect parity in visual layout with Streamlit; preserve workflow and data fidelity instead.

## Current Streamlit Responsibilities (What We’re Replacing)

Streamlit today provides:

- **Routing/layout**: `app.py` uses Streamlit tabs to route to:
  - `frontend/tabs/web.py` (web capture)
  - `frontend/tabs/api.py` (API prompts)
  - `frontend/tabs/batch.py` (batch runs)
  - `frontend/tabs/history.py` (history, filters, detail, exports)
- **Session state**: `st.session_state` holds the API client, tab state, polling flags, and intermediate results.
- **Rendering**: `frontend/components/response.py` renders metrics, response markdown, sources, citations, and extra links.
- **Web capture orchestration**: `frontend/tabs/web.py` runs Playwright capture locally and then persists results to backend using:
  - `POST /api/v1/interactions/save-network-log`
  - optional polling `GET /api/v1/interactions/{id}` for citation tagging status

The migration replaces Streamlit’s UI/state/routing with SPA equivalents and replaces Streamlit’s *embedded capture execution* with a dedicated local runner process.

## Target Architecture (End State)

### High-level diagram

```
               ┌──────────────────────────────────┐
               │            SPA (React)            │
               │  - Web/API/Batch/History pages    │
               │  - Typed API client (OpenAPI)     │
               │  - Live capture UI (events/logs)  │
               └───────────────┬───────────────────┘
                               │ HTTP (backend API)
                               v
               ┌──────────────────────────────────┐
               │          FastAPI Backend          │
               │  /api/v1/interactions/*           │
               │  /api/v1/providers                │
               │  /health                          │
               └───────────────┬───────────────────┘
                               │
                               │ (persist normalized capture payload)
                               │  POST /api/v1/interactions/save-network-log
                               v
                     SQLite + migrations + services

     ┌─────────────────────────────────────────────────────────────┐
     │                    Local Capture Runner                      │
     │  - Playwright + installed Chrome                             │
     │  - Uses existing capture/parser code                          │
     │  - Streams progress events to SPA (SSE/WebSocket)             │
     │  - Posts final normalized payload to backend                  │
     └─────────────────────────────────────────────────────────────┘
```

### Who talks to whom

- SPA → Backend: normal app operations (API mode, batch API mode, history, exports).
- SPA → Runner (localhost): start/stop capture, stream events, retrieve final capture payload.
- Runner → Backend: persist capture via `save-network-log` using the same schema Streamlit uses today.

## Key Contracts (Stabilize Before SPA Work)

### Backend persistence contract for web capture

The runner should produce and submit a `SaveNetworkLogRequest` payload:

- Schema: `backend/app/api/v1/schemas/requests.py` `SaveNetworkLogRequest`
- Endpoint: `POST /api/v1/interactions/save-network-log` (`backend/app/api/v1/endpoints/interactions.py`)

Important: this schema already supports:

- `search_queries[]` (with optional sources)
- `sources[]` (flattened “all sources” list)
- `citations[]` (with `rank` optional and tagging fields)
- `raw_response` for debugging
- `enable_citation_tagging` toggle

### Backend read contracts used by UI

The SPA should use the same endpoints Streamlit uses today:

- `POST /api/v1/interactions/send` (API mode)
- `POST /api/v1/interactions/batch`, `GET /api/v1/interactions/batch/{batch_id}`, `POST /api/v1/interactions/batch/{batch_id}/cancel`
- `GET /api/v1/interactions/recent` (pagination/filtering)
- `GET /api/v1/interactions/{interaction_id}`
- `GET /api/v1/interactions/{interaction_id}/export/markdown`
- `GET /api/v1/providers` (models/providers)

## Local Capture Runner: Design

### Form factor options (choose one)

1. **Local HTTP service (recommended for SPA)**
   - A small local server (FastAPI/Starlette in Python) bound to `127.0.0.1`.
   - Exposes `start capture` + `stream events` endpoints consumable by the SPA.
   - Pros: simple integration with browser-based SPA; easy live streaming; cross-platform.
   - Cons: introduces a second “server” process.

2. **CLI-only runner**
   - SPA cannot directly control a CLI without extra glue.
   - Useful for development and debugging, but not a good UX for end users.

3. **Desktop wrapper (Electron/Tauri)**
   - Great UX long-term, but higher initial build complexity.

This plan assumes option (1): a local HTTP service.

### Runner responsibilities

- Launch and manage Playwright + Chrome (and any session persistence needed).
- Execute capture using existing modules in `frontend/network_capture/` (or extracted equivalents).
- Emit progress events during:
  - browser start / login / search enablement
  - prompt submission
  - response generation
  - parsing/normalization
  - backend persistence (save-network-log)
- Return the backend’s saved `SendPromptResponse` payload to the SPA for display (or at least `interaction_id`).

### Runner API (localhost)

Suggested endpoints (v0):

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/captures` | Start a capture job. Returns `capture_id`. |
| `GET /v1/captures/{capture_id}/events` | Stream events (SSE) or WebSocket. |
| `POST /v1/captures/{capture_id}/cancel` | Cancel/stop capture. |
| `GET /v1/captures/{capture_id}` | Get final result + status. |

Suggested request body for start:

```jsonc
{
  "prompt": "string",
  "model": "chatgpt-free",
  "headless": true,
  "backend_base_url": "http://localhost:8000",
  "enable_citation_tagging": true
}
```

### Event schema (runner → SPA)

Use a stable event envelope (compatible with future cloud capture):

```jsonc
{
  "capture_id": "string",
  "ts": "2025-12-16T12:34:56.789Z",
  "phase": "browser" | "auth" | "prompt" | "response" | "parse" | "persist" | "error",
  "message": "human-readable text",
  "data": { "phase_specific": "payload" }
}
```

The SPA should render these as a live log and optionally summarize them (e.g., “search queries found”, “sources parsed”, etc.).

### Security posture (local-only)

- Bind runner to `127.0.0.1` only (no LAN access).
- Implement strict CORS allowlist for SPA origins (dev and prod).
- Optional hardening: require a runner token (printed to console on startup and provided to SPA via env / manual paste).

## SPA: Design and Implementation Notes

### Recommended stack

- React + TypeScript
- Vite (local dev) or Next.js (if you want a BFF and future auth quickly)
- TanStack Query (or equivalent) for backend calls/caching
- Zod for runtime validation of runner events (since runner is local and may evolve quickly)

### UI parity mapping (Streamlit → SPA pages)

| Current tab | SPA page | Backend dependencies |
| --- | --- | --- |
| Web (`frontend/tabs/web.py`) | `/web` | Runner + `save-network-log` + `GET interaction` polling for tagging |
| API (`frontend/tabs/api.py`) | `/api` | `POST /interactions/send` |
| Batch (`frontend/tabs/batch.py`) | `/batch` | `POST /interactions/batch` + polling/cancel; optional runner batch later |
| History (`frontend/tabs/history.py`) | `/history` | `GET /interactions/recent`, detail fetch, delete, export |

### Rendering model

Refactor Streamlit’s monolithic `display_response` into SPA components:

- `ResponseHeader` (provider/model/time/metrics)
- `ResponseBody` (markdown rendering, link sanitation, images)
- `SearchQueries` (list)
- `SourcesFound` (API vs web mode differences)
- `CitationsUsed` + `ExtraLinks` (with tags/mentions)

Use backend’s `SendPromptResponse` as the canonical DTO to avoid frontend metric recomputation.

## Migration Roadmap (Phased, With Deliverables)

### Phase 1 — Contract hardening (1–3 days)

Deliverables:

- Confirm the backend endpoints above are stable and documented.
- Ensure `SendPromptResponse` fully supports SPA needs for display (it mostly does).
- Identify any missing “UI-friendly” fields and add them to backend responses rather than computing in the SPA.

Recommended checks:

- OpenAPI schema generation is correct and complete.
- History filters/pagination in `GET /interactions/recent` cover what the SPA needs.

### Phase 2 — Introduce the runner as a standalone process (2–5 days)

Deliverables:

- New top-level runner package/app (example name: `capture_runner/` or `runner/`).
- Runner can execute a single ChatGPT capture and post to backend using `save-network-log`.
- Runner streams live progress events to clients.

Implementation steps:

1. Extract or reuse capture modules:
   - Option A (fastest): runner imports existing `frontend/network_capture/*`.
   - Option B (cleaner): move capture code to a shared package (e.g., `capture/`) used by both Streamlit and runner, then delete Streamlit wiring later.
2. Add a runner config layer:
   - Chrome location/channel, session storage path, credentials sources.
3. Provide an install/run experience:
   - `pip install -e .` + `python -m runner` during dev.
   - Later: packaged binary via PyInstaller or similar.

Acceptance criteria:

- From a simple client (curl/Postman), start capture, watch events stream, and receive a saved `interaction_id`.

### Phase 3 — Build SPA shell (3–7 days)

Deliverables:

- SPA repo/app in-tree (or separate repo if preferred).
- Generated TS client from backend OpenAPI.
- Pages: `/api`, `/history` with working calls and rendering.

Acceptance criteria:

- API prompt works end-to-end.
- History list/detail/delete/export work end-to-end.

### Phase 4 — Implement Batch (API mode) in SPA (2–4 days)

Deliverables:

- SPA batch page uses backend-managed batch endpoints.
- Live progress UI with cancel.

Acceptance criteria:

- Matches Streamlit batch behavior for API mode.

### Phase 5 — Implement Web capture page via runner (3–7 days)

Deliverables:

- SPA `/web` page can:
  - start capture via runner
  - stream events live
  - show final `SendPromptResponse` after backend persistence
  - optionally poll for citation-tagging completion (same as Streamlit’s current behavior)

Acceptance criteria:

- Web capture flow works without Streamlit running.
- Captures are persisted and appear in History.

### Phase 6 — Decommission Streamlit UI (1–2 days)

Deliverables:

- Streamlit remains optional (or removed) once SPA+runner parity exists.
- Update repo docs to reflect new run workflow:
  - Backend (Docker)
  - SPA (local dev server)
  - Runner (local service)

Acceptance criteria:

- “Happy path” user can run full system without Streamlit.

## Dev and Run Workflow (Target)

Local dev commands (illustrative):

- Backend: `docker compose up -d`
- Runner: `python -m runner --port 7777`
- SPA: `pnpm dev` (or `npm run dev`) with:
  - `VITE_API_BASE_URL=http://localhost:8000`
  - `VITE_RUNNER_BASE_URL=http://127.0.0.1:7777`

## Risks and Mitigations

- **Playwright brittleness / CAPTCHA / UI changes**: keep runner events very explicit, store raw logs, and fail fast with actionable messages.
- **Two-process UX**: provide a single `scripts/start-dev.sh` to launch backend+runner+SPA; later package runner.
- **Schema drift**: treat `SaveNetworkLogRequest` as a strict contract; validate runner output against backend schema (optional: JSON Schema export).
- **Cloud migration later**: keep event schema and capture job API compatible with a future “cloud capture service” so the SPA doesn’t care where capture runs.

## Open Questions (Decisions to make early)

1. SPA framework choice: Vite vs Next.js (BFF needs? auth? hosting?).
2. Runner packaging: pure dev process vs packaged binary for users.
3. Credential/session model for ChatGPT capture (single account vs pool, session persistence paths, secrets handling).
4. Streaming: SSE vs WebSocket (SSE is simpler; WS is richer for bi-directional control).
5. How much of Streamlit’s formatting (markdown sanitation, citation display) should be moved into shared libraries vs reimplemented in TS.

