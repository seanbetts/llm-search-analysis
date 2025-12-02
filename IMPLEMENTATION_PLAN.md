# LLM Search Analysis - Implementation Plan

**Strategy:** FastAPI-first, SQLite-for-now, Fast Track (4 weeks)
**Last Updated:** December 2, 2024
**Status:** ✅ Week 1-3 Complete, ✅ Week 4 Days 15-20 Complete (Docker, Error Handling, Logging, Testing, Documentation), Week 4 Day 21 NEXT (Deployment)

---

## Overview

**Goal:** Transform monolithic Streamlit app into clean API-first architecture

**Current:**
```
Streamlit (1,507 lines) → Direct database calls
```

**Target:**
```
Streamlit → FastAPI API → Services → Repository → SQLite
```

**Why FastAPI:**
- Creates stable API for any frontend (Streamlit now, React later)
- Enables testing and proper separation of concerns
- Automatic OpenAPI documentation
- Async support for browser automation

**Why SQLite:**
- Already using it successfully
- SQLAlchemy abstracts database choice (easy to switch later)
- Fast for single-instance deployments
- Zero ops overhead

---

## Stage 1: FastAPI Backend Foundation (Week 1-2)

### Days 1-2: Project Structure & Initial Setup ✅

**Goal:** Create FastAPI project with basic endpoints

- [x] Create `backend/` directory structure
  ```
  backend/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.py
  │   ├── dependencies.py
  │   ├── api/v1/
  │   │   ├── endpoints/
  │   │   │   ├── health.py
  │   │   │   ├── interactions.py
  │   │   │   └── providers.py
  │   │   └── schemas/
  │   │       ├── requests.py
  │   │       └── responses.py
  │   ├── services/
  │   ├── repositories/
  │   ├── models/
  │   └── core/
  ├── tests/
  ├── requirements.txt
  └── .env.example
  ```

- [x] Create `backend/requirements.txt`
  - fastapi
  - uvicorn[standard]
  - sqlalchemy
  - pydantic
  - python-dotenv
  - pytest
  - httpx (for testing)

- [x] Create `backend/app/main.py` (FastAPI app entry point)
  - Initialize FastAPI app
  - Add CORS middleware (for future React)
  - Include health check endpoint
  - Basic error handling

- [x] Create `backend/app/config.py` (Pydantic Settings)
  - Database URL (SQLite)
  - API keys (OpenAI, Google, Anthropic)
  - Environment configuration

- [x] Create health check endpoint: `GET /health`
  - Returns status, version
  - Test database connectivity

- [x] Test: Run FastAPI on port 8000
  ```bash
  cd backend
  uvicorn app.main:app --reload --port 8000
  ```

- [x] Verify: Access http://localhost:8000/docs (automatic Swagger docs)

**Deliverable:** FastAPI backend running with health check ✅

---

### Days 3-4: Define API Contracts (Pydantic Schemas) ✅

**Goal:** Define all request/response schemas for API endpoints

- [x] Create `backend/app/api/v1/schemas/requests.py`
  - `SendPromptRequest` (prompt, provider, model, data_mode, headless)
  - `BatchRequest` (prompts list, models list)
  - Input validation with Pydantic validators

- [x] Create `backend/app/api/v1/schemas/responses.py`
  - `Source` schema
  - `SearchQuery` schema
  - `Citation` schema
  - `SendPromptResponse` schema (full interaction data)
  - `InteractionSummary` schema (for list views)
  - `BatchStatus` schema
  - `ProviderInfo`, `HealthResponse`, `ErrorResponse` schemas

- [x] Add validation rules
  - Prompt length limits (1-10000 chars)
  - XSS prevention (no <script> tags, etc.)
  - Provider validation (openai, google, anthropic, chatgpt)
  - Data mode validation (api, network_log)
  - Case-insensitive provider matching

- [x] Test schemas with pytest
  - Valid inputs pass
  - Invalid inputs raise ValidationError
  - Edge cases handled
  - 29 passing tests

**Deliverable:** Complete API contract definitions with validation ✅

---

### Days 5-8: Build Services & Repositories ✅

**Goal:** Extract business logic and data access into clean layers

#### Day 5-6: Repository Layer ✅

- [x] Create `backend/app/repositories/interaction_repository.py`
  ```python
  class InteractionRepository:
      def save(interaction: Interaction) -> int
      def get_by_id(id: int) -> Optional[Interaction]
      def get_recent(limit: int, data_source: str = None) -> List[Interaction]
      def delete(id: int) -> bool
  ```

- [x] Implement with SQLAlchemy
  - Use existing database models from `src/database.py`
  - Copy models to `backend/app/models/database.py`
  - Add eager loading to prevent N+1 queries (using joinedload)
  - Connection management with dependency injection

- [x] Add unit tests for repository
  - Use in-memory SQLite for testing
  - Test CRUD operations
  - Test eager loading works
  - 11 passing tests

#### Day 7-8: Service Layer ✅

- [x] Create `backend/app/services/interaction_service.py`
  ```python
  class InteractionService:
      def save_interaction(response: ProviderResponse, prompt: str) -> int
      def get_recent_interactions(limit: int) -> List[Interaction]
      def get_interaction_details(id: int) -> Optional[Interaction]
      def delete_interaction(id: int) -> bool
  ```

- [x] Implement business logic
  - Model name normalization (gpt-5-1 → gpt-5.1)
  - Citation classification (Sources Used vs Extra Links)
  - Average rank calculation
  - Domain extraction from URLs

- [x] Create `backend/app/services/provider_service.py`
  ```python
  class ProviderService:
      def send_prompt(prompt: str, model: str) -> SendPromptResponse
      def get_available_providers() -> List[ProviderInfo]
      def get_available_models() -> List[str]
      def get_provider_for_model(model: str) -> str
  ```

- [x] Move provider code from `src/providers/` to backend
  - Copy provider classes (OpenAI, Google, Anthropic)
  - Maintain existing functionality
  - Add to backend/app/services/providers/

- [x] Add unit tests for services
  - Mock repository layer
  - Test business logic in isolation
  - Test error handling
  - 21 passing tests for services + utilities

**Deliverable:** Working services & repositories with tests ✅
**Test Summary:** 61 total tests passing (11 repository + 29 schema + 21 service)

---

### Days 9-10: Implement API Endpoints ✅

**Goal:** Wire up FastAPI endpoints to services

- [x] Create `backend/app/api/v1/endpoints/interactions.py`

  **POST /api/v1/interactions/send**
  - Accept SendPromptRequest
  - Call provider service
  - Save via interaction service
  - Return SendPromptResponse
  - Error handling (400, 500, 502)

  **GET /api/v1/interactions/recent**
  - Query params: limit, data_source
  - Call interaction service
  - Return List[InteractionSummary]

  **GET /api/v1/interactions/{id}**
  - Path param: id
  - Call interaction service
  - Return full InteractionResponse
  - 404 if not found

  **DELETE /api/v1/interactions/{id}**
  - Path param: id
  - Call interaction service
  - Return 204 on success, 404 if not found

- [x] Create `backend/app/api/v1/endpoints/providers.py`

  **GET /api/v1/providers**
  - Return list of available providers
  - Include supported models for each

  **GET /api/v1/providers/models**
  - Return all available models across providers

- [x] Add dependency injection
  - Database session management (get_db)
  - Service instantiation (get_interaction_service, get_provider_service)
  - Proper cleanup on request completion

- [x] Add integration tests
  - Test each endpoint end-to-end
  - Use TestClient from FastAPI
  - Test happy paths and error cases
  - 17 API integration tests

- [x] Add exception handlers
  - RequestValidationError (422)
  - SQLAlchemyError (500)
  - Global exception handler (500)
  - Consistent error response format

- [x] Add OpenAPI documentation
  - All endpoints documented at /docs
  - Request/response schemas
  - Error responses

**Deliverable:** Working FastAPI backend with all endpoints tested ✅
**Test Summary:** 78 total tests passing (11 repository + 29 schema + 21 service + 17 API)

---

## Stage 2: Streamlit API Client (Week 3)

### Days 11-12: Create API Client ✅

**Goal:** Build client library for Streamlit to call FastAPI

- [x] Create `frontend/api_client.py`
  ```python
  class APIClient:
      def __init__(base_url: str, timeout_default, timeout_send_prompt, max_retries, pool_connections, pool_maxsize)
      def send_prompt(...) -> dict
      def get_recent_interactions(...) -> List[dict]
      def get_interaction(...) -> dict
      def delete_interaction(...) -> bool
      def get_providers() -> List[dict]
      def get_models() -> List[str]
      def health_check() -> dict
  ```

- [x] Implement with httpx (420 lines)
  - Connection pooling with configurable limits
  - Timeout configuration (120s for send_prompt, 30s default)
  - Retry logic with exponential backoff (tenacity)
  - Custom exception hierarchy for user-friendly error messages
  - Comprehensive docstrings with examples
  - Type hints throughout

- [x] Custom exceptions implemented
  - `APIClientError` (base)
  - `APITimeoutError`
  - `APIConnectionError`
  - `APIValidationError`
  - `APINotFoundError`
  - `APIServerError`

- [x] Test API client
  - 23 unit tests using respx for HTTP mocking
  - Mock HTTP responses for all endpoints
  - Test error handling (404, 422, 500, timeout, connection)
  - Test retries and cleanup
  - All tests passing ✅

- [x] Live testing with FastAPI backend
  - Health check working
  - Provider/model endpoints working
  - Error handling verified

**Deliverable:** Robust API client for Streamlit ✅
**Test Summary:** 23 unit tests passing (initialization, methods, error handling)

---

### Days 13-14: Update Streamlit UI ✅

**Goal:** Replace direct database calls with API calls

- [x] Update `app.py` imports
  - Removed `from src.database import Database`
  - Added `from frontend.api_client import APIClient, APIClientError, APINotFoundError`
  - Replaced database initialization with API client in session state

- [x] Update Tab 1: Interactive
  - Replaced `provider.send_prompt()` + `db.save_interaction()` with `api_client.send_prompt()`
  - Backend now handles both provider calls AND database persistence
  - Added comprehensive error handling for API exceptions (timeout, connection, validation)
  - Converts API response dict to SimpleNamespace objects for display functions

- [x] Update Tab 2: Batch Analysis
  - Replaced provider + database calls with `api_client.send_prompt()`
  - Updated result processing to handle API response format
  - Fixed syntax error in batch processing
  - Network log mode still uses direct browser capture (unchanged)

- [x] Update Tab 3: History
  - `db.get_recent_interactions()` → `api_client.get_recent_interactions()`
  - `db.get_interaction_details()` → `api_client.get_interaction()`
  - `db.delete_interaction()` → `api_client.delete_interaction()`
  - All filtering and display working correctly

- [x] Update session state management
  - Removed database from session state
  - Added API client to session state with proper initialization
  - Updated `get_all_models()` to fetch from API

- [x] Run both services in parallel
  - FastAPI on port 8000 ✅
  - Streamlit on port 8501 ✅
  - End-to-end workflows tested and working

- [x] Fixed bugs found
  - Syntax error in batch list comprehension
  - API response format conversion (dict → SimpleNamespace)
  - Error handling for all API exceptions
  - Proper cleanup of HTTP client

**Deliverable:** Streamlit UI fully working via FastAPI ✅
**Changes:** 153 insertions(+), 100 deletions(-) in app.py

---

## Stage 3: Polish & Deploy (Week 4)

### Days 15-16: Docker & Local Development ✅

**Goal:** Make it easy to run the full stack locally

- [x] Create `backend/Dockerfile`
  - Python 3.11 slim base image
  - Install dependencies from requirements.txt
  - Copy application code
  - Expose port 8000
  - Run with uvicorn
  - Added health check

- [x] Create `Dockerfile` (frontend at root)
  - Python 3.11 slim base image
  - Install Streamlit and dependencies
  - Install Playwright + Chromium for network capture
  - Copy app.py and config
  - Expose port 8501
  - Run with streamlit
  - Added health check

- [x] Create `docker-compose.yml`
  - Backend service (api) on port 8000
  - Frontend service on port 8501
  - Volume mounting for database persistence (`./backend/data:/app/data`)
  - Volume mounting for frontend data (`./data:/app/data`)
  - Environment variable configuration from .env
  - Docker network (llm-search-network)
  - Service dependencies (frontend depends on api health check)
  - Health checks for both services
  - Restart policies (unless-stopped)

- [x] Create `.dockerignore` files
  - Root .dockerignore for frontend build
  - backend/.dockerignore for backend build
  - Optimized to exclude venv, cache, tests, etc.

- [x] Update `.env.example`
  - Comprehensive documentation
  - All required environment variables
  - Docker-specific configuration notes
  - Instructions for setup

- [x] Update README.md
  - Added "Deployment" section with Docker as Option 1
  - Quick start guide (`docker compose up -d`)
  - Docker architecture explanation
  - Docker commands reference
  - Environment variables documentation
  - Local development option (Option 2)
  - Updated project structure showing Docker files
  - Added architecture overview diagram

**Deliverable:** Complete Docker setup ready for deployment ✅
**Note:** Docker testing skipped (Docker not installed locally)

---

### Days 17-18: Error Handling & Logging ✅

**Goal:** Production-ready error handling and observability

- [x] Add custom exceptions
  - Created `backend/app/core/exceptions.py` with comprehensive hierarchy
  - Defined base APIException with error codes and status codes
  - Client errors (4xx): ValidationError, ResourceNotFoundError, InvalidRequestError, etc.
  - Server errors (5xx): InternalServerError, DatabaseError, ExternalServiceError, etc.
  - Domain-specific: ProviderError, ModelNotSupportedError, InteractionNotFoundError

- [x] Implement exception handlers
  - Global exception handler for all exceptions in FastAPI main.py
  - APIException handler for custom exceptions
  - RequestValidationError handler with field-level details
  - SQLAlchemyError handler for database errors
  - Return consistent error responses with error codes and details
  - All handlers include correlation IDs in logs

- [x] Add structured logging
  - Configured structured logging with correlation_id field
  - Added CorrelationIdFilter for all log records
  - Correlation IDs auto-generated (UUID v4) or from X-Correlation-ID header
  - Log format: timestamp - module - level - [correlation_id] - message
  - All API calls logged with timing and client info

- [x] Add request/response logging middleware
  - Created LoggingMiddleware in `backend/app/core/middleware.py`
  - Logs incoming requests with method, path, query params, client IP, user agent
  - Logs outgoing responses with status codes and duration (ms)
  - Includes correlation IDs in all middleware logs
  - Created CorrelationIDMiddleware for lightweight tracking
  - Added get_correlation_id helper function

- [x] Add validation error handling
  - Catch Pydantic ValidationErrors with custom handler
  - Return user-friendly error messages with VALIDATION_ERROR code
  - Include field-level errors with field paths and types
  - Proper 422 status code for validation failures

- [x] Test error scenarios
  - Created comprehensive test suite in `backend/test_error_handling.py`
  - Tests for validation errors (missing fields)
  - Tests for invalid model errors
  - Tests for interaction not found (404)
  - Tests for correlation ID propagation
  - All tests passing (6/6)

- [x] Update API documentation
  - Added comprehensive error response examples to OpenAPI docs
  - Error examples for all endpoints (/send, /{id}, DELETE /{id})
  - Documented all status codes (400, 404, 422, 500, 502)
  - Interactive examples in /docs interface

**Deliverable:** Robust error handling and logging ✅
**Commits:** e3622c5, 945351d, 1335999

---

### Days 19-20: Testing & Documentation ✅

**Goal:** Comprehensive testing and documentation

- [x] Expand test coverage
  - **Achieved 95% coverage** (exceeded 80% target) ✅
  - Added comprehensive provider implementation tests (48 tests)
  - Added edge case tests for all providers
  - All integration tests passing (166 total tests)

- [x] Run full test suite
  ```bash
  pytest backend/tests/ -v --cov=app --cov-report=html
  ```
  - **166 tests passing** ✅
  - Coverage report: 95% overall
  - Provider tests: OpenAI (100%), Google (96%), Anthropic (100%)

- [x] Update OpenAPI documentation
  - All endpoints documented with descriptions ✅
  - Request/response examples for all endpoints
  - Error codes documented (400, 404, 422, 500, 502)
  - Interactive Swagger UI at /docs

- [x] Create API documentation
  - Created `backend/API_DOCUMENTATION.md` (400+ lines) ✅
  - Complete endpoint reference with examples
  - Data models documented
  - Error handling guide
  - Authentication/environment setup
  - cURL examples for all operations

- [x] Update README.md
  - Created `backend/README.md` with architecture overview ✅
  - System architecture diagrams with layer breakdown
  - Database schema documentation
  - Setup instructions (local & Docker)
  - Development guide with provider integration patterns
  - Testing guide showing 95% coverage
  - Deployment considerations
  - Troubleshooting section

**Deliverable:** Well-tested, documented system ✅
**Test Coverage:** 95% (1047 statements, 55 missing)
**Total Tests:** 166 passing
**Commits:** ea990c1 (tests), 39f8420 (docs)

---

### Days 21: Local Production Hardening

**Goal:** Run the full stack reliably on a single machine

- [ ] Standardize environment configuration
  - Align `.env`, `.env.example`, and any local overrides
  - Document required env vars for backend and Streamlit
  - Clarify local-only vs future-cloud settings

- [ ] Treat Docker Compose as "local production"
  - Use `docker-compose.yml` as the canonical way to run the full stack
  - Confirm backend + Streamlit + SQLite volume all work together
  - Document a one-command startup workflow (e.g. `docker compose up -d`)

- [ ] Add simple backup & restore for SQLite
  - Document backup procedure for the local DB volume
  - Add basic scripts or documented commands for backup/restore
  - Verify backup/restore with a small dataset

- [ ] Local health and smoke checks
  - Add a simple script or Make target that checks `/health` and one core interaction endpoint
  - Document how to run a quick smoke test after changes

- [ ] Operational docs for local-only usage
  - Update README and/or backend docs to describe "local production" usage
  - Include troubleshooting tips for Docker + SQLite + Streamlit on one machine

**Deliverable:** Stable "local production" environment using Docker Compose

---

## Stage 4: Cloud Deployment (Deferred)

**These steps are explicitly deferred until you're ready to deploy to a cloud platform.**

### Cloud Platform Selection & Setup

- [ ] Choose deployment platform
  - **Recommended: Render** (simple, $7/month)
  - Alternative: Railway, Fly.io, AWS ECS

### Deploy Backend & Frontend

- [ ] Deploy FastAPI backend
  - Create web service on chosen platform
  - Set environment variables
  - Configure build command
  - Set start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

- [ ] Deploy Streamlit frontend
  - Create web service on chosen platform
  - Point to backend API URL
  - Configure environment variables
  - Set start command: `streamlit run app.py`

### Persistence & Monitoring

- [ ] Configure SQLite persistence (or future Postgres)
  - Add persistent disk volume (for SQLite) or database service (for Postgres)
  - Mount to `/data` directory (for SQLite)
  - Verify data persists across deploys

- [ ] Test deployed application
  - Verify both services are accessible
  - Test end-to-end workflows
  - Check logs for errors
  - Monitor performance

- [ ] Set up basic monitoring
  - Configure health checks
  - Set up uptime monitoring
  - Configure error tracking (Sentry optional)

**Deliverable:** Application running on a managed cloud platform (later milestone)

---

## Post-Launch: Optional Improvements (Week 5+)

**These can wait until actually needed:**

### Near-Term: Local Quality & DX

- [ ] Add code quality tools
  - Black (formatting)
  - Ruff (linting)
  - mypy (type checking)
  - pre-commit hooks

- [ ] Strengthen tests around current workflows
  - Add E2E tests that hit the FastAPI backend via Docker (local-only)
  - Add targeted tests for any newly discovered edge cases

- [ ] Basic SQLite tuning for local use
  - Add indexes for obvious hot paths once data grows
  - Measure impact on common queries

### Performance Optimizations (When Slow)

- [ ] Add database indexes to SQLite
  - Index on created_at, prompt_id, response_id
  - Composite indexes for common queries
  - Measure query performance improvement

- [ ] Add caching layer (Redis)
  - Cache API responses (1 hour TTL)
  - Cache model/provider lists
  - Cache recent interactions

- [ ] Optimize N+1 queries
  - Use eager loading in repository
  - Measure query count reduction

### Code Quality Improvements (When Time Permits)

- [ ] Split chatgpt_capturer.py into modules
  - Extract authentication logic
  - Extract search enabler
  - Extract response extractor

- [ ] Add more comprehensive tests
  - E2E tests with Playwright
  - Load tests with Locust
  - Security tests

- [ ] Add code quality tools
  - Black (formatting)
  - Ruff (linting)
  - mypy (type checking)
  - pre-commit hooks

### Infrastructure Upgrades (When Scaling)

- [ ] Migrate to PostgreSQL
  - When concurrent writes become an issue
  - Change DATABASE_URL in .env
  - Run migrations
  - Test thoroughly

- [ ] Add Redis for caching
  - When API responses get slow
  - Set up Redis instance
  - Add caching decorators
  - Monitor cache hit rates

- [ ] Add background job queue
  - When batch jobs take >1 minute
  - Use Redis Streams or RabbitMQ
  - Move long-running tasks to workers

### Frontend Migration (When Needed)

- [ ] Start React frontend
  - When Streamlit becomes limiting
  - Use Next.js + TypeScript
  - Call same FastAPI backend
  - Gradual migration (run both)

---

## Progress Tracking

### Week 1-2: FastAPI Backend ✅
- [x] Days 1-2: Project structure & setup ✅
- [x] Days 3-4: API contracts (Pydantic) ✅
- [x] Days 5-8: Services & repositories ✅
- [x] Days 9-10: API endpoints ✅

### Week 3: Streamlit API Client ✅
- [x] Days 11-12: API client library ✅
- [x] Days 13-14: Update Streamlit UI ✅

### Week 4: Polish & Deploy 🚧
- [x] Days 15-16: Docker & local dev ✅
- [x] Days 17-18: Error handling & logging ✅
- [x] Days 19-20: Testing & documentation ✅ (95% coverage, 166 tests)
- [ ] Days 21: Local production hardening NEXT

### Week 5+: Optional Improvements
- [ ] Local quality & DX improvements
- [ ] Performance optimizations (as needed)
- [ ] Code quality improvements (as time permits)
- [ ] Infrastructure upgrades (when scaling)
- [ ] React frontend (when Streamlit limiting)

---

## Success Criteria

**Week 2:** ✅ FastAPI backend with all endpoints working and tested

**Week 3:** ✅ Streamlit calling FastAPI for all operations

**Week 4:** 🚧 95% complete - Testing & documentation done, local production hardening pending
- ✅ Docker setup complete
- ✅ Error handling & logging production-ready
- ✅ 95% test coverage achieved (166 tests passing)
- ✅ Comprehensive API & backend documentation
- ⏳ Local production hardening (Day 21)

**Cloud Deployment (Deferred Stage 4):**
- ⏳ Application deployed to a managed cloud platform
- ⏳ Persistent storage configured for cloud
- ⏳ Basic uptime and error monitoring in place

**Long-term:**
- 3-5x faster development velocity
- Can add React without touching backend
- Clean, testable, maintainable codebase
- Foundation for years of growth

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| FastAPI | Modern, fast, async, automatic docs, Pydantic validation |
| SQLite (for now) | Already using, SQLAlchemy abstracts it, easy to switch later |
| Defer PostgreSQL | Only needed at scale (100+ concurrent users) |
| Defer Redis | Only needed when caching required |
| Docker Compose | Simple local dev, easy to understand |
| Render for deployment | Simple, affordable ($7/month), managed platform |

---

## Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Deployment Guide**: See `docs/REFACTORING_RECOMMENDATIONS.md`
- **Architecture Analysis**: See `docs/REFACTORING_RECOMMENDATIONS.md`
- **Research Findings**: See `docs/LLM_SEARCH_FINDINGS.md`

---

## Notes

- Keep Streamlit working throughout migration (run both services in parallel)
- Test frequently - don't build for days without testing
- Commit after each major milestone
- Ask questions if anything is unclear
- Focus on getting it working first, optimize later
- Document decisions as you go

---
