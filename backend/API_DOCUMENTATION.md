# LLM Search Analysis API Documentation

API for analyzing LLM search capabilities across different providers (OpenAI, Google, Anthropic).

**Version:** 1.0.0
**Base URL:** `http://localhost:8000`

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health & Status](#health--status)
  - [Providers](#providers)
  - [Interactions](#interactions)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Examples](#examples)

## Overview

This API provides endpoints to:
- Send prompts to LLM providers with web search capabilities
- Track and analyze search queries, sources, and citations
- Compare LLM search performance across providers
- Store and retrieve interaction history

### Supported Providers

- **OpenAI** (GPT-5.1, GPT-5-mini, GPT-5-nano)
- **Google** (Gemini 3 Pro, Gemini 2.5 Flash, Gemini 2.5 Flash Lite)
- **Anthropic** (Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4.1)

## Authentication

Currently, the API uses API keys configured server-side via environment variables. No client authentication is required.

### Required Environment Variables

```bash
# API Keys (at least one required)
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=sqlite:///./test.db

# Server
LOG_LEVEL=INFO
DEBUG=false
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8501"]
```

## Endpoints

### Health & Status

#### GET /

Root endpoint - API information.

**Response:**
```json
{
  "name": "LLM Search Analysis API",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs"
}
```

#### GET /health

Health check endpoint - verifies API and database connectivity.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "database": "error",
  "error": "Connection refused"
}
```

---

### Providers

#### GET /api/v1/providers

Get list of all configured LLM providers with their supported models.

**Query Parameters:** None

**Response (200 OK):**
```json
[
  {
    "name": "openai",
    "display_name": "OpenAI",
    "supported_models": ["gpt-5.1", "gpt-5-mini", "gpt-5-nano"],
    "is_active": true
  },
  {
    "name": "google",
    "display_name": "Google",
    "supported_models": ["gemini-3-pro-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    "is_active": true
  },
  {
    "name": "anthropic",
    "display_name": "Anthropic",
    "supported_models": ["claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001", "claude-opus-4-1-20250805"],
    "is_active": true
  }
]
```

**Notes:**
- Only providers with configured API keys are returned
- `is_active` indicates whether the provider is currently available

#### GET /api/v1/providers/models

Get flat list of all available models across all configured providers.

**Query Parameters:** None

**Response (200 OK):**
```json
[
  "gpt-5.1",
  "gpt-5-mini",
  "gpt-5-nano",
  "gemini-3-pro-preview",
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "claude-sonnet-4-5-20250929",
  "claude-haiku-4-5-20251001",
  "claude-opus-4-1-20250805"
]
```

---

### Interactions

#### POST /api/v1/interactions/send

Send a prompt to an LLM provider and get response with search data.

**Request Body:**
```json
{
  "prompt": "What are the latest developments in AI?",
  "model": "gpt-5.1"
}
```

**Request Schema:**
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| prompt | string | Yes | The user's prompt | 1-10000 chars, no XSS |
| model | string | Yes | Model identifier | Must be supported model |

**Response (200 OK):**
```json
{
  "interaction_id": 123,
  "prompt": "What are the latest developments in AI?",
  "response_text": "Recent AI developments include...",
  "provider": "openai",
  "model": "gpt-5.1",
  "data_source": "api",
  "response_time_ms": 2341,
  "timestamp": "2025-01-15T10:30:00Z",
  "search_queries": [
    {
      "query": "latest AI developments 2025",
      "sources": [
        {
          "url": "https://example.com/ai-news",
          "title": "AI News 2025",
          "domain": "example.com",
          "rank": 1
        }
      ],
      "timestamp": "2025-01-15T10:30:00Z",
      "order_index": 0
    }
  ],
  "sources": [
    {
      "url": "https://example.com/ai-news",
      "title": "AI News 2025",
      "domain": "example.com",
      "rank": 1
    }
  ],
  "citations": [
    {
      "url": "https://example.com/ai-news",
      "title": "AI News 2025",
      "rank": 1
    }
  ],
  "source_count": 1,
  "citation_count": 1,
  "search_query_count": 1
}
```

**Error Responses:**

**400 Bad Request - Model Not Supported:**
```json
{
  "error": {
    "message": "Model 'invalid-model' is not supported",
    "code": "INVALID_REQUEST",
    "details": {
      "model": "invalid-model"
    }
  }
}
```

**400 Bad Request - API Key Missing:**
```json
{
  "error": {
    "message": "API key for openai is not configured",
    "code": "INVALID_REQUEST",
    "details": {
      "provider": "openai",
      "solution": "Add the API key to your .env file"
    }
  }
}
```

**422 Validation Error:**
```json
{
  "error": {
    "message": "Request validation failed",
    "code": "VALIDATION_ERROR",
    "details": {
      "errors": [
        {
          "field": "body -> prompt",
          "message": "Field required",
          "type": "missing"
        }
      ]
    }
  }
}
```

**502 Bad Gateway - Provider API Error:**
```json
{
  "error": {
    "message": "openai provider error: API rate limit exceeded",
    "code": "EXTERNAL_SERVICE_ERROR",
    "details": {
      "service": "openai provider"
    }
  }
}
```

#### GET /api/v1/interactions/recent

Get a list of recent interactions with summary information.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| limit | integer | No | 50 | Max results (1-1000) |
| data_source | string | No | null | Filter by source: "api" or "network_log" |

**Example Request:**
```
GET /api/v1/interactions/recent?limit=10&data_source=api
```

**Response (200 OK):**
```json
[
  {
    "interaction_id": 123,
    "prompt": "What are the latest developments in AI?",
    "response_text": "Recent AI developments include...",
    "provider": "openai",
    "model": "gpt-5.1",
    "data_source": "api",
    "response_time_ms": 2341,
    "timestamp": "2025-01-15T10:30:00Z",
    "source_count": 5,
    "citation_count": 3,
    "search_query_count": 2,
    "average_citation_rank": 2.3
  }
]
```

**Notes:**
- Results are ordered by timestamp (most recent first)
- Summary includes counts and aggregates, not full nested data
- `average_citation_rank` shows average position of cited sources

#### GET /api/v1/interactions/{interaction_id}

Get full details of a specific interaction.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| interaction_id | integer | The interaction ID |

**Response (200 OK):**
```json
{
  "interaction_id": 123,
  "prompt": "What are the latest developments in AI?",
  "response_text": "Recent AI developments include...",
  "provider": "openai",
  "model": "gpt-5.1",
  "data_source": "api",
  "response_time_ms": 2341,
  "timestamp": "2025-01-15T10:30:00Z",
  "search_queries": [
    {
      "query": "latest AI developments 2025",
      "sources": [
        {
          "url": "https://example.com/ai-news",
          "title": "AI News 2025",
          "domain": "example.com",
          "rank": 1
        }
      ],
      "timestamp": "2025-01-15T10:30:00Z",
      "order_index": 0
    }
  ],
  "sources": [
    {
      "url": "https://example.com/ai-news",
      "title": "AI News 2025",
      "domain": "example.com",
      "rank": 1
    }
  ],
  "citations": [
    {
      "url": "https://example.com/ai-news",
      "title": "AI News 2025",
      "rank": 1
    }
  ],
  "source_count": 1,
  "citation_count": 1,
  "search_query_count": 1
}
```

**Error Responses:**

**404 Not Found:**
```json
{
  "error": {
    "message": "Interaction with ID 999 not found",
    "code": "RESOURCE_NOT_FOUND",
    "details": {
      "resource_type": "Interaction",
      "resource_id": "999"
    }
  }
}
```

#### DELETE /api/v1/interactions/{interaction_id}

Delete an interaction and all associated data.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| interaction_id | integer | The interaction ID |

**Response (204 No Content):**
No response body on success.

**Error Responses:**

**404 Not Found:**
```json
{
  "error": {
    "message": "Interaction with ID 999 not found",
    "code": "RESOURCE_NOT_FOUND",
    "details": {
      "resource_type": "Interaction",
      "resource_id": "999"
    }
  }
}
```

---

## Data Models

### Source

Represents a web source retrieved during search.

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "domain": "example.com",
  "rank": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| url | string | Source URL |
| title | string \| null | Source title |
| domain | string | Extracted domain |
| rank | integer | Position in search results (1-indexed) |

### Citation

Represents a source that was explicitly cited in the response.

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "rank": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| url | string | Citation URL |
| title | string \| null | Citation title |
| rank | integer \| null | Matching source rank if available |

### SearchQuery

Represents a search query made by the LLM.

```json
{
  "query": "latest AI developments",
  "sources": [/* Source objects */],
  "timestamp": "2025-01-15T10:30:00Z",
  "order_index": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| query | string | Search query string |
| sources | Source[] | Sources returned for this query |
| timestamp | string \| null | ISO 8601 timestamp |
| order_index | integer | Query order (0-indexed) |

### InteractionSummary

Summary view of an interaction (used in list responses).

```json
{
  "interaction_id": 123,
  "prompt": "What are the latest developments in AI?",
  "response_text": "Recent AI developments include...",
  "provider": "openai",
  "model": "gpt-5.1",
  "data_source": "api",
  "response_time_ms": 2341,
  "timestamp": "2025-01-15T10:30:00Z",
  "source_count": 5,
  "citation_count": 3,
  "search_query_count": 2,
  "average_citation_rank": 2.3
}
```

### SendPromptResponse

Full interaction response with all nested data.

```json
{
  "interaction_id": 123,
  "prompt": "What are the latest developments in AI?",
  "response_text": "Recent AI developments include...",
  "provider": "openai",
  "model": "gpt-5.1",
  "data_source": "api",
  "response_time_ms": 2341,
  "timestamp": "2025-01-15T10:30:00Z",
  "search_queries": [/* SearchQuery objects */],
  "sources": [/* Source objects */],
  "citations": [/* Citation objects */],
  "source_count": 5,
  "citation_count": 3,
  "search_query_count": 2
}
```

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "message": "Human-readable error message",
    "code": "ERROR_CODE",
    "details": {
      "key": "Additional context"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| VALIDATION_ERROR | 422 | Request validation failed |
| INVALID_REQUEST | 400 | Invalid request (bad model, missing key, etc.) |
| RESOURCE_NOT_FOUND | 404 | Requested resource not found |
| DATABASE_ERROR | 500 | Database operation failed |
| EXTERNAL_SERVICE_ERROR | 502 | Provider API error |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error |

### Correlation IDs

Every request receives a correlation ID for tracing:

**Response Header:**
```
X-Correlation-ID: abc123-def456-ghi789
```

Use this ID when reporting issues or debugging.

---

## Examples

### Example 1: Send Prompt to OpenAI

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/interactions/send \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What are the latest breakthroughs in quantum computing?",
    "model": "gpt-5.1"
  }'
```

**Response:**
```json
{
  "interaction_id": 456,
  "prompt": "What are the latest breakthroughs in quantum computing?",
  "response_text": "Recent quantum computing breakthroughs include...",
  "provider": "openai",
  "model": "gpt-5.1",
  "data_source": "api",
  "response_time_ms": 3200,
  "timestamp": "2025-01-15T11:00:00Z",
  "search_queries": [
    {
      "query": "quantum computing breakthroughs 2025",
      "sources": [
        {
          "url": "https://quantumtech.com/breakthroughs",
          "title": "Quantum Breakthroughs 2025",
          "domain": "quantumtech.com",
          "rank": 1
        }
      ],
      "timestamp": "2025-01-15T11:00:00Z",
      "order_index": 0
    }
  ],
  "sources": [
    {
      "url": "https://quantumtech.com/breakthroughs",
      "title": "Quantum Breakthroughs 2025",
      "domain": "quantumtech.com",
      "rank": 1
    }
  ],
  "citations": [
    {
      "url": "https://quantumtech.com/breakthroughs",
      "title": "Quantum Breakthroughs 2025",
      "rank": 1
    }
  ],
  "source_count": 1,
  "citation_count": 1,
  "search_query_count": 1
}
```

### Example 2: Get Recent Interactions

**Request:**
```bash
curl http://localhost:8000/api/v1/interactions/recent?limit=5
```

**Response:**
```json
[
  {
    "interaction_id": 456,
    "prompt": "What are the latest breakthroughs in quantum computing?",
    "response_text": "Recent quantum computing breakthroughs include...",
    "provider": "openai",
    "model": "gpt-5.1",
    "data_source": "api",
    "response_time_ms": 3200,
    "timestamp": "2025-01-15T11:00:00Z",
    "source_count": 1,
    "citation_count": 1,
    "search_query_count": 1,
    "average_citation_rank": 1.0
  }
]
```

### Example 3: Get Available Providers

**Request:**
```bash
curl http://localhost:8000/api/v1/providers
```

**Response:**
```json
[
  {
    "name": "openai",
    "display_name": "OpenAI",
    "supported_models": ["gpt-5.1", "gpt-5-mini", "gpt-5-nano"],
    "is_active": true
  }
]
```

### Example 4: Delete Interaction

**Request:**
```bash
curl -X DELETE http://localhost:8000/api/v1/interactions/456
```

**Response:**
```
HTTP/1.1 204 No Content
```

---

## Interactive API Documentation

The API provides interactive Swagger documentation at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

These interfaces allow you to:
- Browse all endpoints
- Try API calls directly from the browser
- See request/response schemas
- View example payloads

---

## Rate Limiting

Currently, there are no API-level rate limits. However, be aware of:
- Provider API rate limits (OpenAI, Google, Anthropic)
- Database connection limits
- Server resource constraints

---

## Changelog

### Version 1.0.0 (2025-01-15)
- Initial release
- Support for OpenAI, Google, and Anthropic providers
- Interaction tracking and history
- Search query and citation analysis
- Comprehensive error handling
- 95% test coverage
