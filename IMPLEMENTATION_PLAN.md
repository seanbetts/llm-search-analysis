# LLM Search Analysis - Implementation Plan

**Strategy:** FastAPI-first, SQLite-for-now, Fast Track (4 weeks)
**Last Updated:** December 1, 2024
**Status:** 🚀 Ready to start

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

### Days 5-8: Build Services & Repositories

**Goal:** Extract business logic and data access into clean layers

#### Day 5-6: Repository Layer

- [ ] Create `backend/app/repositories/interaction_repository.py`
  ```python
  class InteractionRepository:
      def save(interaction: Interaction) -> int
      def get_by_id(id: int) -> Optional[Interaction]
      def get_recent(limit: int, data_source: str = None) -> List[Interaction]
      def delete(id: int) -> bool
  ```

- [ ] Implement with SQLAlchemy
  - Use existing database models from `src/database.py`
  - Copy models to `backend/app/models/database.py`
  - Add eager loading to prevent N+1 queries
  - Connection management with dependency injection

- [ ] Add unit tests for repository
  - Use in-memory SQLite for testing
  - Test CRUD operations
  - Test eager loading works

#### Day 7-8: Service Layer

- [ ] Create `backend/app/services/interaction_service.py`
  ```python
  class InteractionService:
      def save_interaction(response: ProviderResponse, prompt: str) -> int
      def get_recent_interactions(limit: int) -> List[Interaction]
      def get_interaction_details(id: int) -> Optional[Interaction]
      def delete_interaction(id: int) -> bool
  ```

- [ ] Implement business logic
  - Model name normalization (gpt-5-1 → gpt-5.1)
  - Citation classification (Sources Used vs Extra Links)
  - Average rank calculation
  - Domain extraction from URLs

- [ ] Create `backend/app/services/provider_service.py`
  ```python
  class ProviderService:
      def get_provider(provider_name: str, data_mode: str) -> Provider
      def send_prompt(provider: Provider, prompt: str, model: str) -> ProviderResponse
      def get_available_providers() -> List[str]
      def get_available_models(provider: str) -> List[str]
  ```

- [ ] Move provider code from `src/providers/` to backend
  - Copy provider classes
  - Adapt for async if needed
  - Maintain existing functionality

- [ ] Add unit tests for services
  - Mock repository layer
  - Test business logic in isolation
  - Test error handling

**Deliverable:** Working services & repositories with tests

---

### Days 9-10: Implement API Endpoints

**Goal:** Wire up FastAPI endpoints to services

- [ ] Create `backend/app/api/v1/endpoints/interactions.py`

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

- [ ] Create `backend/app/api/v1/endpoints/providers.py`

  **GET /api/v1/providers**
  - Return list of available providers
  - Include supported models for each

  **GET /api/v1/providers/{provider}/models**
  - Return models for specific provider

- [ ] Add dependency injection
  - Database session management
  - Service instantiation
  - Proper cleanup on request completion

- [ ] Add integration tests
  - Test each endpoint end-to-end
  - Use TestClient from FastAPI
  - Test happy paths and error cases

- [ ] Add request/response logging
  - Log all API calls
  - Include timing information
  - Use structured logging (structlog)

**Deliverable:** Working FastAPI backend with all endpoints tested

---

## Stage 2: Streamlit API Client (Week 3)

### Days 11-12: Create API Client

**Goal:** Build client library for Streamlit to call FastAPI

- [ ] Create `frontend/api_client.py`
  ```python
  class APIClient:
      def __init__(base_url: str)
      def send_prompt(...) -> dict
      def get_recent_interactions(...) -> List[dict]
      def get_interaction(...) -> dict
      def delete_interaction(...) -> bool
      def get_providers() -> List[dict]
  ```

- [ ] Implement with `requests` or `httpx`
  - Connection pooling
  - Timeout configuration
  - Retry logic for transient failures
  - Error handling and user-friendly messages

- [ ] Add response caching (optional)
  - Cache provider/model lists
  - Cache interaction details
  - Use @st.cache_data

- [ ] Test API client
  - Mock HTTP responses
  - Test error handling
  - Test retries

**Deliverable:** Robust API client for Streamlit

---

### Days 13-14: Update Streamlit UI

**Goal:** Replace direct database calls with API calls

- [ ] Update `app.py` imports
  - Remove direct database imports
  - Add API client import

- [ ] Update Tab 1: Interactive
  - Replace `st.session_state.db.save_interaction()` with `api_client.send_prompt()`
  - Update error handling
  - Test all functionality works

- [ ] Update Tab 2: Batch Analysis
  - Replace database calls with API calls
  - Update progress tracking
  - Test batch processing

- [ ] Update Tab 3: History
  - Replace `get_recent_interactions()` with API call
  - Replace `get_interaction_details()` with API call
  - Replace `delete_interaction()` with API call
  - Test filtering and search

- [ ] Update session state management
  - Remove database from session state
  - Add API client to session state
  - Initialize API client once

- [ ] Run both services in parallel
  - FastAPI on port 8000
  - Streamlit on port 8501
  - Test end-to-end workflows

- [ ] Fix any bugs found
  - Response format differences
  - Error handling edge cases
  - Performance issues

**Deliverable:** Streamlit UI fully working via FastAPI

---

## Stage 3: Polish & Deploy (Week 4)

### Days 15-16: Docker & Local Development

**Goal:** Make it easy to run the full stack locally

- [ ] Create `backend/Dockerfile`
  - Python 3.11 base image
  - Install dependencies
  - Copy application code
  - Expose port 8000
  - Run with uvicorn

- [ ] Create `frontend/Dockerfile`
  - Python 3.11 base image
  - Install Streamlit
  - Copy frontend code
  - Expose port 8501
  - Run with streamlit

- [ ] Create `docker-compose.yml`
  ```yaml
  services:
    api:
      build: ./backend
      ports: ["8000:8000"]
      volumes: ["./data:/app/data"]
      env_file: .env

    frontend:
      build: ./frontend
      ports: ["8501:8501"]
      environment:
        - API_BASE_URL=http://api:8000
      depends_on: [api]
  ```

- [ ] Create `.env.example`
  - Document all environment variables
  - Include instructions

- [ ] Test Docker Compose setup
  ```bash
  docker-compose up
  # Verify both services start
  # Verify Streamlit can call API
  # Verify database persists in volume
  ```

- [ ] Update README.md
  - Add Docker instructions
  - Document environment variables
  - Add architecture diagram

**Deliverable:** Complete Docker setup for local development

---

### Days 17-18: Error Handling & Logging

**Goal:** Production-ready error handling and observability

- [ ] Add custom exceptions
  - Create `backend/app/core/exceptions.py`
  - Define exception hierarchy
  - Add error codes and messages

- [ ] Implement exception handlers
  - Global exception handler in FastAPI
  - Return consistent error responses
  - Log all errors with context

- [ ] Add structured logging
  - Install structlog
  - Configure logging in config.py
  - Add correlation IDs to requests
  - Log all API calls with timing

- [ ] Add request/response logging middleware
  - Log incoming requests
  - Log outgoing responses
  - Include status codes and timing

- [ ] Add validation error handling
  - Catch Pydantic ValidationErrors
  - Return user-friendly error messages
  - Include field-level errors

- [ ] Test error scenarios
  - Invalid inputs
  - Provider failures
  - Database errors
  - Network timeouts

**Deliverable:** Robust error handling and logging

---

### Days 19-20: Testing & Documentation

**Goal:** Comprehensive testing and documentation

- [ ] Expand test coverage
  - Aim for 80%+ coverage on services
  - Add edge case tests
  - Add integration tests
  - Add load tests (optional)

- [ ] Run full test suite
  ```bash
  pytest backend/tests/ -v --cov=app --cov-report=html
  ```

- [ ] Update OpenAPI documentation
  - Add descriptions to all endpoints
  - Add examples for requests/responses
  - Document error codes
  - Add authentication (if applicable)

- [ ] Create API documentation
  - Endpoint reference
  - Authentication guide
  - Rate limiting info (if applicable)
  - Example usage

- [ ] Update README.md
  - Architecture overview
  - Setup instructions
  - API documentation link
  - Deployment guide

- [ ] Create DEPLOYMENT.md
  - Deployment options (Render, Railway, etc.)
  - Configuration guide
  - Monitoring setup
  - Backup strategy

**Deliverable:** Well-tested, documented system

---

### Days 21: Deploy to Cloud

**Goal:** Get the application running in production

- [ ] Choose deployment platform
  - **Recommended: Render** (simple, $7/month)
  - Alternative: Railway, Fly.io, AWS ECS

- [ ] Deploy FastAPI backend
  - Create web service on Render
  - Set environment variables
  - Configure build command
  - Set start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

- [ ] Deploy Streamlit frontend
  - Create web service on Render
  - Point to backend API URL
  - Configure environment variables
  - Set start command: `streamlit run app.py`

- [ ] Configure SQLite persistence
  - Add persistent disk volume
  - Mount to /data directory
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

**Deliverable:** Application running in production

---

## Post-Launch: Optional Improvements (Week 5+)

**These can wait until actually needed:**

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

### Week 1-2: FastAPI Backend 🚧
- [x] Days 1-2: Project structure & setup ✅
- [x] Days 3-4: API contracts (Pydantic) ✅
- [ ] Days 5-8: Services & repositories 🚧 IN PROGRESS
- [ ] Days 9-10: API endpoints

### Week 3: Streamlit API Client
- [ ] Days 11-12: API client library
- [ ] Days 13-14: Update Streamlit UI

### Week 4: Polish & Deploy
- [ ] Days 15-16: Docker & local dev
- [ ] Days 17-18: Error handling & logging
- [ ] Days 19-20: Testing & documentation
- [ ] Days 21: Deploy to production

### Week 5+: Optional Improvements
- [ ] Performance optimizations (as needed)
- [ ] Code quality improvements (as time permits)
- [ ] Infrastructure upgrades (when scaling)
- [ ] React frontend (when Streamlit limiting)

---

## Success Criteria

**Week 2:** ✅ FastAPI backend with all endpoints working and tested

**Week 3:** ✅ Streamlit calling FastAPI for all operations

**Week 4:** ✅ Deployed to production, fully documented

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

**Ready to start? Let's build the FastAPI backend!** 🚀
