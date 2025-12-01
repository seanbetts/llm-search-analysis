from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
  sources: List[Source] = Field(default_factory=list, description="Sources found for this query")
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

  # Network log exclusive fields
  snippet_used: Optional[str] = Field(None, description="Exact snippet cited")
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
    default_factory=list,
    description="Search queries made during generation"
  )
  citations: List[Citation] = Field(
    default_factory=list,
    description="Citations used in the response"
  )
  all_sources: Optional[List[Source]] = Field(
    default=None,
    description="All sources (for network_log mode, where sources are not linked to search queries)"
  )

  # Metadata
  provider: str = Field(..., description="LLM provider name")
  model: str = Field(..., description="Model name used")
  response_time_ms: Optional[int] = Field(None, ge=0, description="Response time in milliseconds")
  data_source: str = Field(default="api", description="Data collection mode (api/network_log)")
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
          "response_text": "Artificial intelligence has seen rapid development...",
          "search_queries": [],
          "citations": [],
          "provider": "openai",
          "model": "gpt-4o",
          "response_time_ms": 1500,
          "data_source": "api"
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
  response_preview: str = Field(..., description="First 200 chars of response")

  search_query_count: int = Field(default=0, ge=0, description="Number of search queries")
  source_count: int = Field(default=0, ge=0, description="Number of sources found")
  citation_count: int = Field(default=0, ge=0, description="Number of citations used")
  average_rank: Optional[float] = Field(None, description="Average rank of citations")
  extra_links_count: int = Field(default=0, ge=0, description="Number of extra links not from search")

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
          "response_preview": "Artificial intelligence (AI) is the simulation of human intelligence...",
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


class BatchStatus(BaseModel):
  """Status of a batch processing request."""

  batch_id: str = Field(..., description="Unique batch identifier")
  total_tasks: int = Field(..., ge=1, description="Total number of tasks")
  completed_tasks: int = Field(default=0, ge=0, description="Number of completed tasks")
  failed_tasks: int = Field(default=0, ge=0, description="Number of failed tasks")
  status: str = Field(
    ...,
    description="Batch status (pending, processing, completed, failed)"
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
