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
DATABASE_URL=sqlite:///./tests/data/test.db

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

Get a paginated list of recent interactions with summary information.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 1 | Page number (1-indexed) |
| page_size | integer | No | 20 | Items per page (1-100) |
| data_source | string | No | null | Filter by source: "api" or "network_log" |
| provider | string | No | null | Filter by provider: "openai", "google", "anthropic" |
| model | string | No | null | Filter by model (e.g., "gpt-5.1") |
| date_from | string | No | null | Filter by created_at >= date_from (ISO 8601) |
| date_to | string | No | null | Filter by created_at <= date_to (ISO 8601) |

**Example Request:**
```
GET /api/v1/interactions/recent?page=1&page_size=10&provider=openai&model=gpt-5.1
```

**Response (200 OK):**
```json
{
  "items": [
    {
      "interaction_id": 123,
      "prompt": "What are the latest developments in AI?",
      "response_preview": "Recent AI developments include...",
      "provider": "OpenAI",
      "model": "gpt-5.1",
      "model_display_name": "GPT-5.1",
      "data_source": "api",
      "response_time_ms": 2341,
      "created_at": "2025-01-15T10:30:00Z",
      "source_count": 5,
      "citation_count": 3,
      "search_query_count": 2,
      "average_rank": 2.3,
      "extra_links_count": 1
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_items": 150,
    "total_pages": 15,
    "has_next": true,
    "has_prev": false
  }
}
```

**Notes:**
- Results are ordered by created_at (most recent first)
- Response includes pagination metadata for building UI navigation
- Summary includes counts and aggregates, not full nested data
- `average_rank` shows average position of cited sources (lower is better)
- `extra_links_count` shows citations not from search results
- Filters can be combined (e.g., provider + model + date range)

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

## TypeScript Type Definitions

For TypeScript/JavaScript developers, here are the type definitions for all API responses:

```typescript
// Source types
interface Source {
  url: string;
  title: string | null;
  domain: string;
  rank: number;
  pub_date?: string | null;
  search_description?: string | null;
  snippet_text?: string | null; // Deprecated alias for search_description
  internal_score?: number | null;
  metadata?: Record<string, any> | null;
}

interface Citation {
  url: string;
  title: string | null;
  rank: number | null;
  snippet_cited?: string | null;
  citation_confidence?: number | null;
  metadata?: Record<string, any> | null;
}

interface SearchQuery {
  query: string;
  sources: Source[];
  timestamp: string | null;
  order_index: number;
  internal_ranking_scores?: Record<string, any> | null;
  query_reformulations?: string[] | null;
}

// Pagination
interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// Interaction types
interface InteractionSummary {
  interaction_id: number;
  prompt: string;
  response_preview: string;
  provider: string;
  model: string;
  model_display_name: string | null;
  data_source: string;
  response_time_ms: number;
  created_at: string;
  source_count: number;
  citation_count: number;
  search_query_count: number;
  average_rank: number | null;
  extra_links_count: number;
}

interface SendPromptResponse {
  interaction_id: number;
  prompt: string;
  response_text: string;
  provider: string;
  model: string;
  model_display_name: string | null;
  data_source: string;
  response_time_ms: number;
  created_at: string;
  search_queries: SearchQuery[];
  all_sources: Source[];
  citations: Citation[];
  sources_found: number;
  sources_used: number;
  avg_rank: number | null;
  extra_links_count: number;
  raw_response?: Record<string, any> | null;
  metadata?: Record<string, any> | null;
}

interface PaginatedInteractionList {
  items: InteractionSummary[];
  pagination: PaginationMeta;
}

// Provider types
interface Provider {
  name: string;
  display_name: string;
  supported_models: string[];
  is_active: boolean;
}

// Request types
interface SendPromptRequest {
  prompt: string;
  model: string;
  data_mode?: 'api' | 'network_log';
  headless?: boolean;
}

// Error types
interface APIError {
  error: {
    message: string;
    code: string;
    details?: Record<string, any>;
  };
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

**cURL:**
```bash
curl -X POST http://localhost:8000/api/v1/interactions/send \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What are the latest breakthroughs in quantum computing?",
    "model": "gpt-5.1"
  }'
```

**TypeScript/JavaScript (fetch):**
```typescript
const response = await fetch('http://localhost:8000/api/v1/interactions/send', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    prompt: 'What are the latest breakthroughs in quantum computing?',
    model: 'gpt-5.1',
  }),
});

const data: SendPromptResponse = await response.json();
console.log(data.response_text);
console.log(`Found ${data.search_queries.length} search queries`);
```

**TypeScript/JavaScript (axios):**
```typescript
import axios from 'axios';

const { data } = await axios.post<SendPromptResponse>(
  'http://localhost:8000/api/v1/interactions/send',
  {
    prompt: 'What are the latest breakthroughs in quantum computing?',
    model: 'gpt-5.1',
  }
);

console.log(data.response_text);
console.log(`Response time: ${data.response_time_ms}ms`);
```

**React Example:**
```tsx
import { useState } from 'react';

function PromptForm() {
  const [result, setResult] = useState<SendPromptResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (prompt: string, model: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/interactions/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, model }),
      });

      if (!response.ok) {
        const error: APIError = await response.json();
        throw new Error(error.error.message);
      }

      const data: SendPromptResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {result && (
        <div>
          <h3>{result.provider} - {result.model}</h3>
          <p>{result.response_text}</p>
          <p>Response time: {result.response_time_ms}ms</p>
        </div>
      )}
    </div>
  );
}
```

**Response:**
```json
{
  "interaction_id": 456,
  "prompt": "What are the latest breakthroughs in quantum computing?",
  "response_text": "Recent quantum computing breakthroughs include...",
  "provider": "OpenAI",
  "model": "gpt-5.1",
  "model_display_name": "GPT-5.1",
  "data_source": "api",
  "response_time_ms": 3200,
  "created_at": "2025-01-15T11:00:00Z",
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
  "all_sources": [
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
  "sources_found": 1,
  "sources_used": 1,
  "avg_rank": 1.0,
  "extra_links_count": 0
}
```

### Example 2: Get Recent Interactions with Pagination

**cURL:**
```bash
curl "http://localhost:8000/api/v1/interactions/recent?page=1&page_size=10&provider=openai"
```

**TypeScript/JavaScript (fetch):**
```typescript
const params = new URLSearchParams({
  page: '1',
  page_size: '10',
  provider: 'openai',
});

const response = await fetch(
  `http://localhost:8000/api/v1/interactions/recent?${params}`
);

const data: PaginatedInteractionList = await response.json();

console.log(`Page ${data.pagination.page} of ${data.pagination.total_pages}`);
console.log(`Total items: ${data.pagination.total_items}`);

data.items.forEach(interaction => {
  console.log(`${interaction.model}: ${interaction.prompt}`);
});
```

**TypeScript/JavaScript (axios):**
```typescript
import axios from 'axios';

const { data } = await axios.get<PaginatedInteractionList>(
  'http://localhost:8000/api/v1/interactions/recent',
  {
    params: {
      page: 1,
      page_size: 10,
      provider: 'openai',
      model: 'gpt-5.1',
    },
  }
);

console.log(`Showing ${data.items.length} of ${data.pagination.total_items} total`);
```

**React Pagination Example:**
```tsx
import { useState, useEffect } from 'react';

function InteractionHistory() {
  const [data, setData] = useState<PaginatedInteractionList | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchInteractions = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          page: page.toString(),
          page_size: '20',
          provider: 'openai',
        });

        const response = await fetch(
          `http://localhost:8000/api/v1/interactions/recent?${params}`
        );
        const result: PaginatedInteractionList = await response.json();
        setData(result);
      } catch (error) {
        console.error('Failed to fetch interactions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchInteractions();
  }, [page]);

  if (loading) return <div>Loading...</div>;
  if (!data) return <div>No data</div>;

  return (
    <div>
      <h2>Interaction History</h2>

      {data.items.map(interaction => (
        <div key={interaction.interaction_id}>
          <h3>{interaction.model}</h3>
          <p>{interaction.prompt}</p>
          <small>{interaction.created_at}</small>
        </div>
      ))}

      <div className="pagination">
        <button
          onClick={() => setPage(p => p - 1)}
          disabled={!data.pagination.has_prev}
        >
          Previous
        </button>

        <span>
          Page {data.pagination.page} of {data.pagination.total_pages}
        </span>

        <button
          onClick={() => setPage(p => p + 1)}
          disabled={!data.pagination.has_next}
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

**Response:**
```json
{
  "items": [
    {
      "interaction_id": 456,
      "prompt": "What are the latest breakthroughs in quantum computing?",
      "response_preview": "Recent quantum computing breakthroughs include...",
      "provider": "OpenAI",
      "model": "gpt-5.1",
      "model_display_name": "GPT-5.1",
      "data_source": "api",
      "response_time_ms": 3200,
      "created_at": "2025-01-15T11:00:00Z",
      "source_count": 1,
      "citation_count": 1,
      "search_query_count": 1,
      "average_rank": 1.0,
      "extra_links_count": 0
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_items": 150,
    "total_pages": 15,
    "has_next": true,
    "has_prev": false
  }
}
```

### Example 3: Get Available Providers

**cURL:**
```bash
curl http://localhost:8000/api/v1/providers
```

**TypeScript/JavaScript (fetch):**
```typescript
const response = await fetch('http://localhost:8000/api/v1/providers');
const providers: Provider[] = await response.json();

providers.forEach(provider => {
  if (provider.is_active) {
    console.log(`${provider.display_name}:`);
    provider.supported_models.forEach(model => {
      console.log(`  - ${model}`);
    });
  }
});
```

**TypeScript/JavaScript (axios):**
```typescript
import axios from 'axios';

const { data } = await axios.get<Provider[]>(
  'http://localhost:8000/api/v1/providers'
);

const activeProviders = data.filter(p => p.is_active);
console.log(`Found ${activeProviders.length} active providers`);
```

**Response:**
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
    "supported_models": ["gemini-3-pro-preview", "gemini-2.5-flash"],
    "is_active": true
  }
]
```

### Example 4: Delete Interaction

**cURL:**
```bash
curl -X DELETE http://localhost:8000/api/v1/interactions/456
```

**TypeScript/JavaScript (fetch):**
```typescript
const response = await fetch(
  'http://localhost:8000/api/v1/interactions/456',
  {
    method: 'DELETE',
  }
);

if (response.status === 204) {
  console.log('Interaction deleted successfully');
} else if (response.status === 404) {
  const error: APIError = await response.json();
  console.error('Not found:', error.error.message);
}
```

**TypeScript/JavaScript (axios):**
```typescript
import axios from 'axios';

try {
  await axios.delete('http://localhost:8000/api/v1/interactions/456');
  console.log('Interaction deleted successfully');
} catch (error) {
  if (axios.isAxiosError(error) && error.response?.status === 404) {
    console.error('Interaction not found');
  } else {
    console.error('Failed to delete interaction');
  }
}
```

**React Example with Confirmation:**
```tsx
function DeleteButton({ interactionId }: { interactionId: number }) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this interaction?')) {
      return;
    }

    setDeleting(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/interactions/${interactionId}`,
        { method: 'DELETE' }
      );

      if (response.status === 204) {
        alert('Interaction deleted successfully');
        // Refresh list or navigate away
      } else if (response.status === 404) {
        alert('Interaction not found');
      }
    } catch (error) {
      alert('Failed to delete interaction');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <button onClick={handleDelete} disabled={deleting}>
      {deleting ? 'Deleting...' : 'Delete'}
    </button>
  );
}
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

## React/TypeScript Integration

### Creating an API Client Class

For React applications, we recommend creating a reusable API client:

```typescript
// api/llm-analysis-client.ts
class LLMAnalysisClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async sendPrompt(
    prompt: string,
    model: string
  ): Promise<SendPromptResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/interactions/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, model }),
    });

    if (!response.ok) {
      const error: APIError = await response.json();
      throw new Error(error.error.message);
    }

    return response.json();
  }

  async getInteractions(params?: {
    page?: number;
    page_size?: number;
    provider?: string;
    model?: string;
    data_source?: string;
  }): Promise<PaginatedInteractionList> {
    const queryParams = new URLSearchParams(
      Object.entries(params || {})
        .filter(([_, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    );

    const response = await fetch(
      `${this.baseUrl}/api/v1/interactions/recent?${queryParams}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch interactions');
    }

    return response.json();
  }

  async getInteraction(id: number): Promise<SendPromptResponse> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/interactions/${id}`
    );

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Interaction ${id} not found`);
      }
      throw new Error('Failed to fetch interaction');
    }

    return response.json();
  }

  async deleteInteraction(id: number): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/interactions/${id}`,
      { method: 'DELETE' }
    );

    if (!response.ok && response.status !== 404) {
      throw new Error('Failed to delete interaction');
    }
  }

  async getProviders(): Promise<Provider[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/providers`);

    if (!response.ok) {
      throw new Error('Failed to fetch providers');
    }

    return response.json();
  }
}

export const apiClient = new LLMAnalysisClient();
```

### React Hook Example

```typescript
// hooks/useInteractions.ts
import { useState, useEffect } from 'react';
import { apiClient } from '../api/llm-analysis-client';

export function useInteractions(page: number = 1) {
  const [data, setData] = useState<PaginatedInteractionList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await apiClient.getInteractions({ page, page_size: 20 });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [page]);

  return { data, loading, error };
}
```

---

## Changelog

### Version 1.1.0 (2025-12-07)
- Added pagination and filtering to GET /api/v1/interactions/recent
- Updated response format to include pagination metadata
- Added comprehensive TypeScript type definitions
- Added TypeScript/JavaScript code examples for all endpoints
- Added React integration examples and best practices
- Updated all data models to reflect current API schema

### Version 1.0.0 (2025-01-15)
- Initial release
- Support for OpenAI, Google, and Anthropic providers
- Interaction tracking and history
- Search query and citation analysis
- Comprehensive error handling
- 95% test coverage
