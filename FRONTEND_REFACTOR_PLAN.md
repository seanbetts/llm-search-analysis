# Frontend Refactor Plan (Streamlit → React-Ready)

**Goal:** Make the FastAPI backend the source of truth for domain logic and metrics, keep Streamlit as a thin, disposable UI shell, and shape APIs/data structures so a future React (or similar) frontend can plug in with minimal duplication.

> Note: The earlier architecture review refers to a `ui/` package (for constants, components, etc.). This plan uses the existing `frontend/` package instead; wherever `ui/` appears in older docs, read it as `frontend/`.

---

## Guiding Principles

- Prefer moving logic into the backend over adding abstractions in Streamlit.
- Any non-trivial computation needed in a future React UI should not live only in `app.py`.
- Streamlit refactors should improve readability and maintainability but stay relatively shallow (no heavy Streamlit component framework).
- Backend is responsible for security-critical validation and normalization; the frontend provides only light UX validation and surfaces backend errors clearly.

## Test-Driven Development (TDD) Approach

**This refactor MUST be test-led.** Every change should follow this pattern:

1. **Write Tests First:**
   - Before moving logic to backend, write tests that define expected behavior
   - Tests should cover both happy path and edge cases
   - Use existing behavior as the specification

2. **Backend Testing Requirements:**
   - **Unit Tests:** Every new function/method in services, repositories, utilities
   - **Integration Tests:** Every new or modified API endpoint
   - **Schema Tests:** Validate all new/modified Pydantic schemas
   - **Target Coverage:** Maintain or exceed current 79% coverage
   - All tests must pass before merging

3. **Frontend Testing Strategy:**
   - **Behavior Preservation:** New components must maintain existing UI behavior
   - **API Client Tests:** Add tests for any new APIClient methods
   - **Manual Testing:** Test each refactored UI component thoroughly
   - Note: Streamlit testing is limited, so manual verification is critical

4. **Refactoring Safety:**
   - Run full test suite before and after each change
   - If tests fail after refactor, fix immediately or revert
   - Use git branches for each phase to enable easy rollback

5. **Test Organization:**
   ```
   backend/tests/
   ├── test_metrics.py              # New: Test metric calculations
   ├── test_export_endpoints.py     # New: Test export logic
   ├── test_model_display_names.py  # New: Test name mappings
   └── test_interaction_service.py  # Update: Add metric computation tests

   frontend/tests/
   ├── test_api_client.py           # Update: Test new methods
   └── test_components.py           # New: Test display components
   ```

6. **TDD Workflow Example:**
   ```python
   # Step 1: Write the test FIRST
   def test_compute_interaction_metrics():
       """Test that metrics are computed correctly on save."""
       interaction = create_test_interaction(
           citations=[{"rank": 1}, {"rank": 3}],
           sources=[...]
       )
       metrics = compute_metrics(interaction)
       assert metrics.sources_found == 5
       assert metrics.sources_used == 2
       assert metrics.avg_rank == 2.0

   # Step 2: Implement to make test pass
   def compute_metrics(interaction):
       # Implementation here
       ...

   # Step 3: Refactor with confidence (tests still pass)
   ```

---

## Phase 0 – Inventory & API Contract Check (P1)

**Status:** ✅ COMPLETED (Dec 2, 2025)

**Objective:** Understand what the current Streamlit UI does and which parts of the logic should move server-side or into shared modules.

- [x] **Inventory current UI features in `app.py`:**
  - Interactive prompt flow.
  - Batch analysis flow.
  - History listing and interaction detail view.
  - Markdown and CSV exports.
  - Metrics display (sources found/used, avg rank, extra links, analysis type).
  - Network-log mode behaviour and toggles.

- [x] **Map each feature to backend endpoints:**
  - For each UI feature, record which FastAPI endpoint(s) it calls.
  - Note any gaps where the UI computes derived values that could instead come from the backend.

- [x] **Identify "computed-on-frontend" pieces to move:**
  - Metrics: sources found/used, avg rank, extra links, analysis type, formatted timestamps.
  - Model/provider display names.
  - Markdown export structure.
  - Network-log specific derivations (e.g., `all_sources` vs `query.sources` handling).

---

### Inventory Results

**File Sizes:**
- `app.py`: **1,605 lines** (73KB) - Too large!
- `frontend/api_client.py`: 412 lines (12KB) - Well structured ✅

**Current Structure:**
```
app.py (1,605 lines)
├── CSS (lines 27-93) - 67 lines inline
├── State Management (lines 95-119)
├── Utility Functions (lines 121-405)
│   ├── format_pub_date() - Date formatting
│   ├── normalize_model_id() - Model name normalization
│   ├── get_model_display_name() - Large model mapping dict (47 lines!)
│   ├── sanitize_response_markdown() - Response cleaning
│   ├── build_interaction_markdown() - Export builder (120 lines!)
│   ├── format_response_text() - Citation link conversion
│   └── extract_images_from_response() - Image extraction
├── Data Loading (lines 407-454)
│   └── get_all_models() - Fetch and merge models from backend
├── Display Functions (lines 456-686)
│   └── display_response() - Main response renderer (230 lines!)
├── Tab Functions (lines 688-1485)
│   ├── tab_interactive() - Interactive prompting (161 lines)
│   ├── tab_batch() - Batch analysis (245 lines)
│   └── tab_history() - Query history (393 lines!)
└── Main (lines 1487-1605)
    ├── sidebar_info() - Sidebar content
    └── main() - App entrypoint
```

**Tab 1: Interactive Prompting** (`tab_interactive()` lines 688-849)
- **Backend endpoints used:**
  - `GET /api/v1/providers` - Get providers and models
  - `POST /api/v1/interactions/send` - Send prompt
- **Frontend computations:**
  - Average rank calculation (line 497)
  - Extra links count fallback (lines 503-505)
  - Markdown export structure (lines 214-334)

**Tab 2: Batch Analysis** (`tab_batch()` lines 849-1094)
- **Backend endpoints used:**
  - `POST /api/v1/interactions/send` (called in loop)
- **Frontend computations:**
  - All metrics computed per-response (lines 978-982)
  - Results aggregation for CSV export
  - Progress bar management

**Tab 3: Query History** (`tab_history()` lines 1094-1487)
- **Backend endpoints used:**
  - `GET /api/v1/interactions/recent?limit=100` - Get history
  - `GET /api/v1/interactions/{id}` - Get details
  - `DELETE /api/v1/interactions/{id}` - Delete interaction
- **Frontend computations:**
  - Metrics already provided by `InteractionSummary` ✅
  - Client-side filtering (no backend filter params)

---

### Key Findings

✅ **Good News:**
- Backend already has `InteractionSummary` with most metrics:
  - `search_query_count` ✅
  - `source_count` ✅
  - `citation_count` ✅
  - `average_rank` ✅
  - `extra_links_count` ✅
- Well-structured `APIClient` with proper error handling
- Good separation between API schemas and business logic

⚠️ **Needs Work:**
- Frontend computes metrics in multiple places:
  - Lines 227-241: `build_interaction_markdown()`
  - Lines 497-506: `display_response()`
  - Lines 978-982: `tab_batch()`
- Export logic lives entirely in frontend (170 lines)
- Model name normalization in frontend (lines 132-185, 47 lines)
- No pagination for history endpoint
- Large CSS block inline in `app.py` (67 lines)

---

### Frontend-Only Logic to Move

**High Priority:**

1. **Metrics Calculation** (lines 227-241, 497-506, 978-982)
   - `sources_found` - Count of sources from search
   - `sources_used` - Citations with rank (from search results)
   - `avg_rank` - Average citation rank
   - NOTE: Backend has these in `InteractionSummary` but NOT in `SendPromptResponse`
   - **Action:** Add these fields to `SendPromptResponse`, compute on save

2. **Export Logic** (lines 214-334, 170 lines)
   - `build_interaction_markdown()` - 120 lines
   - `format_response_text()` - 50 lines
   - **Action:** Create backend endpoints:
     - `GET /api/v1/interactions/{id}/export/markdown`
     - `GET /api/v1/interactions/export.csv`

3. **Model Display Names** (lines 132-185, 47 lines)
   - `normalize_model_id()` - Special case handling
   - `get_model_display_name()` - Large mapping dict
   - **Action:** Add `model_display_name` field to backend responses
   - **Action:** Create `GET /api/v1/models` endpoint with display names

**Medium Priority:**

4. **History Filtering** (No backend support)
   - Frontend does client-side filtering
   - **Action:** Add query params to `/api/v1/interactions/recent`:
     - `?provider=`, `?model=`, `?search=`, `?data_source=`
     - `?offset=`, `?limit=` (pagination)

5. **Date Formatting** (lines 121-130)
   - `format_pub_date()` - Parse various date formats
   - **Action:** Return ISO 8601 from backend, keep frontend helper

**Low Priority:**

6. **Large Display Function** (lines 456-686, 230 lines)
   - `display_response()` - Too large, needs splitting
   - **Action:** Extract to components (`metrics.py`, `sources.py`, `response.py`)

7. **Inline CSS** (lines 27-93, 67 lines)
   - **Action:** Move to `frontend/styles.py`

---

### Backend API Gaps Identified

**Missing Endpoints:**
1. History filtering & pagination
2. Export endpoints (markdown, CSV)
3. Model information with display names

**Schema Enhancements Needed:**
- Add to `SendPromptResponse`:
  - `sources_found: int`
  - `sources_used: int`
  - `avg_rank: Optional[float]`
  - (Note: `extra_links_count` already exists ✅)

**Deliverable:** ✅ Complete - See findings above

---

## Phase 1 – Centralize Domain Logic in Backend/Core (P1)

**Objective:** Make the backend (or shared core) responsible for metrics, naming, and exports so Streamlit and future React clients are thin renderers.

### 1. Metrics & Summaries in Backend

✅ **COMPLETED** (2025-12-03)

- [x] Extend backend response schemas so `SendPromptResponse` and `InteractionSummary` include:
  - [x] `sources_found` - Total sources from search queries
  - [x] `sources_used` - Citations with rank (from search results)
  - [x] `avg_rank` - Average rank of citations
  - [x] `extra_links` - Already existed in schema
  - [x] `analysis_type` - **Not needed**: `data_source` field already provides this ("api" or "network_log"). Frontend can trivially map for display.
  - [x] Display-ready timestamp - **Working as intended**: Backend returns ISO 8601 timestamps in `created_at`. Frontend has `format_pub_date()` for display formatting. This follows best practice.

- [x] Move calculations currently done in `app.py` (e.g. in `build_interaction_markdown()` and the History tab) into backend services.
  - [x] Metrics now computed in `InteractionService.save_interaction()` (lines 87-101)
  - [x] Stored in database (`Response` model columns: `sources_found`, `sources_used_count`, `avg_rank`)
  - [x] Returned in `get_interaction_details()` (line 267-269)

- [x] Add backend tests that verify these metrics so both Streamlit and React UIs can rely on them.
  - [x] Created `tests/test_metrics_computation.py` with 12 comprehensive tests
  - [x] All 197 backend tests pass

**Files Changed:**
- `backend/app/api/v1/schemas/responses.py` - Added metrics fields to SendPromptResponse (lines 126-145)
- `backend/app/models/database.py` - Added metrics columns to Response model (lines 67-70)
- `backend/app/repositories/interaction_repository.py` - Updated save() to store metrics (lines 44-48, 110-112)
- `backend/app/services/interaction_service.py` - Compute metrics on save (lines 87-101, 267-269)
- `backend/app/core/utils.py` - Updated calculate_average_rank to use getattr (line 92-93)
- `backend/tests/test_metrics_computation.py` - NEW: 12 TDD tests (329 lines)

**Frontend Integration - ✅ COMPLETED** (2025-12-03):
- [x] Updated `build_interaction_markdown()` (lines 227-236) to use backend metrics
  - Now uses `details.get('sources_found')`, `details.get('sources_used')`, `details.get('avg_rank')`
  - Removed manual calculation logic
- [x] Updated `display_response()` (lines 478-495) to use backend metrics
  - Uses `getattr(response, 'sources_found')`, `getattr(response, 'sources_used')`, `getattr(response, 'avg_rank')`
  - Removed all manual counting and calculations
- [x] Updated `tab_batch()` (lines 962-984) to use backend metrics
  - Batch results now use `response_data.get('sources_found')`, etc. for API mode
  - Uses `getattr(response, 'sources_found')`, etc. for network log mode
  - Removed duplicate avg_rank calculations

**Result**: Frontend now displays metrics computed by backend. All frontend calculations removed. Metrics are computed once on save and returned in all API responses.

### 2. Model & Provider Naming - ✅ COMPLETED (2025-12-03)

**Backend Implementation - ✅ COMPLETED**:
- [x] Created `get_model_display_name()` in `backend/app/core/utils.py` (lines 100-160)
  - Maps known model IDs to friendly display names (Claude Sonnet 4.5, GPT-5.1, Gemini 2.5 Flash, etc.)
  - Handles multiple format variants for robustness (e.g., claude-sonnet-4-5-20250929, claude-sonnet-4.5-20250929)
  - Fallback formatting for unknown models (removes date suffixes, capitalizes words)
- [x] Added 14 comprehensive TDD tests in `backend/tests/test_model_display_names.py`
  - Tests for Anthropic, OpenAI, Google, ChatGPT models
  - Tests for unknown models with date suffixes and version numbers
  - All 211 backend tests passing
- [x] Extended API response schemas:
  - Added `model_display_name: Optional[str]` to `SendPromptResponse` (line 122)
  - Added `model_display_name: Optional[str]` to `InteractionSummary` (line 185)
- [x] Updated services to compute and set display names:
  - `InteractionService.get_recent_interactions()` (line 175)
  - `InteractionService.get_interaction_details()` (line 270)
  - `ProviderService.send_prompt()` (line 189)

**Frontend Integration - ✅ COMPLETED**:
- [x] Updated `display_response()` (line 472) to use backend `model_display_name`
- [x] Updated `tab_history()` (line 1119) to use backend `model_display_name` for DataFrame
- [x] Updated model filter dropdown (line 1148) to use backend display names
- [x] Updated `tab_details()` (line 1291) to use backend `model_display_name`
- [x] Removed `normalize_model_id()` and `get_model_display_name()` from frontend (56 lines removed)

**Result**: Backend now provides formatted model display names in all API responses. Frontend removed duplicate 56-line mapping logic. Single source of truth for model name formatting.

### 3. Export Logic - ✅ COMPLETED (2025-12-03)

**Backend Implementation - ✅ COMPLETED**:
- [x] Created `ExportService` class in `backend/app/services/export_service.py` (202 lines)
  - `build_markdown()` method converts interaction data to formatted markdown
  - Handles both API and network_log data sources
  - Uses `format_pub_date()` utility for date formatting
  - Converts reference-style citation links to inline markdown links
- [x] Created export endpoint `GET /api/v1/interactions/{id}/export/markdown`
  - Returns `PlainTextResponse` with `text/markdown` media type
  - Proper error handling (404 for not found, 500 for server errors)
  - Comprehensive OpenAPI documentation with response examples
- [x] Added `format_pub_date()` utility to `backend/app/core/utils.py` (lines 164-184)
  - Converts ISO datetime to friendly format: "Mon, Jan 15, 2024 10:30 UTC"
- [x] Added dependency injection for `ExportService` in `backend/app/dependencies.py`

**Frontend Integration - ✅ COMPLETED**:
- [x] Added `export_interaction_markdown()` method to `APIClient` class
  - Makes GET request to export endpoint
  - Returns plain text markdown (not JSON)
  - Comprehensive error handling (404, 500, timeout, connection errors)
- [x] Updated `app.py` line 1175 to use `api_client.export_interaction_markdown()`
- [x] Removed `build_interaction_markdown()` function from frontend (116 lines removed)
- [x] Kept helper functions `format_response_text()` and `format_pub_date()` as they're still used for UI display

**Testing - ✅ COMPLETED**:
- [x] Backend endpoint tested and working
- [x] API client integration tested and working
- [x] End-to-end export functionality verified

**Result**: Markdown export logic moved to backend. Frontend now calls backend API instead of generating markdown locally. 116 lines of duplicate logic removed from frontend.

### 4. Network-Log Specific Mapping - ✅ COMPLETED (2025-12-03)

**Backend Implementation - ✅ COMPLETED**:
- [x] Updated `InteractionService.get_interaction_details()` to populate `all_sources` for both API and network_log modes
  - API mode: Aggregates sources from all search queries
  - Network_log mode: Uses sources directly from response
  - Provides consistent, pre-aggregated list for frontend
- [x] Updated schema description for `all_sources` field to reflect it's always populated
- [x] Verified all 211 backend tests passing including 4 network_log-specific tests:
  - `test_network_log_mode_all_sources_handling` - API contract test
  - `test_metrics_with_network_log_mode` - metrics computation test
  - `test_network_log_exclusive_fields` - repository test
  - `test_mixed_api_and_network_log_data` - integration test

**Frontend Integration - ✅ COMPLETED**:
- [x] Removed special-case logic for network_log mode in `app.py` (lines 429-436)
  - Previously: Checked `data_source` and gathered sources differently
  - Now: Uses `all_sources` field directly for both modes
- [x] Updated batch tab source handling (lines 614-616)
  - Simplified to use `all_sources` field consistently
- [x] Both API and network_log data now handled uniformly

**Testing - ✅ COMPLETED**:
- [x] All 211 backend tests passing
- [x] API endpoint verified to return `all_sources` field
- [x] Docker container rebuilt and restarted with changes

**Result**: Backend provides consistent, pre-aggregated `all_sources` field for both API and network_log modes. Frontend eliminates special-case logic and treats both data sources uniformly. Most domain logic lives in backend; frontend is a thin renderer over rich JSON responses.

---

## Phase 2 – Streamlit Refactor: Thin Shell + Modules (P2)

**Objective:** Make `app.py` small and comprehensible, with tab-specific modules and minimal, view-only helpers.

### 1. Extract CSS and Create Module Structure - ✅ COMPLETED (2025-12-03)

**Module Structure Created - ✅ COMPLETED**:
- [x] Created `frontend/__init__.py` - root module
- [x] Created `frontend/styles.py` with `load_styles()` function
- [x] Created `frontend/tabs/` directory structure for tab modules
- [x] Moved 65 lines of CSS from app.py to styles module

**Updated app.py - ✅ COMPLETED**:
- [x] Added import: `from frontend.styles import load_styles`
- [x] Replaced inline CSS block with `load_styles()` call
- [x] Reduced app.py from 1418 to 1353 lines (-65 lines)

**Testing - ✅ COMPLETED**:
- [x] Streamlit app tested and functional
- [x] CSS styles loading correctly via module

**Result**: CSS now in dedicated, reusable module. Better separation of concerns and improved maintainability.

### 2. Split `app.py` by Responsibility

- [ ] Keep in `app.py`:
  - Page config and CSS loading (via `load_styles()`).
  - `initialize_session_state()` (slimmed down).
  - `sidebar_info()`.
  - `main()` function that wires tabs.

- [ ] Create tab modules:
  - `frontend/tabs/interactive.py` with `tab_interactive()`.
  - `frontend/tabs/batch.py` with `tab_batch()`.
  - `frontend/tabs/history.py` with `tab_history()`.

### 3. Introduce Minimal UI Helpers

- [ ] `frontend/components/metrics.py`:
  - Functions to render the metrics row given backend-provided metrics (no calculations inside).

- [ ] `frontend/components/sources.py`:
  - Functions to render "Sources Found", "Sources Used", and "Extra Links" using the normalized backend data shape.

- [ ] `frontend/components/response.py`:
  - Response text rendering and related view-level helpers, such as:
    - `sanitize_response_markdown()`.
    - Image extraction and inline display.

### 4. Centralize Frontend Utilities (Thin Only)

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

### 5. Unify Error Handling

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
