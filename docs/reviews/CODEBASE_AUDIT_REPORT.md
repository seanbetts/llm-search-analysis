# Codebase Audit Report
**LLM Search Analysis Project**
**Date:** 2025-12-09
**Auditor:** Claude Sonnet 4.5
**Repository Status:** main branch (clean)

---

## 1. Architecture & Data Flow Summary

The LLM Search Analysis project is a well-architected full-stack application that compares web search capabilities across OpenAI, Google Gemini, and Anthropic Claude providers. The backend is a FastAPI service (~19,300 LOC) with a clean 3-layer architecture: API routes handle HTTP concerns, services implement business logic including provider orchestration and metrics computation, and repositories manage SQLAlchemy ORM operations against SQLite (upgradable to PostgreSQL). The schema centers on an `interactions` model (replacing legacy sessions/prompts) with cascading relationships to responses, search queries, query sources, response sources, and citations. The frontend is a Streamlit application (~5,000 LOC) organized into modular tabs (interactive, batch, history) that consumes the backend via an `httpx`-based API client with connection pooling and retry logic. The system supports dual data collection modes: official provider APIs (95% coverage, 191 tests) and experimental Playwright-based network capture for ChatGPT. Alembic migrations manage schema evolution with 5 revisions covering baseline schema, source table splits, foreign key enforcement, response metrics, and the interactions model. The Docker Compose setup is hybrid—backend runs in a container while frontend runs natively on macOS to avoid ARM64 Chrome emulation issues.

---

## 2. Repository Snapshot

```
llm-search-analysis/
├── README.md                           # Project overview, quickstart, docs map
├── CONTRIBUTING.md                     # Contribution guidelines
├── pyproject.toml                      # Ruff/pytest config, Python 3.11+ requirement
├── Makefile                           # Dev commands: lint, test, format, clean
├── docker-compose.yml                 # Hybrid deployment (backend only)
├── .env.example                       # Comprehensive env var template
├── .gitignore                         # Properly excludes .env, *.db, logs, sessions
│
├── app.py                             # Streamlit entry point
├── requirements.txt                   # Frontend deps (Streamlit, Playwright, SDKs)
├── Dockerfile                         # Frontend image (commented out in compose)
│
├── backend/
│   ├── requirements.txt               # FastAPI, SQLAlchemy, Alembic, SDKs, pytest
│   ├── Dockerfile                     # Production-ready backend image
│   ├── alembic.ini                    # Migration config
│   ├── pytest.ini                     # Test configuration
│   │
│   ├── app/
│   │   ├── main.py                    # FastAPI app, middleware, exception handlers
│   │   ├── config.py                  # Pydantic Settings with validation
│   │   ├── dependencies.py            # Dependency injection chain
│   │   │
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── interactions.py    # POST /send, GET /recent, GET /{id}, DELETE
│   │   │   │   └── providers.py       # GET /providers, GET /providers/models
│   │   │   └── schemas/
│   │   │       ├── requests.py        # Pydantic request models
│   │   │       └── responses.py       # Pydantic response models
│   │   │
│   │   ├── core/
│   │   │   ├── exceptions.py          # Custom exception hierarchy
│   │   │   ├── middleware.py          # Logging, correlation IDs
│   │   │   ├── utils.py              # Model normalization, domain extraction
│   │   │   ├── json_schemas.py        # Metadata validation with Pydantic
│   │   │   └── provider_schemas.py    # Raw response payload validation
│   │   │
│   │   ├── models/
│   │   │   └── database.py            # SQLAlchemy ORM (7 tables)
│   │   │
│   │   ├── repositories/
│   │   │   └── interaction_repository.py  # Data access with eager loading
│   │   │
│   │   └── services/
│   │       ├── interaction_service.py     # Business logic, metrics computation
│   │       ├── provider_service.py        # Provider orchestration
│   │       ├── export_service.py          # Markdown export
│   │       └── providers/
│   │           ├── base_provider.py       # Abstract base class
│   │           ├── provider_factory.py    # Factory pattern with model mapping
│   │           ├── openai_provider.py     # Responses API integration
│   │           ├── google_provider.py     # Gemini Search Grounding
│   │           └── anthropic_provider.py  # Claude web_search tool
│   │
│   ├── migrations/
│   │   ├── env.py                         # Alembic environment
│   │   └── versions/
│   │       ├── 1058847fd4ba_baseline_schema.py
│   │       ├── 1faa14f77fa5_split_sources_tables.py
│   │       ├── 4aae0231e6df_enforce_fk_constraints_and_indexes.py
│   │       ├── 8564cf28ae1f_add_response_metrics_columns.py
│   │       └── 9b9f1c6a2e3f_add_interactions_table.py
│   │
│   ├── tests/                             # 191 tests, 95% coverage, 13,239 LOC
│   │   ├── conftest.py                    # Fixtures, test DB setup
│   │   ├── test_api.py                    # Endpoint tests
│   │   ├── test_api_contracts.py          # Schema validation tests
│   │   ├── test_integration_database.py   # Edge case/messy data tests
│   │   ├── test_openai_provider.py        # OpenAI provider tests
│   │   ├── test_google_provider.py        # Google provider tests
│   │   ├── test_anthropic_provider.py     # Anthropic provider tests
│   │   ├── test_provider_factory.py       # Factory tests
│   │   ├── test_provider_service.py       # Service tests
│   │   ├── test_repository.py             # Repository tests
│   │   ├── test_service.py                # Business logic tests
│   │   ├── test_exception_handlers.py     # Error handling tests
│   │   ├── test_provider_sdk_validation.py # SDK schema validation
│   │   ├── test_provider_payload_schemas.py # Raw payload validation
│   │   ├── test_e2e_persistence.py        # Live API tests (RUN_E2E=1)
│   │   ├── test_metrics_computation.py    # Metric calculations
│   │   ├── test_roundtrip_persistence.py  # Save/retrieve integrity
│   │   └── fixtures/
│   │       └── provider_payloads.py       # Canonical response samples
│   │
│   └── data/                              # Data directory (gitignored)
│       └── llm_search.db                  # SQLite database
│
├── frontend/
│   ├── api_client.py                      # httpx client with retries
│   ├── config.py                          # Frontend configuration
│   ├── styles.py                          # CSS injection
│   ├── utils.py                           # Formatting utilities
│   │
│   ├── tabs/
│   │   ├── interactive.py                 # Single prompt, network mode
│   │   ├── batch.py                       # Prompt×model matrix
│   │   └── history.py                     # Recent interactions viewer
│   │
│   ├── components/
│   │   ├── response.py                    # Display helpers
│   │   └── models.py                      # Model metadata
│   │
│   ├── helpers/
│   │   ├── error_handling.py              # Streamlit error display
│   │   ├── metrics.py                     # Metric formatting
│   │   └── serialization.py               # Data conversion
│   │
│   ├── network_capture/
│   │   ├── base_capturer.py               # Abstract capturer
│   │   ├── browser_manager.py             # Playwright management
│   │   ├── chatgpt_capturer.py           # ChatGPT network capture (~1,300 LOC)
│   │   └── parser.py                      # Network log parser
│   │
│   └── tests/                             # Frontend tests
│       ├── test_api_client.py
│       ├── test_response_components.py
│       ├── test_network_parser.py
│       ├── test_history_filters.py
│       ├── test_helpers_misc.py
│       └── fixtures/
│           └── send_prompt_responses.py
│
├── docs/
│   ├── backend/
│   │   ├── OVERVIEW.md                    # Architecture, schema, patterns
│   │   ├── API_DOCUMENTATION.md           # Endpoint reference
│   │   └── TESTING.md                     # Test strategy
│   │
│   ├── frontend/
│   │   ├── OVERVIEW.md                    # Frontend architecture
│   │   ├── TESTING.md                     # UI test coverage
│   │   └── NETWORK_CAPTURE.md             # Playwright guide
│   │
│   ├── operations/
│   │   ├── ENVIRONMENT_VARIABLES.md       # Comprehensive env var docs
│   │   └── BACKUP_AND_RESTORE.md          # DB maintenance
│   │
│   ├── research/
│   │   └── LLM_SEARCH_FINDINGS.md         # Research insights
│   │
│   ├── proposals/
│   │   ├── LIVE_NETWORK_LOGS_PLAN.md      # Streaming capture design
│   │   └── LANGUAGE_CLASSIFIER_EXTENSION.md
│   │
│   ├── archive/                           # Historical plans
│   │   ├── FASTAPI_IMPLEMENTATION_PLAN.md
│   │   ├── DEVELOPMENT_PLAN.md
│   │   ├── FRONTEND_REFACTOR_PLAN.md
│   │   └── DOCSTRING_STANDARDIZATION_PLAN.md
│   │
│   └── reviews/
│       └── CODEBASE_AUDIT.md              # This document
│
└── scripts/
    ├── verify-docker-setup.sh
    ├── start-hybrid.sh
    └── run_all_tests.sh
```

---

## 3. Top 10 Findings

### 1. SQLite Concurrency Risk in Production
**Severity:** High
**Impact:** `backend/app/dependencies.py`, `backend/app/config.py`
**Issue:** SQLite is the default database with `check_same_thread=False`, which allows multi-threaded access but doesn't prevent write contention. Under load (multiple simultaneous POST requests), this causes "database is locked" errors.
**Remediation:** Add explicit guidance in `docs/operations/` for migrating to PostgreSQL in production, or implement write queue pattern for SQLite.

### 2. API Keys Logged in Debug Mode
**Severity:** High
**Impact:** `backend/app/dependencies.py:42`
**Issue:** `echo=settings.DEBUG` enables SQLAlchemy query logging which may log API keys from HTTP headers or query parameters during debugging.
**Remediation:** Disable SQLAlchemy echo unconditionally in production (set `echo=False` always) and add explicit warning in `.env.example` about DEBUG mode security implications.

### 3. Missing Rate Limiting
**Severity:** High
**Impact:** All API endpoints in `backend/app/api/v1/endpoints/`
**Issue:** No rate limiting middleware exists. A malicious user can spam `/api/v1/interactions/send` causing excessive LLM provider API costs.
**Remediation:** Implement `slowapi` or FastAPI rate limiting middleware with per-IP limits (e.g., 10 requests/minute for `/send`).

### 4. Hardcoded Database URL in alembic.ini
**Severity:** Medium
**Impact:** `backend/alembic.ini:64`
**Issue:** `sqlalchemy.url = sqlite:///./data/llm_search.db` is hardcoded, requiring manual edits for PostgreSQL migrations. This is error-prone during deployment.
**Remediation:** Modify `backend/migrations/env.py` to read from `settings.DATABASE_URL` instead of `alembic.ini`, matching runtime configuration.

### 5. Incomplete Input Sanitization for Network Log Mode
**Severity:** Medium
**Impact:** `backend/app/api/v1/endpoints/interactions.py` (POST `/save-network-log`)
**Issue:** The `/save-network-log` endpoint accepts arbitrary JSON in `raw_response`, `search_queries`, and `metadata` fields. While Pydantic validates structure, there's no size limit on these payloads. A malicious frontend could submit multi-MB JSON blobs causing memory exhaustion.
**Remediation:** Add `max_length` constraints in Pydantic schemas for JSON fields (e.g., 1MB limit) and validate total request body size in middleware.

### 6. Frontend API Client Stores Credentials in Session State
**Severity:** Medium
**Impact:** `app.py:46-53`, `frontend/config.py`
**Issue:** `CHATGPT_PASSWORD` from environment variables is accessible in Streamlit's `st.session_state` indirectly through config. While not directly exposed, this increases attack surface if XSS vulnerability exists.
**Remediation:** Pass credentials only when needed (not in session state), and implement credential rotation policy documented in operations docs.

### 7. Missing Index on interactions.deleted_at
**Severity:** Medium
**Impact:** `backend/app/models/database.py:37`
**Issue:** The `deleted_at` column (soft delete pattern) lacks an index. Queries filtering `WHERE deleted_at IS NULL` will perform full table scans as the dataset grows.
**Remediation:** Create a new Alembic migration adding `Index("ix_interactions_deleted_at", "deleted_at")` for soft-delete queries.

### 8. Test Coverage Gaps in Network Capture Module
**Severity:** Medium
**Impact:** `frontend/network_capture/chatgpt_capturer.py` (~1,300 LOC)
**Issue:** The ChatGPT network capture module has minimal test coverage (only parser tests exist). The complex Playwright automation, WebSocket handling, and session management are untested, risking breakage on ChatGPT UI updates.
**Remediation:** Add integration tests with mocked Playwright responses to validate capture flow, error handling, and session persistence.

### 9. Potential Memory Leak in API Client
**Severity:** Low
**Impact:** `frontend/api_client.py:93-96`
**Issue:** The `__del__` method closes the httpx client, but Python's GC may not call it promptly. In long-running Streamlit sessions with many API calls, unclosed connections may accumulate.
**Remediation:** Implement context manager protocol (`__enter__`/`__exit__`) and update frontend to use `with APIClient() as client:` pattern.

### 10. Incomplete Error Context in Provider Errors
**Severity:** Low
**Impact:** `backend/app/services/providers/openai_provider.py:94`, similar in other providers
**Issue:** Provider error messages like `"OpenAI API error: {str(e)}"` don't include correlation IDs or request context, making debugging customer issues difficult.
**Remediation:** Enhance exception handlers in provider modules to include correlation ID from request context (requires passing Request object through service layer).

---

## 4. Section Reviews

### 4.1 Backend (FastAPI)

**Strengths:**
- **Excellent architecture:** Clean 3-layer separation (API → Service → Repository) with proper dependency injection via FastAPI's `Depends()`. Repository pattern prevents N+1 queries with `joinedload()`.
- **Comprehensive error handling:** Custom exception hierarchy (`APIException` → domain-specific errors) with consistent JSON error responses, correlation IDs, and proper HTTP status codes.
- **High test coverage:** 95% coverage with 191 tests including unit, integration, contract, and database edge case tests. Contract tests would have caught historical bugs (commits 974518c, 6473e54).
- **Strong typing:** Pydantic v2 for all request/response schemas with custom validators. Type hints throughout codebase improve IDE support and catch errors early.
- **Provider abstraction:** `BaseProvider` ABC enforces consistent interface. Factory pattern with `MODEL_PROVIDER_MAP` makes adding new providers straightforward.
- **Observability:** Structured logging with correlation IDs, request/response logging middleware, and DEBUG mode for troubleshooting.

**Weaknesses / Risks:**
- **SQLite production risk:** Default `check_same_thread=False` enables multi-threading but write contention causes "database is locked" errors under load. No migration path to PostgreSQL documented in production guides.
- **No rate limiting:** Endpoint `/api/v1/interactions/send` is unprotected. Malicious users can spam expensive LLM API calls causing financial damage.
- **Debug mode security:** `echo=settings.DEBUG` in `dependencies.py` logs SQL queries including potential secrets. No warnings in docs about disabling DEBUG in production.
- **Missing API versioning deprecation strategy:** API is v1 but no plan for v2 introduction or backward compatibility handling.
- **Incomplete provider SDK error handling:** Some provider integrations (especially Google's redirect resolution) lack timeout handling. Network delays could hang requests indefinitely.

**Suggested Improvements:**
1. **Add rate limiting middleware:** Implement `slowapi` with Redis backend for distributed rate limiting (10 req/min for `/send`, 100 req/min for read endpoints).
2. **PostgreSQL migration guide:** Create `docs/operations/POSTGRESQL_MIGRATION.md` with step-by-step Alembic migration, connection pooling config, and performance tuning.
3. **API key rotation:** Document API key rotation policy and implement health checks that alert on provider credential expiry (e.g., OpenAI key approaching usage limits).
4. **Async provider calls:** Current synchronous provider calls block the event loop. Refactor to `async def send_prompt()` using `httpx.AsyncClient` for better throughput.
5. **Metrics endpoint:** Add `/metrics` endpoint (Prometheus format) for request counts, response times, provider error rates, and database query latency.

---

### 4.2 SQLite Database & Migrations

**Observed Schema:**
The schema centers on `InteractionModel` (replacing legacy sessions/prompts) with cascading deletes:
- **providers** (id, name, display_name, is_active, created_at)
- **interactions** (id, provider_id FK, model_name, prompt_text, data_source, created_at, updated_at, deleted_at, metadata_json)
  - Indexes: created_at, provider_id, data_source
- **responses** (id, interaction_id FK CASCADE, response_text, response_time_ms, raw_response_json, data_source, extra_links_count, sources_found, sources_used_count, avg_rank)
- **search_queries** (id, response_id FK, search_query, order_index, internal_ranking_scores JSON, query_reformulations JSON)
- **query_sources** (id, search_query_id FK, url, title, domain, rank, snippet_text, metadata_json)
- **response_sources** (id, response_id FK, url, title, domain, rank, snippet_text, metadata_json) — for network_log mode
- **sources_used** (id, response_id FK, query_source_id FK nullable, response_source_id FK nullable, url, title, rank, snippet_used, citation_confidence, metadata_json)
  - CHECK constraint: only one of query_source_id or response_source_id can be set

**Migration Gaps / Drift:**
- **Alembic config drift:** `alembic.ini` hardcodes `sqlalchemy.url`, but runtime uses `settings.DATABASE_URL`. This causes confusion during migrations if `.env` differs from `alembic.ini`.
- **No down migrations tested:** Migration files have `downgrade()` functions but no CI tests verify reversibility. Rollbacks may fail.
- **Missing migration for deleted_at index:** Soft delete pattern exists (`interactions.deleted_at`) but no index, causing slow queries as data grows.
- **JSON column validation:** `metadata_json`, `raw_response_json`, `internal_ranking_scores`, and `query_reformulations` are unvalidated at schema level. Corrupt JSON can be inserted.

**Query / Indexing Risks:**
- **Soft delete performance:** Queries filter `WHERE deleted_at IS NULL` without index, causing full table scans.
- **Citation queries:** No compound index on `sources_used(response_id, rank)`. Queries computing average rank will degrade as citations grow.
- **JSON field queries:** SQLite's JSON functions (like `json_extract`) are slow without covering indexes. No indexes on commonly queried JSON paths.
- **Cascade delete performance:** Deleting an interaction cascades to 6 child tables. Without proper indexing on foreign keys, this causes sequential scans.

**Suggested Improvements:**
1. **Add missing indexes:**
   ```sql
   CREATE INDEX ix_interactions_deleted_at ON interactions(deleted_at);
   CREATE INDEX ix_sources_used_response_rank ON sources_used(response_id, rank);
   ```
2. **Alembic config fix:** Modify `backend/migrations/env.py` to read `DATABASE_URL` from settings, ignoring `alembic.ini`. Document this change.
3. **Migration testing:** Add CI step to test up/down migrations on sample data, verifying idempotency and data preservation.
4. **JSON schema validation:** Add `CHECK` constraints or application-level validation (in `InteractionService`) to reject malformed JSON blobs before persistence.
5. **PostgreSQL readiness:** Test schema migration to PostgreSQL (JSONB vs JSON, different index strategies). Document differences in `docs/operations/`.

---

### 4.3 Provider Integrations (Anthropic, OpenAI, Google, factories and validation)

**Strengths:**
- **Clean abstraction:** `BaseProvider` ABC enforces `get_provider_name()`, `get_supported_models()`, `send_prompt()`, and `validate_model()`. All providers implement this interface consistently.
- **Factory pattern:** `ProviderFactory` with `MODEL_PROVIDER_MAP` allows model-based provider selection (e.g., `"gpt-5.1"` → `OpenAIProvider`). Adding new providers requires minimal changes.
- **Canonical fixtures:** `backend/tests/fixtures/provider_payloads.py` contains real provider response samples, validated by `test_provider_payload_schemas.py`. This catches SDK breaking changes early.
- **SDK validation tests:** `test_provider_sdk_validation.py` verifies SDK responses parse correctly before provider-specific logic, isolating compatibility issues.
- **Response normalization:** All providers return `ProviderResponse` dataclass with `search_queries`, `citations`, `sources`, ensuring frontend receives consistent schema.

**Weaknesses:**
- **Google redirect handling fragility:** `google_provider.py` resolves Google redirect URLs (`vertexaisearch.cloud.google.com`) synchronously with `requests.head()`. This lacks timeout, retry logic, and error handling. Network issues cause endpoint hangs.
- **Anthropic/Google network capture TODOs:** `frontend/network_capture/parser.py` has `TODO: Implement Claude-specific parsing` and `TODO: Implement Gemini-specific parsing` comments. Network capture only works for ChatGPT.
- **Provider error context loss:** When a provider raises an exception, the error message doesn't include correlation ID or original prompt, making debugging difficult.
- **No circuit breaker pattern:** If OpenAI API is down, every request retries indefinitely. No fast-fail or circuit breaker to prevent cascading failures.
- **API key validation delayed:** Keys are only validated when a request is made. Invalid keys cause runtime errors instead of startup warnings.

**Suggested Improvements:**
1. **Async provider calls with timeouts:**
   ```python
   async def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
       async with httpx.AsyncClient(timeout=30.0) as client:
           response = await client.post(...)
   ```
2. **Implement circuit breaker:** Use `pybreaker` library to fail-fast when provider is consistently erroring (e.g., after 5 failures in 60s, open circuit for 5 minutes).
3. **Startup API key validation:** In `app/main.py` startup event, make test calls to each configured provider to validate keys. Log warnings for invalid keys.
4. **Complete network capture:** Implement Anthropic and Google parsers in `network_capture/parser.py` or document limitations in `docs/frontend/NETWORK_CAPTURE.md`.
5. **Enhanced error context:** Pass `Request` object through service layer to include correlation ID in provider exceptions.

---

### 4.4 Frontend (Streamlit & frontend package)

**UX / Structure Findings:**
- **Positive:**
  - Clean tab separation (Interactive, Batch, History) with minimal shared state beyond `st.session_state`.
  - API client abstraction (`frontend/api_client.py`) isolates backend communication with retries and error handling.
  - Responsive error messages with `frontend/helpers/error_handling.py` providing consistent Streamlit `st.error()` formatting.
  - Network capture mode toggle in sidebar with clear experimental warning.
  - Comprehensive sidebar metrics documentation educating users on "Sources Found vs. Sources Used vs. Extra Links."

- **Issues:**
  - **Session state bloat:** `st.session_state` stores entire response objects (`response`, `batch_results`), which grow unbounded. Long sessions risk memory exhaustion.
  - **No pagination in History tab:** History loads all interactions at once. With 10,000+ interactions, this causes slow rendering and OOM errors.
  - **Network capture UX confusion:** Browser automation runs synchronously, blocking Streamlit for 30-60 seconds with no progress indicator. Users think app is frozen.
  - **No batch operation cancellation:** Batch mode runs all prompt×model combinations sequentially. No cancel button if user starts a 20-prompt × 3-model job.

**Code Organisation Risks:**
- **Monolithic `chatgpt_capturer.py`:** 1,300 LOC in a single file with complex Playwright automation, WebSocket handling, and session management. Hard to maintain and untested.
- **Hardcoded CSS:** `frontend/styles.py` injects CSS via `st.markdown()`. Changes require code edits instead of theme files.
- **Tight coupling to backend schema:** Frontend components directly reference backend response fields (e.g., `response['search_queries'][0]['sources']`). Schema changes break frontend silently.
- **No state persistence:** Closing browser loses all session state. Users can't bookmark or share analysis URLs.

**Suggested Improvements:**
1. **Implement pagination:** Use backend's `/recent?page=1&page_size=20` in History tab with "Load More" button.
2. **Async network capture with progress:** Use `st.spinner()` and Playwright's event callbacks to show progress (e.g., "Navigating to ChatGPT...", "Submitting prompt...", "Capturing response...").
3. **Batch cancellation:** Add cancel button using `st.stop()` and cleanup logic to abort in-progress batch operations.
4. **Refactor `chatgpt_capturer.py`:** Split into classes: `ChatGPTAuthenticator`, `ChatGPTPrompter`, `ResponseCapturer`, `NetworkParser`. Add integration tests.
5. **URL state persistence:** Use Streamlit's `st.experimental_get_query_params()` / `st.experimental_set_query_params()` to encode selected interaction ID in URL, enabling bookmarking.

---

### 4.5 Testing & Quality

**Coverage Strength:**
- **Backend: 95% with 191 tests, 13,239 LOC of test code:**
  - Unit tests for all providers, services, repositories with mocked dependencies.
  - Integration tests (`test_integration_database.py`) with messy/corrupt data scenarios (NULL foreign keys, broken relationships, orphaned records).
  - Contract tests (`test_api_contracts.py`) validating API response schemas match frontend expectations, preventing `'NoneType' object is not iterable` bugs.
  - E2E tests (`test_e2e_persistence.py`) with real provider APIs (gated by `RUN_E2E=1`).
  - Metrics computation tests verifying average rank, source counts, and citation classification.
  - SDK validation tests (`test_provider_sdk_validation.py`) ensuring provider SDK responses parse correctly.

- **Frontend: Partial coverage (~30%):**
  - API client tests with `respx` mocks.
  - Component/helper tests for formatting functions.
  - **Missing:** No Streamlit UI tests (experimental `AppTest` not used), no network capture integration tests.

**Blind Spots:**
1. **Network capture module:** `chatgpt_capturer.py` (~1,300 LOC) has no integration tests. Playwright automation, WebSocket handling, session persistence untested.
2. **Concurrent request handling:** No load tests verifying SQLite handles simultaneous writes. "Database is locked" errors only manifest under production load.
3. **Migration reversibility:** No tests for `downgrade()` functions in Alembic migrations. Rollbacks may fail silently.
4. **Large payload handling:** No tests for multi-MB `raw_response` or 1000+ citation responses. Memory/performance characteristics unknown.
5. **Error recovery paths:** Provider timeout/retry logic lacks tests. Circuit breaker behavior (if implemented) untested.

**Five Specific Tests to Add Next:**

1. **Load test for concurrent writes:**
   ```python
   # test_load_database.py
   def test_concurrent_prompt_submissions(test_db):
       """Verify SQLite handles 10 simultaneous POST /send without 'database is locked' errors."""
       import concurrent.futures
       with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
           futures = [executor.submit(send_prompt, f"Prompt {i}") for i in range(10)]
           results = [f.result() for f in futures]
       assert all(r.status_code == 200 for r in results)
   ```

2. **Network capture authentication failure test:**
   ```python
   # test_chatgpt_capturer.py
   def test_chatgpt_login_failure_with_invalid_credentials():
       """Verify ChatGPTCapturer raises AuthenticationError with clear message on invalid password."""
       capturer = ChatGPTCapturer(email="test@example.com", password="wrong")
       with pytest.raises(AuthenticationError, match="Login failed: Invalid credentials"):
           capturer.capture_prompt("test")
   ```

3. **Alembic migration reversibility test:**
   ```python
   # test_migrations.py
   def test_migration_reversibility():
       """Verify all migrations can upgrade and downgrade without data loss."""
       # Insert test data at revision N
       # Upgrade to N+1
       # Downgrade to N
       # Verify test data still intact and schema matches
   ```

4. **Provider timeout handling test:**
   ```python
   # test_provider_timeouts.py
   def test_openai_timeout_raises_timeout_error():
       """Verify OpenAIProvider raises TimeoutError after 30s with no response."""
       with patch('openai.Client.responses.create', side_effect=TimeoutError):
           provider = OpenAIProvider("test-key")
           with pytest.raises(TimeoutError, match="OpenAI API timed out"):
               provider.send_prompt("test", "gpt-5.1")
   ```

5. **Large payload memory test:**
   ```python
   # test_large_payloads.py
   def test_save_interaction_with_10000_citations():
       """Verify system handles 10,000 citations without OOM or significant slowdown."""
       citations = [{"url": f"https://example.com/{i}", "title": f"Source {i}"} for i in range(10000)]
       response_id = save_interaction(..., citations=citations)
       retrieved = get_interaction_details(response_id)
       assert len(retrieved.citations) == 10000
       # Verify memory usage stays under 500MB (requires memory profiling)
   ```

---

### 4.6 Tooling, Docker & Operational Model

**Observations on scripts, compose usage, run lifecycle:**
- **Docker Compose hybrid model:** Backend runs in container, frontend runs natively on macOS to avoid ARM64 Chrome issues. Well-documented in `docker-compose.yml` comments and README.
- **Comprehensive scripts:**
  - `scripts/verify-docker-setup.sh` – health checks for backend, frontend, database, API keys.
  - `scripts/start-hybrid.sh` – orchestrates Docker backend + native Streamlit frontend.
  - `scripts/run_all_tests.sh` – runs backend + frontend tests sequentially.
- **Makefile targets:** `make lint`, `make test-backend`, `make test-frontend`, `make format`, `make clean` for common dev tasks.
- **Alembic migrations:** Run manually (`alembic upgrade head`) in backend container or via script. Not automated in Docker entrypoint.
- **Environment configuration:** Comprehensive `.env.example` with deployment mode sections (Docker vs. Local). Clear documentation in `docs/operations/ENVIRONMENT_VARIABLES.md`.

**Risks:**
- **No automated migrations on startup:** Backend container doesn't run `alembic upgrade head` in entrypoint. Fresh deployments start with empty database, causing 500 errors until migrations run manually.
- **Frontend-backend version coupling:** No API versioning. Frontend assumes latest backend schema. Deploying mismatched versions causes runtime errors.
- **Docker volume backup manual:** `docs/operations/BACKUP_AND_RESTORE.md` describes manual backup (`docker cp`). No automated daily backups configured.
- **No health check for frontend:** `docker-compose.yml` has backend health check but frontend service is commented out. Can't verify full stack health.
- **Log rotation missing:** Application logs (`LOG_LEVEL=DEBUG`) grow unbounded. No `logrotate` config for production.

**Suggested Improvements:**
1. **Automated migrations in entrypoint:**
   ```dockerfile
   # backend/Dockerfile
   CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
   ```
2. **API versioning:** Add `/api/v2/` routes for breaking changes. Keep v1 active for 6 months with deprecation warnings.
3. **Automated backups:** Add cron job in backend container or compose service:
   ```yaml
   backup:
     image: alpine
     volumes:
       - ./backend/data:/data
     command: sh -c "while true; do cp /data/llm_search.db /data/backups/llm_search_$(date +%Y%m%d_%H%M%S).db; sleep 86400; done"
   ```
4. **Frontend Docker image:** Fix ARM64 Chrome issues by using remote Chrome (CDP over network) or platform-specific images. Re-enable frontend in compose.
5. **Monitoring stack:** Add `prometheus` + `grafana` services to compose for metrics visualization (request rates, error rates, database size).

---

## 5. Suggested Improvement Roadmap

### Phase 1 — Quick Wins (under 1 day)

1. **Add missing database indexes**
   Create Alembic migration for `ix_interactions_deleted_at` and `ix_sources_used_response_rank`. Deploy immediately to prevent query degradation.

2. **Disable SQLAlchemy echo in production**
   Change `backend/app/dependencies.py:42` to `echo=False` unconditionally. Add `.env.example` warning about DEBUG mode logging secrets.

3. **Fix Alembic config drift**
   Modify `backend/migrations/env.py` to read `settings.DATABASE_URL` instead of hardcoded `alembic.ini` URL. Document change in migration guide.

4. **Add rate limiting to /send endpoint**
   Install `slowapi`, configure 10 req/min limit for `/api/v1/interactions/send`. Prevents cost overruns from malicious spam.

5. **Implement API client context manager**
   Add `__enter__`/`__exit__` to `frontend/api_client.py`. Update frontend tabs to use `with APIClient() as client:` pattern, fixing potential connection leaks.

6. **Add pagination to History tab**
   Use backend's `/recent?page=X` endpoint in `frontend/tabs/history.py`. Add "Load More" button to prevent OOM with large datasets.

### Phase 2 — Structural Improvements

1. **Migrate to async providers with timeouts**
   Refactor all provider `send_prompt()` methods to `async def` using `httpx.AsyncClient`. Add 30-second timeouts and proper error handling. Prevents hung requests.

2. **Implement circuit breaker pattern**
   Use `pybreaker` library for each provider. After 5 consecutive failures, fail-fast for 5 minutes. Add metrics endpoint to expose circuit state.

3. **PostgreSQL migration guide**
   Create `docs/operations/POSTGRESQL_MIGRATION.md` with Alembic migration, connection pooling (SQLAlchemy `pool_size=10`), and JSONB index examples.

4. **Refactor network capture module**
   Split `chatgpt_capturer.py` into separate classes: `Authenticator`, `Prompter`, `ResponseCapturer`, `Parser`. Add integration tests with mocked Playwright.

5. **Add automated database backups**
   Create Docker Compose service that runs daily backups via cron, stores 7-day rolling backups with timestamps. Document restore procedure.

6. **Implement startup API key validation**
   Add FastAPI startup event (`@app.on_event("startup")`) that tests each configured provider key with lightweight API call. Log warnings for invalid keys.

### Phase 3 — Nice-to-Haves

1. **Add Prometheus metrics endpoint**
   Implement `/metrics` with `prometheus-fastapi-instrumentator`. Track request counts, response times, provider error rates, database query latency.

2. **Implement API versioning**
   Add `/api/v2/` routes for breaking changes. Keep v1 active with deprecation headers (`Deprecated: true, Sunset: 2026-06-01`) for 6-month transition.

3. **Build Grafana dashboard**
   Add `prometheus` + `grafana` services to `docker-compose.yml`. Create dashboard with panels for request rates, error rates, database size, provider SLA.

4. **Add Streamlit URL state persistence**
   Use `st.experimental_set_query_params({"interaction_id": 123})` to encode selected interaction in URL. Enables bookmarking and sharing.

5. **Implement live network capture streaming**
   Follow `docs/proposals/LIVE_NETWORK_LOGS_PLAN.md` to stream Playwright events to Streamlit via WebSocket. Add fourth tab for real-time capture visualization.

6. **Complete Anthropic/Google network capture**
   Implement TODO parsers in `frontend/network_capture/parser.py` for Claude and Gemini. Test against live ChatGPT-style network logs.

---

## 6. Appendix

### A. Migration Checklist for PostgreSQL

When migrating from SQLite to PostgreSQL:

1. **Schema compatibility:**
   - Change `JSON` columns to `JSONB` for better performance.
   - Update indexes: SQLite doesn't support partial indexes; PostgreSQL does (`WHERE deleted_at IS NULL`).
   - Test foreign key cascade deletes (behavior differs slightly).

2. **Connection pooling:**
   ```python
   # backend/app/dependencies.py
   engine = create_engine(
       settings.DATABASE_URL,
       pool_size=10,
       max_overflow=20,
       pool_pre_ping=True,  # Verify connections before use
       pool_recycle=3600     # Recycle connections every hour
   )
   ```

3. **Alembic migration:**
   ```bash
   # Export data from SQLite
   sqlite3 data/llm_search.db .dump > backup.sql

   # Edit alembic.ini or env.py to point to PostgreSQL
   export DATABASE_URL="postgresql://user:pass@localhost/llm_search"

   # Run migrations
   alembic upgrade head

   # Import data (requires schema translation)
   ```

4. **Performance tuning:**
   - Enable query plan logging: `log_statement = 'all'` in `postgresql.conf`.
   - Add JSONB GIN indexes for commonly queried JSON paths:
     ```sql
     CREATE INDEX idx_raw_response_metadata ON responses USING GIN (raw_response_json);
     ```

### B. Security Hardening Checklist

- [ ] Remove `DEBUG=true` from `.env` in production
- [ ] Set `CORS_ORIGINS` to specific frontend domain (not `*`)
- [ ] Implement rate limiting on all POST endpoints
- [ ] Add request body size limits (max 10MB)
- [ ] Rotate API keys quarterly and update `.env`
- [ ] Enable HTTPS with TLS 1.3 minimum (use reverse proxy like nginx)
- [ ] Add Content Security Policy headers
- [ ] Implement audit logging for destructive operations (DELETE, UPDATE)
- [ ] Set up alerts for unusual API usage patterns (e.g., 100+ requests from single IP)
- [ ] Review `.gitignore` to ensure no secrets committed

### C. Endpoint Summary Table

| Method | Endpoint | Purpose | Auth | Rate Limit |
|--------|----------|---------|------|------------|
| GET | `/` | API info | None | - |
| GET | `/health` | Health check | None | - |
| GET | `/api/v1/providers` | List providers | None | - |
| GET | `/api/v1/providers/models` | List models | None | - |
| POST | `/api/v1/interactions/send` | Send prompt | None | **Missing** |
| POST | `/api/v1/interactions/save-network-log` | Save network data | None | **Missing** |
| GET | `/api/v1/interactions/recent` | List interactions | None | - |
| GET | `/api/v1/interactions/{id}` | Get details | None | - |
| GET | `/api/v1/interactions/{id}/export/markdown` | Export markdown | None | - |
| DELETE | `/api/v1/interactions/{id}` | Delete interaction | None | **Missing** |

### D. Key Dependencies with Security Notes

| Package | Version | Security Notes |
|---------|---------|----------------|
| fastapi | 0.115.5 | Keep updated; check CVE-2024-XXXXX advisories |
| sqlalchemy | 2.0.36 | No known vulnerabilities |
| openai | 2.8.1 | Contains API keys; never log |
| anthropic | 0.42.0 | Contains API keys; never log |
| google-genai | 1.7.0 | Contains API keys; never log |
| playwright | >=1.40.0 | Browser automation; sandbox untrusted input |
| streamlit | >=1.30.0 | XSS risk if rendering untrusted HTML |
| httpx | 0.28.1 | SSRF risk if URL not validated |

**Recommendation:** Run `pip-audit` or `safety check` monthly to detect vulnerable dependencies.

---

**End of Audit Report**
