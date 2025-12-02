# Frontend Refactor Plan (Streamlit → React-Ready)

**Goal:** Make the FastAPI backend the source of truth for domain logic and metrics, keep Streamlit as a thin, disposable UI shell, and shape APIs/data structures so a future React (or similar) frontend can plug in with minimal duplication.

> Note: The earlier architecture review refers to a `ui/` package (for constants, components, etc.). This plan uses the existing `frontend/` package instead; wherever `ui/` appears in older docs, read it as `frontend/`.

---

## Guiding Principles

- Prefer moving logic into the backend over adding abstractions in Streamlit.
- Any non-trivial computation needed in a future React UI should not live only in `app.py`.
- Streamlit refactors should improve readability and maintainability but stay relatively shallow (no heavy Streamlit component framework).
- Backend is responsible for security-critical validation and normalization; the frontend provides only light UX validation and surfaces backend errors clearly.

---

## Phase 0 – Inventory & API Contract Check (P1)

**Objective:** Understand what the current Streamlit UI does and which parts of the logic should move server-side or into shared modules.

- [ ] **Inventory current UI features in `app.py`:**
  - Interactive prompt flow.
  - Batch analysis flow.
  - History listing and interaction detail view.
  - Markdown and CSV exports.
  - Metrics display (sources found/used, avg rank, extra links, analysis type).
  - Network-log mode behaviour and toggles.

- [ ] **Map each feature to backend endpoints:**
  - For each UI feature, record which FastAPI endpoint(s) it calls.
  - Note any gaps where the UI computes derived values that could instead come from the backend.

- [ ] **Identify “computed-on-frontend” pieces to move:**
  - Metrics: sources found/used, avg rank, extra links, analysis type, formatted timestamps.
  - Model/provider display names.
  - Markdown export structure.
  - Network-log specific derivations (e.g., `all_sources` vs `query.sources` handling).

**Deliverable:** Short mapping (can live here or in `IMPLEMENTATION_PLAN.md`) listing "Frontend-only logic to move server-side or share."

---

## Phase 1 – Centralize Domain Logic in Backend/Core (P1)

**Objective:** Make the backend (or shared core) responsible for metrics, naming, and exports so Streamlit and future React clients are thin renderers.

### 1. Metrics & Summaries in Backend

- [ ] Extend backend response schemas so `InteractionDetail` and `InteractionSummary` include:
  - `sources_found`
  - `sources_used`
  - `avg_rank`
  - `extra_links`
  - `analysis_type`
  - Display-ready timestamp (or a clearly defined structure for formatting on the client).

- [ ] Move calculations currently done in `app.py` (e.g. in `build_interaction_markdown()` and the History tab) into backend services.

- [ ] Add backend tests that verify these metrics so both Streamlit and React UIs can rely on them.

### 2. Model & Provider Naming

- [ ] Move `normalize_model_id()` and `get_model_display_name()` logic into:
  - A backend utility module used by services and/or
  - Backend response fields like `provider_display` and `model_display` that are ready for UI.

- [ ] Add tests to ensure name mappings are stable and consistent across UIs.

- [ ] In the frontend, treat any remaining mapping helpers (e.g. display-name fallbacks) as temporary shims:
  - Prefer using backend-provided display fields wherever available.
  - Avoid introducing new long-lived provider/model tables in the frontend.

### 3. Export Logic (Markdown & CSV)

- [ ] Implement backend export endpoints, for example:
  - `GET /api/v1/interactions/{id}/export/markdown`
  - `GET /api/v1/interactions/export.csv` (or a parameterised export endpoint).

- [ ] Move the structure currently implemented in `build_interaction_markdown()` into backend code.

- [ ] Update Streamlit:
  - Keep export buttons in the UI.
  - Change them to call the backend export endpoints instead of rebuilding export formats in `app.py`.

### 4. Network-Log Specific Mapping

- [ ] Consolidate network-log semantics in the backend:
  - Provide a consistent JSON shape for `sources`, `citations`, and network-log-specific fields.
  - Ensure `data_source` is explicit, and that the backend provides already-aggregated lists that the UI can render without special-case logic.

- [ ] Add backend tests for network-log data so UI code can treat network-log vs API data uniformly where possible.

**Result:** Most domain logic lives in the backend; the frontend becomes a relatively thin renderer over rich JSON responses.

---

## Phase 2 – Streamlit Refactor: Thin Shell + Modules (P2)

**Objective:** Make `app.py` small and comprehensible, with tab-specific modules and minimal, view-only helpers.

### 1. Split `app.py` by Responsibility

- [ ] Keep in `app.py`:
  - Page config and global CSS.
  - `initialize_session_state()` (slimmed down).
  - `sidebar_info()`.
  - `main()` function that wires tabs.

- [ ] Create tab modules:
  - `frontend/tabs/interactive.py` with `tab_interactive()`.
  - `frontend/tabs/batch.py` with `tab_batch()`.
  - `frontend/tabs/history.py` with `tab_history()`.

- [ ] Extract global CSS from `app.py`:
  - Move the long `<style>...</style>` block into a dedicated helper (e.g. `frontend/styles.py`) or a separate CSS file (e.g. `frontend/styles.css`).
  - Keep `app.py` responsible only for injecting the CSS via a small wrapper (e.g. `st.markdown(load_styles(), unsafe_allow_html=True)`).

### 2. Introduce Minimal UI Helpers

- [ ] `frontend/components/metrics.py`:
  - Functions to render the metrics row given backend-provided metrics (no calculations inside).

- [ ] `frontend/components/sources.py`:
  - Functions to render "Sources Found", "Sources Used", and "Extra Links" using the normalized backend data shape.

- [ ] `frontend/components/response.py`:
  - Response text rendering and related view-level helpers, such as:
    - `sanitize_response_markdown()`.
    - Image extraction and inline display.

### 3. Centralize Frontend Utilities (Thin Only)

- [ ] `frontend/utils.py` for small, Streamlit-side helpers that:
  - Format any remaining timestamps (if not already formatted by backend).
  - Provide simple, view-only convenience functions used by multiple tabs.

- [ ] `frontend/constants.py` for UI-only configuration, such as:
  - Default history limit for the History tab.
  - Max prompt length for the text area (kept in sync with backend validation).
  - Default data collection mode.
  - Any other purely presentational constants.

- [ ] Avoid using `frontend/constants.py` as the source of truth for provider/model names:
  - Use backend-provided display fields where possible.
  - Reserve constants for UI behaviour/config, not domain semantics.

### 4. Unify Error Handling

- [ ] Implement a helper like `safe_api_call(callable)` that:
  - Wraps calls to `APIClient`.
  - Catches `APIClientError` subclasses.
  - Displays consistent Streamlit error messages or warnings.

- [ ] Replace scattered `try/except` blocks in tabs with calls to `safe_api_call`.

- [ ] Clarify validation responsibilities:
  - Rely on backend Pydantic validation and error codes for correctness and security (length limits, allowed models/providers, XSS checks, etc.).
  - Use frontend checks only for UX (e.g. non-empty prompt, obvious length warnings) and to show friendly summaries of backend validation errors.

**Result:** `app.py` becomes a thin entrypoint; tab modules and components are small, focused, and mostly view-only.

---

## Phase 3 – React-Ready API & Data Shapes (P1/P2)

**Objective:** Shape the backend API and data contracts so a future React app can plug in directly with minimal redesign.

### 1. Define React-Oriented API Surface

- [ ] Confirm a small, stable set of endpoints for React:
  - `POST /api/v1/interactions/send`
  - `GET /api/v1/interactions/recent` (with filters/pagination)
  - `GET /api/v1/interactions/{id}`
  - `DELETE /api/v1/interactions/{id}`
  - Export endpoints (markdown/CSV as above)

- [ ] Document these endpoints explicitly for JavaScript/TypeScript clients in `backend/API_DOCUMENTATION.md`.

### 2. History Filtering & Pagination

- [ ] Add server-side pagination and filtering to history endpoints:
  - Query params like `page`, `page_size`.
  - Filters such as `provider`, `model`, `analysis_type`, date ranges.

- [ ] Update Streamlit to use these parameters while keeping UI logic simple (no heavy client-side reimplementation).

- [ ] Improve perceived performance for history views:
  - Use `st.cache_data` (with a sensible TTL or manual "Refresh" control) when appropriate to avoid refetching unchanged history on every interaction.
  - Combine caching with backend pagination so the UI fetches only the needed slice of data.

### 3. Future Authentication / Multi-User Considerations (Optional)

- [ ] Decide whether to reserve space in the API for auth/multi-user (e.g., headers or token-based auth), even if not implemented yet, to avoid breaking changes when React arrives.

**Result:** The API surface is stable and well-documented for a React client, and Streamlit is just one consumer of that API.

---

## Phase 4 – React Migration Path (Planning Only) (P3)

**Objective:** Outline how the React app will map onto the existing backend and concepts, without implementing it yet.

- [ ] Sketch React routes and views that correspond to current tabs:
  - `/interactive`
  - `/batch`
  - `/history`
  - `/interaction/:id`

- [ ] Define TypeScript types that mirror backend responses:
  - `InteractionSummary`
  - `InteractionDetail`
  - `Citation`
  - `Source`
  - `Metrics`

- [ ] Plan a JS/TS client library:
  - Methods mirroring the Python `APIClient`:
    - `sendPrompt`
    - `getRecentInteractions`
    - `getInteraction`
    - `deleteInteraction`
    - `exportInteractionMarkdown`
    - `exportHistoryCsv`

**Result:** When you are ready to build the React frontend, the path to implementation is clear and aligned with the current backend design.

---

## Priority Summary

- **P1 (High Priority / Do First)**
  - Move metrics, model/provider naming, export logic, and network-log mapping into backend or shared core.
  - Define and document the React-ready API surface.

- **P2 (Medium Priority)**
  - Split `app.py` into tab modules and minimal components.
  - Introduce thin UI helpers, unified error handling, and UI-only constants/config in Streamlit.
  - Extract inline CSS and remove magic numbers (timeouts, limits) in favour of configuration.

- **P3 (Lower Priority / Planning)**
  - React migration design: routes, TypeScript types, and JS/TS client library shape.
