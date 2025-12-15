# Frontend Overview (Streamlit)

The Streamlit frontend provides the user interface for LLM Search Analysis. After the recent refactor, the UI is a thin shell that renders backend data and handles browser automation for network capture mode.

## Architecture Snapshot

```
app.py
├── frontend/styles.py                 # CSS helpers
├── frontend/utils.py                  # Shared formatting helpers
├── frontend/helpers/                  # e.g., error handling wrapper
├── frontend/components/
│   └── response.py                    # Rendering helpers (display_response, etc.)
├── frontend/tabs/
│   ├── interactive.py                # Tab 1 – single prompt + network mode
│   ├── batch.py                      # Tab 2 – prompt/model matrix
│   └── history.py                    # Tab 3 – recent interactions
└── frontend/api_client.py            # HTTP client wrapping FastAPI
```

Key principles:
- **Backend-first** – the FastAPI service is the source of truth for metrics, model names, exports, etc. The UI renders what the API returns.
- **Modular tabs** – each tab lives in `frontend/tabs/` with minimal shared state beyond `st.session_state`.
- **Reusable components** – complex display helpers (response rendering, CSS, error handling) live in `frontend/components/` and `frontend/helpers/`.
- **Network capture isolation** – Live browser automation is implemented under `frontend/network_capture/` and documented in `docs/frontend/NETWORK_CAPTURE.md`.

## Tabs at a Glance

| Tab | Module | Responsibilities |
| --- | --- | --- |
| Interactive | `frontend/tabs/interactive.py` | Single-prompt runs, model selection, network capture toggle, markdown export. |
| Batch | `frontend/tabs/batch.py` | Prompt × model matrix execution, CSV import/export, progress display. |
| History | `frontend/tabs/history.py` | Recent interactions list, filters, detail view, markdown export, delete. |

All tabs use the shared `APIClient` to talk to FastAPI and share the unified error-handling helper for consistent Streamlit messaging.

## API Client

`frontend/api_client.py` wraps `httpx` with connection pooling, retries, and custom exceptions. It exposes methods for:
- `send_prompt(...)`
- `get_recent_interactions(...)`
- `get_interaction(...)`
- `delete_interaction(...)`
- `get_providers()` / `get_models()`
- `export_interaction_markdown(...)`

See `docs/backend/OVERVIEW.md` for the corresponding FastAPI endpoints.

## Testing

- **API client tests** (respx mocks) – see `frontend/tests/test_api_client.py`.
- **Component tests** – see `docs/frontend/TESTING.md` for coverage of formatting/conversion helpers.
- Streamlit’s experimental `AppTest` isn’t used yet; manual verification and backend contract tests ensure schema stability.

## Network Capture

Refer to `docs/frontend/NETWORK_CAPTURE.md` for Playwright prerequisites, architecture, and current status. Network capture is encapsulated so the rest of the UI consumes normalized data identical to the API mode.

## Active Work

- **Frontend Refactor Plan** (`docs/archive/FRONTEND_REFACTOR_PLAN.md`) – Phase 3 focuses on pagination/filtering, React-ready contracts, and further modularization.
- **Live Network Logs Plan** (`docs/proposals/LIVE_NETWORK_LOGS_PLAN.md`) – adds a fourth tab that streams browser events in real time, reusing the existing network capture stack.
