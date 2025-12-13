"""Response schemas for API endpoints.

This module defines Pydantic models for API responses returned to clients.
All response schemas provide consistent structure and automatic OpenAPI
documentation.

Key Schemas:
- SendPromptResponse: Full interaction data after sending a prompt
- InteractionResponse: Individual interaction details
- PaginatedInteractionList: Paginated list of interactions
- Provider/ModelResponse: Available providers and models
- Source/SearchQuery: Search data embedded in responses

The schemas ensure:
- Consistent response format across all endpoints
- Type-safe serialization from database models
- Rich metadata for API consumers
- Automatic OpenAPI/Swagger documentation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _empty_source_list() -> List[Source]:
  """Return a new list for source fields."""
  return []


def _empty_search_query_list() -> List[SearchQuery]:
  """Return a new list for search query fields."""
  return []


def _empty_citation_list() -> List[Citation]:
  """Return a new list for citation fields."""
  return []


def _empty_tag_list() -> List[str]:
  """Return a new list for tag fields."""
  return []


class Source(BaseModel):
  """Source/URL fetched during search."""

  url: str = Field(..., description="Source URL")
  title: Optional[str] = Field(None, description="Source title")
  domain: Optional[str] = Field(None, description="Domain name")
  rank: Optional[int] = Field(None, ge=1, description="Position in search results (1-indexed)")
  pub_date: Optional[str] = Field(None, description="ISO-formatted publication date")

  # Network log exclusive fields
  snippet_text: Optional[str] = Field(None, description="Snippet extracted by model")
  internal_score: Optional[float] = Field(None, description="Internal relevance score")
  metadata: Optional[Dict[str, Any]] = Field(None, description="Full metadata from logs")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "url": "https://example.com/article",
          "title": "Understanding AI",
          "domain": "example.com",
          "rank": 1,
          "pub_date": "2024-01-15"
        }
      ]
    }
  }


class SearchQuery(BaseModel):
  """Search query made during response generation."""

  query: str = Field(..., description="The search query text")
  sources: List[Source] = Field(default_factory=_empty_source_list, description="Sources found for this query")
  timestamp: Optional[str] = Field(None, description="When the query was made")
  order_index: int = Field(default=0, ge=0, description="Order in the query sequence")

  # Network log exclusive fields
  internal_ranking_scores: Optional[Dict[str, Any]] = Field(
    None,
    description="Internal ranking scores from logs"
  )
  query_reformulations: Optional[List[str]] = Field(
    None,
    description="Query evolution steps"
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "query": "latest AI developments 2024",
          "sources": [],
          "order_index": 0
        }
      ]
    }
  }


class Citation(BaseModel):
  """Citation/source actually used in the response."""

  url: str = Field(..., description="Citation URL")
  title: Optional[str] = Field(None, description="Citation title")
  rank: Optional[int] = Field(None, ge=1, description="Rank from original search results")
  text_snippet: Optional[str] = Field(None, description="Text snippet from citation")
  start_index: Optional[int] = Field(None, ge=0, description="Start offset of cited text")
  end_index: Optional[int] = Field(None, ge=0, description="End offset of cited text")
  published_at: Optional[str] = Field(None, description="Published date provided by provider")

  # Network log exclusive fields
  snippet_cited: Optional[str] = Field(None, description="Exact snippet cited")
  citation_confidence: Optional[float] = Field(
    None,
    ge=0.0,
    le=1.0,
    description="Citation confidence score"
  )
  metadata: Optional[Dict[str, Any]] = Field(
    None,
    description="Additional citation metadata"
  )
  function_tags: List[str] = Field(
    default_factory=_empty_tag_list,
    description="Functional roles applied to this citation"
  )
  stance_tags: List[str] = Field(
    default_factory=_empty_tag_list,
    description="Stance annotations describing how the citation relates to the claim"
  )
  provenance_tags: List[str] = Field(
    default_factory=_empty_tag_list,
    description="Provenance annotations derived from citation metadata"
  )
  influence_summary: Optional[str] = Field(
    None,
    description="Short summary describing how the source influenced the claim"
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "url": "https://example.com/article",
          "title": "Understanding AI",
          "rank": 1
        }
      ]
    }
  }


class SendPromptResponse(BaseModel):
  """Full response from sending a prompt to an LLM."""

  # Core response data
  prompt: str = Field(..., description="The original prompt text")
  response_text: str = Field(..., description="The LLM's response text")
  search_queries: List[SearchQuery] = Field(
    default_factory=_empty_search_query_list,
    description="Search queries made during generation"
  )
  citations: List[Citation] = Field(
    default_factory=_empty_citation_list,
    description="Citations used in the response"
  )
  all_sources: Optional[List[Source]] = Field(
    default_factory=_empty_source_list,
    description=(
      "All sources aggregated from all search queries (API mode) or directly "
      "from response (web capture mode). Always populated for consistent "
      "frontend handling."
    )
  )

  # Metadata
  provider: str = Field(..., description="LLM provider name")
  model: str = Field(..., description="Model name used")
  model_display_name: Optional[str] = Field(
    None,
    description="Formatted display name for the model"
  )
  response_time_ms: Optional[int] = Field(None, ge=0, description="Response time in milliseconds")
  data_source: str = Field(default="api", description="Data collection mode (api/web)")

  # Computed metrics
  sources_found: int = Field(
    default=0,
    ge=0,
    description="Total number of sources from search queries"
  )
  sources_used: int = Field(
    default=0,
    ge=0,
    description="Number of citations with rank (from search results)"
  )
  avg_rank: Optional[float] = Field(
    None,
    ge=0,
    description="Average rank of citations from search results"
  )
  extra_links_count: int = Field(
    default=0,
    ge=0,
    description="Links in response not from search results"
  )

  # Database IDs (returned after saving)
  interaction_id: Optional[int] = Field(None, description="Database interaction ID")
  created_at: Optional[datetime] = Field(None, description="When the interaction was created")

  # Raw data
  raw_response: Optional[Dict[str, Any]] = Field(None, description="Raw API response")
  metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "prompt": "What are the latest developments in AI?",
          "response_text": "Artificial intelligence has seen rapid development...",
          "search_queries": [],
          "citations": [],
          "provider": "openai",
          "model": "gpt-4o",
          "response_time_ms": 1500,
          "data_source": "api",
          "sources_found": 5,
          "sources_used": 3,
          "avg_rank": 2.3,
          "extra_links_count": 1
        }
      ]
    }
  }


class InteractionSummary(BaseModel):
  """Summary of an interaction for list views."""

  interaction_id: int = Field(..., description="Database interaction ID")
  prompt: str = Field(..., description="The prompt text")
  provider: str = Field(..., description="LLM provider name")
  model: str = Field(..., description="Model name used")
  model_display_name: Optional[str] = Field(
    None,
    description="Formatted display name for the model"
  )
  response_preview: str = Field(..., description="First 200 chars of response")

  search_query_count: int = Field(default=0, ge=0, description="Number of search queries")
  source_count: int = Field(default=0, ge=0, description="Number of sources found")
  citation_count: int = Field(default=0, ge=0, description="Number of citations used")
  average_rank: Optional[float] = Field(None, description="Average rank of citations")
  extra_links_count: int = Field(
    default=0,
    ge=0,
    description="Number of extra links not from search"
  )

  response_time_ms: Optional[int] = Field(None, ge=0, description="Response time in milliseconds")
  data_source: str = Field(default="api", description="Data collection mode")
  created_at: datetime = Field(..., description="When the interaction was created")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "interaction_id": 1,
          "prompt": "What is artificial intelligence?",
          "provider": "openai",
          "model": "gpt-4o",
          "response_preview": (
            "Artificial intelligence (AI) is the simulation of human intelligence..."
          ),
          "search_query_count": 2,
          "source_count": 5,
          "citation_count": 3,
          "average_rank": 2.5,
          "response_time_ms": 1500,
          "data_source": "api",
          "created_at": "2024-01-15T10:30:00Z"
        }
      ]
    }
  }


class QueryHistoryStats(BaseModel):
  """Aggregate metrics for the entire query history."""

  analyses: int = Field(..., ge=0, description="Total number of recorded analyses")
  avg_response_time_ms: Optional[float] = Field(
    None,
    ge=0,
    description="Average response time across all analyses"
  )
  avg_searches: Optional[float] = Field(
    None,
    ge=0,
    description="Average number of search queries per analysis"
  )
  avg_sources_found: Optional[float] = Field(
    None,
    ge=0,
    description="Average number of sources found"
  )
  avg_sources_used: Optional[float] = Field(
    None,
    ge=0,
    description="Average number of sources cited"
  )
  avg_rank: Optional[float] = Field(
    None,
    ge=0,
    description="Average citation rank"
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "analyses": 120,
          "avg_response_time_ms": 18500.5,
          "avg_searches": 4.2,
          "avg_sources_found": 12.7,
          "avg_sources_used": 5.8,
          "avg_rank": 3.1,
        }
      ]
    }
  }


class PaginationMeta(BaseModel):
  """Pagination metadata for list responses."""

  page: int = Field(..., ge=1, description="Current page number (1-indexed)")
  page_size: int = Field(..., ge=1, le=100, description="Number of items per page")
  total_items: int = Field(..., ge=0, description="Total number of items across all pages")
  total_pages: int = Field(..., ge=0, description="Total number of pages")
  has_next: bool = Field(..., description="Whether there is a next page available")
  has_prev: bool = Field(..., description="Whether there is a previous page available")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "page": 1,
          "page_size": 10,
          "total_items": 150,
          "total_pages": 15,
          "has_next": True,
          "has_prev": False
        }
      ]
    }
  }


class PaginatedInteractionList(BaseModel):
  """Paginated list of interaction summaries."""

  items: List[InteractionSummary] = Field(
    default_factory=list,
    description="List of interaction summaries for current page"
  )
  pagination: PaginationMeta = Field(..., description="Pagination metadata")
  stats: Optional[QueryHistoryStats] = Field(
    default=None,
    description="Aggregate metrics for the entire history dataset"
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "items": [
            {
              "interaction_id": 42,
              "prompt": "What is the weather today?",
              "provider": "openai",
              "model": "gpt-4o",
              "model_display_name": "GPT-4o",
              "response_preview": "I don't have access to real-time weather data...",
              "search_query_count": 2,
              "source_count": 5,
              "citation_count": 3,
              "average_rank": 2.5,
              "extra_links_count": 0,
              "response_time_ms": 3500,
              "data_source": "api",
              "created_at": "2024-01-15T10:30:00Z"
            }
          ],
          "pagination": {
            "page": 1,
            "page_size": 10,
            "total_items": 150,
            "total_pages": 15,
            "has_next": True,
            "has_prev": False
          }
        }
      ]
    }
  }


class BatchStatus(BaseModel):
  """Status of a batch processing request."""

  batch_id: str = Field(..., description="Unique batch identifier")
  total_tasks: int = Field(..., ge=1, description="Total number of tasks")
  completed_tasks: int = Field(default=0, ge=0, description="Number of completed tasks")
  failed_tasks: int = Field(default=0, ge=0, description="Number of failed tasks")
  status: str = Field(
    ...,
    description="Batch status (pending, processing, completed, failed, cancelled)"
  )
  cancel_reason: Optional[str] = Field(
    default=None,
    description="Reason provided when the batch was cancelled"
  )

  results: List[SendPromptResponse] = Field(
    default_factory=list,
    description="Completed results"
  )
  errors: List[Dict[str, Any]] = Field(
    default_factory=list,
    description="Error details for failed tasks"
  )

  started_at: Optional[datetime] = Field(None, description="When batch started")
  completed_at: Optional[datetime] = Field(None, description="When batch completed")
  estimated_completion: Optional[datetime] = Field(
    None,
    description="Estimated completion time"
  )

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "batch_id": "batch_123",
          "total_tasks": 10,
          "completed_tasks": 7,
          "failed_tasks": 1,
          "status": "processing",
          "cancel_reason": None,
          "results": [],
          "errors": [],
          "started_at": "2024-01-15T10:30:00Z"
        }
      ]
    }
  }


class ProviderInfo(BaseModel):
  """Information about an available LLM provider."""

  name: str = Field(..., description="Provider name (internal)")
  display_name: str = Field(..., description="Provider display name")
  is_active: bool = Field(..., description="Whether provider is currently active")
  supported_models: List[str] = Field(..., description="List of supported models")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "name": "openai",
          "display_name": "OpenAI",
          "is_active": True,
          "supported_models": ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini"]
        }
      ]
    }
  }


class HealthResponse(BaseModel):
  """Health check response."""

  status: str = Field(..., description="Health status (healthy/unhealthy)")
  version: str = Field(..., description="API version")
  database: str = Field(..., description="Database connection status")
  timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "status": "healthy",
          "version": "1.0.0",
          "database": "connected",
          "timestamp": "2024-01-15T10:30:00Z"
        }
      ]
    }
  }


class ErrorResponse(BaseModel):
  """Error response schema."""

  status: str = Field(default="error", description="Response status")
  message: str = Field(..., description="Error message")
  detail: Optional[str] = Field(None, description="Detailed error information")
  code: Optional[str] = Field(None, description="Error code")

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "status": "error",
          "message": "Invalid request",
          "detail": "Prompt cannot be empty",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
