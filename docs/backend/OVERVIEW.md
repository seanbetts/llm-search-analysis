# LLM Search Analysis - Backend API

FastAPI-based REST API for analyzing LLM search capabilities across OpenAI, Google, and Anthropic providers.

**Version:** 1.0.0
**Test Coverage:** 95% (191 tests)
**Python:** 3.10+

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Setup](#setup)
- [Development](#development)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)

## Overview

The backend API provides:
- **Multi-Provider LLM Integration**: OpenAI, Google Gemini, Anthropic Claude
- **Web Search Analysis**: Track queries, sources, and citations
- **Interaction Persistence**: SQLite database with full history
- **RESTful API**: Clean endpoints with automatic OpenAPI documentation
- **Comprehensive Error Handling**: Consistent error responses with correlation IDs
- **High Test Coverage**: 95% coverage with 191 passing tests

### Key Features

- Provider abstraction layer for easy integration of new LLMs
- Automatic search query and source tracking
- Citation analysis with rank tracking
- Database schema supporting both API and network capture modes
- Correlation ID tracking for request tracing
- Structured logging with request/response details
- CORS support for frontend integration

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (Streamlit)                   │
│                      Port: 8501                              │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP REST API
┌────────────────────────────┴────────────────────────────────┐
│                     Backend API (FastAPI)                    │
│                          Port: 8000                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  API Layer (FastAPI)                   │  │
│  │  - /api/v1/interactions  - /api/v1/providers          │  │
│  │  - Request validation    - Error handling             │  │
│  │  - OpenAPI docs          - CORS middleware            │  │
│  └─────────────┬──────────────────────┬───────────────────┘  │
│                │                      │                       │
│  ┌─────────────┴──────────┐  ┌───────┴─────────────────────┐│
│  │   Service Layer        │  │   Provider Layer            ││
│  │  - Business logic      │  │  - Provider abstraction     ││
│  │  - Data transformation │  │  - OpenAI integration       ││
│  │  - Validation          │  │  - Google integration       ││
│  └─────────────┬──────────┘  │  - Anthropic integration    ││
│                │              │  - Factory pattern          ││
│  ┌─────────────┴──────────┐  └─────────────────────────────┘│
│  │  Repository Layer       │                                 │
│  │  - Data access          │                                 │
│  │  - Query building       │                                 │
│  │  - Transaction mgmt     │                                 │
│  └─────────────┬───────────┘                                 │
└────────────────┼─────────────────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────────────────┐
│                  Database (SQLite)                           │
│  - Providers  - Interactions  - Responses                    │
│  - Search Queries  - Query Sources  - Response Sources       │
│  - Sources Used                                              │
└──────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**API Layer (`app/api/v1/`)**
- HTTP request/response handling
- Request validation with Pydantic schemas
- Error handling and formatting
- OpenAPI documentation
- CORS and middleware

**Service Layer (`app/services/`)**
- Business logic implementation
- Provider orchestration
- Data transformation and aggregation
- Model validation
- API key management

**Repository Layer (`app/repositories/`)**
- Database operations (CRUD)
- Query building with SQLAlchemy
- Transaction management
- Data persistence

**Provider Layer (`app/services/providers/`)**
- LLM provider integrations
- Response parsing
- Search query extraction
- Citation tracking

### Project Structure

```
backend/
├── app/
│   ├── main.py                      # FastAPI application entry
│   ├── config.py                    # Configuration management
│   ├── dependencies.py              # Dependency injection
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── interactions.py  # Interaction endpoints
│   │       │   └── providers.py     # Provider endpoints
│   │       └── schemas/
│   │           ├── requests.py      # Request models
│   │           └── responses.py     # Response models
│   │
│   ├── core/
│   │   ├── exceptions.py            # Custom exceptions
│   │   ├── middleware.py            # Custom middleware
│   │   └── utils.py                 # Utility functions
│   │
│   ├── models/
│   │   └── database.py              # SQLAlchemy ORM models
│   │
│   ├── repositories/
│   │   └── interaction_repository.py # Data access layer
│   │
│   └── services/
│       ├── interaction_service.py    # Business logic
│       ├── provider_service.py       # Provider orchestration
│       └── providers/
│           ├── base_provider.py      # Abstract base class
│           ├── provider_factory.py   # Provider factory
│           ├── openai_provider.py    # OpenAI Responses API
│           ├── google_provider.py    # Google Gemini
│           └── anthropic_provider.py # Anthropic Claude
│
├── tests/                            # Test suite (191 tests)
│   ├── test_api.py                   # API endpoint tests
│   ├── test_api_contracts.py         # API contract/schema validation tests
│   ├── test_integration_database.py  # Database integration tests with edge cases
│   ├── test_openai_provider.py       # OpenAI provider tests
│   ├── test_google_provider.py       # Google provider tests
│   ├── test_anthropic_provider.py    # Anthropic provider tests
│   ├── test_provider_factory.py      # Factory tests
│   ├── test_provider_service.py      # Service tests
│   ├── test_repository.py            # Repository tests
│   ├── test_service.py               # Business logic tests
│   ├── test_schemas.py               # Schema validation tests
│   ├── test_middleware.py            # Middleware tests
│   └── test_exception_handlers.py    # Error handling tests
│
├── data/                             # Data directory
│   └── llm_search.db                 # SQLite database (auto-created)
│
├── requirements.txt                  # Python dependencies
├── pytest.ini                        # Pytest configuration
├── Dockerfile                        # Docker image definition
├── .dockerignore                     # Docker build exclusions
├── .env.example                      # Environment template
├── API_DOCUMENTATION.md              # Detailed API docs
└── README.md                         # This file
```

### Database Schema

The persistence model now centers on `InteractionModel`, which replaces the old
`sessions → prompts → responses` chain. Alembic revision `9b9f1c6a2e3f` creates
the schema below and enforces cascading deletes so orphaned records cannot be
introduced.

```sql
providers (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  display_name TEXT,
  is_active BOOLEAN DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

interactions (
  id INTEGER PRIMARY KEY,
  provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  data_source TEXT NOT NULL DEFAULT 'api',
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  deleted_at TIMESTAMP,
  metadata_json JSON
)

responses (
  id INTEGER PRIMARY KEY,
  interaction_id INTEGER NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
  response_text TEXT,
  response_time_ms INTEGER,
  created_at TIMESTAMP NOT NULL,
  raw_response_json JSON,
  data_source TEXT DEFAULT 'api',
  extra_links_count INTEGER DEFAULT 0,
  sources_found INTEGER DEFAULT 0,
  sources_used_count INTEGER DEFAULT 0,
  avg_rank REAL
)

search_queries (
  id INTEGER PRIMARY KEY,
  response_id INTEGER NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
  search_query TEXT,
  created_at TIMESTAMP NOT NULL,
  order_index INTEGER DEFAULT 0,
  internal_ranking_scores JSON,
  query_reformulations JSON
)

query_sources (
  id INTEGER PRIMARY KEY,
  search_query_id INTEGER NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  title TEXT,
  domain TEXT,
  rank INTEGER,
  pub_date TEXT,
  snippet_text TEXT,
  internal_score REAL,
  metadata_json JSON
)

response_sources (
  id INTEGER PRIMARY KEY,
  response_id INTEGER NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  title TEXT,
  domain TEXT,
  rank INTEGER,
  pub_date TEXT,
  snippet_text TEXT,
  internal_score REAL,
  metadata_json JSON
)

sources_used (
  id INTEGER PRIMARY KEY,
  response_id INTEGER NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
  query_source_id INTEGER REFERENCES query_sources(id),
  response_source_id INTEGER REFERENCES response_sources(id),
  url TEXT NOT NULL,
  title TEXT,
  rank INTEGER,
  snippet_used TEXT,
  citation_confidence REAL,
  metadata_json JSON,
  CHECK (
    (query_source_id IS NULL) OR
    (response_source_id IS NULL)
  )
)
```

**Relationships:**
- One provider → Many interactions
- One interaction → Many responses
- One response → Many search queries, response sources, and citations
- `sources_used` rows optionally reference the originating query/response source
  to guarantee referential integrity for citations.

### Schema Operations & Migration Guidance

- **Alembic-managed schema** – The backend no longer creates tables on startup;
  always run `alembic upgrade head` before launching the API.
- **Interactions migration (`9b9f1c6a2e3f`)** – Required for any database that still
  has `sessions`/`prompts`.
  1. Back up the SQLite/Postgres database.
  2. Run `alembic upgrade 9b9f1c6a2e3f` (or `upgrade head` if that revision is the latest).
  3. Inspect the migration logs to ensure interactions were backfilled and the
     legacy tables dropped.
- **Post-migration validation**
  - Execute `python scripts/audit_json_payloads.py --dry-run` to confirm
    historical blobs (raw responses, ranking scores, metadata) still parse.
  - Run `python scripts/backfill_metrics.py --dry-run` to verify response metrics
    remain consistent.
  - Spot-check counts: interactions should match historical response counts, and
    `prompts`/`sessions` tables should no longer exist.

### Provider Integration Pattern

Each provider implements the `BaseProvider` abstract class:

```python
class BaseProvider(ABC):
  """Abstract base class for LLM providers."""

  @abstractmethod
  def get_provider_name(self) -> str:
    """Return provider identifier."""
    pass

  @abstractmethod
  def get_supported_models(self) -> List[str]:
    """Return list of supported models."""
    pass

  @abstractmethod
  def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
    """Send prompt and return structured response."""
    pass

  def validate_model(self, model: str) -> bool:
    """Check if model is supported."""
    return model in self.get_supported_models()
```

**Implementations:**
- `OpenAIProvider`: Uses Responses API with web_search tool
- `GoogleProvider`: Uses google-genai SDK with Search Grounding
- `AnthropicProvider`: Uses Claude API with web_search_20250305 tool

## Setup

### Prerequisites

- Python 3.10 or higher
- pip or poetry
- At least one provider API key

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd llm-search-analysis/backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

5. **Environment variables:**
   ```bash
   # Required: At least one API key
   OPENAI_API_KEY=sk-...
   GOOGLE_API_KEY=AIza...
   ANTHROPIC_API_KEY=sk-ant-...

   # Database
   DATABASE_URL=sqlite:///./data/llm_search.db

   # Server
   LOG_LEVEL=INFO
   DEBUG=false
   CORS_ORIGINS=["http://localhost:3000","http://localhost:8501"]
   ```

6. **Start the server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

7. **Access the API:**
   - API: http://localhost:8000
   - Swagger docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - Health check: http://localhost:8000/health

### Docker Setup

1. **Build and run with Docker:**
   ```bash
   docker build -t llm-search-backend .
   docker run -p 8000:8000 \
     -e OPENAI_API_KEY=sk-... \
     -e GOOGLE_API_KEY=AIza... \
     -e ANTHROPIC_API_KEY=sk-ant-... \
     -v $(pwd)/data:/app/data \
     llm-search-backend
   ```

2. **Or use docker-compose (from project root):**
   ```bash
   cd ..  # Back to project root
   docker compose up -d
   ```

## Development

### Code Style

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for classes and functions
- Format code with Black (recommended)
- Sort imports with isort (recommended)

### Adding a New Provider

1. **Create provider class:**
   ```python
   # app/services/providers/new_provider.py
   from .base_provider import BaseProvider, ProviderResponse

   class NewProvider(BaseProvider):
     SUPPORTED_MODELS = ["model-1", "model-2"]

     def get_provider_name(self) -> str:
       return "new_provider"

     def get_supported_models(self) -> List[str]:
       return self.SUPPORTED_MODELS

     def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
       # Implementation
       pass
   ```

2. **Add to factory:**
   ```python
   # app/services/providers/provider_factory.py
   from .new_provider import NewProvider

   class ProviderFactory:
     PROVIDER_MODELS = {
       # ... existing providers
       "model-1": "new_provider",
       "model-2": "new_provider",
     }

     @staticmethod
     def create_provider(provider_name: str, api_key: str):
       if provider_name == "new_provider":
         return NewProvider(api_key)
       # ... existing providers
   ```

3. **Write tests:**
   ```python
   # tests/test_new_provider.py
   import pytest
   from app.services.providers.new_provider import NewProvider

   class TestNewProvider:
     def test_get_provider_name(self):
       provider = NewProvider("test-key")
       assert provider.get_provider_name() == "new_provider"
     # ... more tests
   ```

## API Documentation

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for detailed endpoint documentation.

### Quick Reference

**Base URL:** `http://localhost:8000`

**Endpoints:**
- `GET /` - API info
- `GET /health` - Health check
- `GET /api/v1/providers` - List providers
- `GET /api/v1/providers/models` - List models
- `POST /api/v1/interactions/send` - Send prompt
- `POST /api/v1/interactions/batch` - Submit batch job
- `GET /api/v1/interactions/batch/{batch_id}` - Poll batch status/results
- `GET /api/v1/interactions/recent` - Get recent interactions
- `GET /api/v1/interactions/{id}` - Get interaction details
- `DELETE /api/v1/interactions/{id}` - Delete interaction

**Interactive Docs:**
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Backend-managed Batch Processing

The backend now orchestrates batch runs rather than relying on client-side loops.

1. `POST /api/v1/interactions/batch` with `{"prompts": [...], "models": [...]}`. The API validates payloads,
   expands the Cartesian product, and returns a `BatchStatus` snapshot containing a `batch_id`, total task count,
   and initial status.
2. Poll `GET /api/v1/interactions/batch/{batch_id}` until `status` is `completed` or `failed`. Each response
   contains all completed `results` (full `SendPromptResponse` objects) plus any `errors`.

The service executes provider calls concurrently using per-provider semaphores so OpenAI, Google, and Anthropic each
adhere to their own throttle. Results are stored in-memory keyed by `batch_id`, which keeps the plumbing simple while
the Streamlit frontend polls every second. If you need durability across restarts, add persistent tables for
`batch_jobs`/`batch_results` before running unattended workloads.

**Configuration**

| Environment Variable | Description | Default |
| --- | --- | --- |
| `BATCH_MAX_CONCURRENCY` | Hard cap on simultaneous provider calls across all batches | `6` |
| `BATCH_PER_PROVIDER_CONCURRENCY` | Default concurrency per provider | `2` |
| `BATCH_MAX_CONCURRENCY_OPENAI` | Override OpenAI concurrency (0 = use default) | `0` |
| `BATCH_MAX_CONCURRENCY_GOOGLE` | Override Google concurrency (0 = use default) | `0` |
| `BATCH_MAX_CONCURRENCY_ANTHROPIC` | Override Anthropic concurrency (0 = use default) | `0` |

Tune these in `.env` (or your deployment environment) to reflect provider quota agreements. Setting a provider-specific
value to `0` falls back to the default per-provider limit. You can observe current caps in API logs when a batch job
starts.

## Testing

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=app --cov-report=html
```

**Run specific test file:**
```bash
pytest tests/test_api.py -v
```

**Run specific test:**
```bash
pytest tests/test_api.py::TestHealthEndpoints::test_health_check_endpoint -v
```

### Test Coverage

Current coverage: **95%** (191 tests passing)

```
app/services/providers/openai_provider.py         100%
app/services/providers/anthropic_provider.py      100%
app/services/provider_service.py                  100%
app/core/middleware.py                            100%
app/models/database.py                            100%
app/config.py                                     100%
app/api/v1/schemas/responses.py                   100%
app/services/providers/google_provider.py          96%
app/main.py                                        97%
...
TOTAL                                              95%
```

### Test Structure

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions with realistic data
- **API tests**: Test HTTP endpoints end-to-end
- **Contract tests**: Validate API response schemas match frontend expectations
- **Database integration tests**: Test with edge cases and messy production-like data
- **Mocking**: Extensive use of mocks for external APIs

### Contract Tests (`test_api_contracts.py`)

Contract tests validate that API responses match the data structures the frontend depends on. These tests prevent bugs caused by schema mismatches:

**What they catch:**
- List fields returning `None` instead of empty lists (causing `'NoneType' object is not iterable`)
- Missing required fields in responses
- Incorrect data types
- Schema violations that break frontend assumptions

**Key tests:**
- `test_send_prompt_response_schema_validation`: Validates complete response structure
- `test_get_interaction_details_list_fields_never_none`: Ensures list fields are always iterable
- `test_nested_sources_in_search_queries_never_none`: Validates nested data structures
- `test_empty_response_data_handling`: Tests edge case of completely empty responses
- `test_citation_without_rank_is_valid`: Validates optional field handling

**Benefits:**
- Catches bugs before they reach frontend (would have caught commits 974518c, 6473e54)
- Documents API contract expectations
- Prevents regressions when modifying response schemas
- Validates Pydantic model defaults match frontend assumptions

### Database Integration Tests (`test_integration_database.py`)

Integration tests with realistic database fixtures simulate production scenarios including messy and corrupt data:

**Edge cases tested:**
- NULL foreign key relationships (orphaned records)
- Responses with NULL prompt_id (broken relationship chains)
- Search queries with no sources (empty result sets)
- Responses with no citations (direct answers without search)
- Mixed API and network_log mode data
- Data migration artifacts (missing fields, unknown models)
- Corrupted timestamps and invalid data

**What they catch:**
- Eager loading crashes with NULL relationships (Response.sources bug)
- N+1 query problems
- Cascading delete failures with orphaned data
- NULL constraint violations
- Query failures on corrupt data

**Key tests:**
- `test_eager_loading_with_null_relationships`: Validates eager loading doesn't crash with NULL FKs
- `test_get_recent_with_missing_relationships`: Tests broken relationship chains
- `test_mixed_api_and_network_log_data`: Validates dual data source support
- `test_data_migration_scenario`: Tests imported/migrated data handling
- `test_delete_with_orphaned_relationships`: Validates cascade deletes work correctly

**Benefits:**
- Production readiness - simulates real-world messy data
- Migration safety - validates data from schema changes
- Robustness - ensures graceful handling of corrupt data
- Would have caught the eager loading crash that required disabling Response.sources joinedload

## Deployment

### Production Considerations

1. **Environment Variables:**
   ```bash
   DEBUG=false
   LOG_LEVEL=WARNING
   DATABASE_URL=postgresql://...  # Use PostgreSQL in production
   ```

2. **Database:**
   - Use PostgreSQL or MySQL instead of SQLite
   - Set up connection pooling
   - Configure backups

3. **Security:**
   - Use environment variables for all secrets
   - Enable HTTPS
   - Configure CORS appropriately
   - Set up rate limiting
   - Use authentication if needed

4. **Monitoring:**
   - Set up logging aggregation
   - Monitor error rates
   - Track API performance
   - Set up alerts

5. **Scaling:**
   - Use multiple workers with Gunicorn
   - Set up load balancing
   - Cache frequent queries
   - Optimize database indexes

### Production Server

**With Gunicorn:**
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

**Environment:**
```bash
export DATABASE_URL=postgresql://user:pass@host/db
export LOG_LEVEL=WARNING
export DEBUG=false
```

## Troubleshooting

### Common Issues

**Database locked error:**
```
Solution: SQLite doesn't handle concurrent writes well.
Use PostgreSQL in production or ensure single writer.
```

**Import errors:**
```bash
# Ensure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**API key errors:**
```
- Check .env file exists and is in backend/ directory
- Verify API keys are valid
- Ensure no quotes around keys in .env
```

**Port already in use:**
```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn app.main:app --port 8001
```

### Debugging

**Enable debug logging:**
```bash
export LOG_LEVEL=DEBUG
uvicorn app.main:app --reload
```

**Check correlation IDs:**
```bash
# Every request gets a correlation ID in the response header
curl -i http://localhost:8000/api/v1/providers
# Look for: X-Correlation-ID: abc123-def456
```

**View logs:**
```bash
# Logs include correlation IDs for request tracing
tail -f logs/app.log | grep "correlation_id"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`pytest`)
5. Ensure coverage remains high (`pytest --cov`)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Review Checklist

- [ ] Tests added for new functionality
- [ ] All tests passing
- [ ] Coverage remains ≥95%
- [ ] Type hints added
- [ ] Docstrings written
- [ ] Error handling implemented
- [ ] Logging added for important operations
- [ ] API documentation updated if needed

## License

MIT

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- Review test examples in `tests/`

---

**Built with:** FastAPI, SQLAlchemy, Pydantic, Pytest
