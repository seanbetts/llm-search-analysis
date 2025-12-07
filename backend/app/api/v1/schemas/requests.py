from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import re

from app.core.json_schemas import SourceMetadata, CitationMetadata, dump_metadata


class SendPromptRequest(BaseModel):
  """Request schema for sending a prompt to an LLM provider."""

  prompt: str = Field(
    ...,
    min_length=1,
    max_length=10000,
    description="The prompt text to send to the LLM",
    examples=["What are the latest developments in AI?"]
  )

  provider: str = Field(
    ...,
    description="LLM provider name (openai, google, anthropic, chatgpt)",
    examples=["openai"]
  )

  model: str = Field(
    ...,
    description="Model name to use",
    examples=["gpt-5.1", "gemini-2.0-flash-exp", "claude-3-7-sonnet-20250219"]
  )

  data_mode: str = Field(
    default="api",
    description="Data collection mode: 'api' or 'network_log'",
    examples=["api", "network_log"]
  )

  headless: bool = Field(
    default=True,
    description="Run browser in headless mode (for network_log mode only)"
  )

  @field_validator("prompt")
  @classmethod
  def validate_prompt(cls, v: str) -> str:
    """Validate prompt for XSS and basic security."""
    # Remove leading/trailing whitespace
    v = v.strip()

    # Check for empty prompt after stripping
    if not v:
      raise ValueError("Prompt cannot be empty or whitespace only")

    # Basic XSS prevention - check for script tags
    if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
      raise ValueError("Prompt contains disallowed script tags")

    # Check for other potentially dangerous HTML tags
    dangerous_tags = ["iframe", "object", "embed", "link", "style"]
    for tag in dangerous_tags:
      if re.search(rf"<{tag}.*?>", v, re.IGNORECASE):
        raise ValueError(f"Prompt contains disallowed tag: {tag}")

    return v

  @field_validator("provider")
  @classmethod
  def validate_provider(cls, v: str) -> str:
    """Validate provider name."""
    valid_providers = ["openai", "google", "anthropic", "chatgpt"]
    v_lower = v.lower()
    if v_lower not in valid_providers:
      raise ValueError(
        f"Invalid provider '{v}'. Must be one of: {', '.join(valid_providers)}"
      )
    return v_lower

  @field_validator("data_mode")
  @classmethod
  def validate_data_mode(cls, v: str) -> str:
    """Validate data collection mode."""
    valid_modes = ["api", "network_log"]
    v_lower = v.lower()
    if v_lower not in valid_modes:
      raise ValueError(
        f"Invalid data_mode '{v}'. Must be one of: {', '.join(valid_modes)}"
      )
    return v_lower

  @model_validator(mode='after')
  def validate_provider_model_match(self) -> 'SendPromptRequest':
    """Validate that provider matches the model."""
    # Import here to avoid circular dependency
    from app.services.providers.provider_factory import ProviderFactory

    # Get the provider that this model belongs to
    expected_provider = ProviderFactory.get_provider_for_model(self.model)

    if not expected_provider:
      raise ValueError(
        f"Model '{self.model}' is not supported. "
        f"Supported models: {', '.join(ProviderFactory.get_all_supported_models())}"
      )

    # Validate provider matches
    if self.provider != expected_provider:
      raise ValueError(
        f"Provider mismatch: model '{self.model}' belongs to provider '{expected_provider}', "
        f"but request specified provider '{self.provider}'"
      )

    return self

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "prompt": "What are the latest developments in quantum computing?",
          "provider": "openai",
          "model": "gpt-5.1",
          "data_mode": "api",
          "headless": True
        }
      ]
    }
  }


class BatchRequest(BaseModel):
  """Request schema for batch processing multiple prompts."""

  prompts: List[str] = Field(
    ...,
    min_length=1,
    max_length=100,
    description="List of prompts to process",
    examples=[["What is AI?", "What is ML?"]]
  )

  provider: str = Field(
    ...,
    description="LLM provider name (openai, google, anthropic, chatgpt)",
    examples=["openai"]
  )

  models: List[str] = Field(
    ...,
    min_length=1,
    description="List of models to test against",
    examples=[["gpt-5.1", "gpt-5.1-mini"]]
  )

  data_mode: str = Field(
    default="api",
    description="Data collection mode: 'api' or 'network_log'",
    examples=["api"]
  )

  headless: bool = Field(
    default=True,
    description="Run browser in headless mode (for network_log mode only)"
  )

  @field_validator("prompts")
  @classmethod
  def validate_prompts(cls, v: List[str]) -> List[str]:
    """Validate each prompt in the list."""
    if not v:
      raise ValueError("Prompts list cannot be empty")

    # Validate each prompt
    validated_prompts = []
    for i, prompt in enumerate(v):
      prompt = prompt.strip()
      if not prompt:
        raise ValueError(f"Prompt at index {i} is empty or whitespace only")
      if len(prompt) > 10000:
        raise ValueError(f"Prompt at index {i} exceeds maximum length of 10000 characters")
      validated_prompts.append(prompt)

    return validated_prompts

  @field_validator("provider")
  @classmethod
  def validate_provider(cls, v: str) -> str:
    """Validate provider name."""
    valid_providers = ["openai", "google", "anthropic", "chatgpt"]
    v_lower = v.lower()
    if v_lower not in valid_providers:
      raise ValueError(
        f"Invalid provider '{v}'. Must be one of: {', '.join(valid_providers)}"
      )
    return v_lower

  @field_validator("models")
  @classmethod
  def validate_models(cls, v: List[str]) -> List[str]:
    """Validate models list."""
    if not v:
      raise ValueError("Models list cannot be empty")
    return v

  @field_validator("data_mode")
  @classmethod
  def validate_data_mode(cls, v: str) -> str:
    """Validate data collection mode."""
    valid_modes = ["api", "network_log"]
    v_lower = v.lower()
    if v_lower not in valid_modes:
      raise ValueError(
        f"Invalid data_mode '{v}'. Must be one of: {', '.join(valid_modes)}"
      )
    return v_lower

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "prompts": [
            "What is artificial intelligence?",
            "Explain machine learning"
          ],
          "provider": "openai",
          "models": ["gpt-5.1", "gpt-5.1-mini"],
          "data_mode": "api",
          "headless": True
        }
      ]
    }
  }


class NetworkLogSource(BaseModel):
  """Typed structure for network-log sources."""

  model_config = ConfigDict(extra="forbid")

  url: str = Field(..., description="Source URL")
  title: Optional[str] = Field(None, description="Source title")
  domain: Optional[str] = Field(None, description="Domain name")
  rank: Optional[int] = Field(None, ge=1, description="Position in search results (1-indexed)")
  pub_date: Optional[str] = Field(None, description="ISO timestamp if available")
  snippet_text: Optional[str] = Field(None, description="Snippet associated with the source")
  internal_score: Optional[float] = Field(None, description="Internal ranking score")
  metadata: Optional[Dict[str, Any]] = Field(None, description="Provider metadata for this source")

  @field_validator("metadata")
  @classmethod
  def validate_metadata(cls, value: Optional[Dict[str, Any]]):
    return dump_metadata(SourceMetadata, value)


class NetworkLogCitation(BaseModel):
  """Typed structure for network-log citations."""

  model_config = ConfigDict(extra="forbid")

  url: str = Field(..., description="Citation URL")
  title: Optional[str] = Field(None, description="Citation title")
  rank: Optional[int] = Field(None, ge=1, description="Rank from search results")
  snippet_used: Optional[str] = Field(None, description="Snippet text used in the response")
  metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata about the citation")

  @field_validator("metadata")
  @classmethod
  def validate_metadata(cls, value: Optional[Dict[str, Any]]):
    return dump_metadata(CitationMetadata, value)


class NetworkLogSearchQuery(BaseModel):
  """Typed structure for search queries captured from network logs."""

  model_config = ConfigDict(extra="forbid")

  query: str = Field(..., description="Search query text")
  order_index: Optional[int] = Field(default=0, ge=0, description="Order of the query in the sequence")
  sources: List[NetworkLogSource] = Field(default_factory=list, description="Sources returned for this query")
  internal_ranking_scores: Optional[Dict[str, Any]] = Field(
    default=None,
    description="Provider-specific ranking metadata"
  )
  query_reformulations: Optional[List[str]] = Field(
    default=None,
    description="List of reformulated queries (if provided)"
  )

  @field_validator("internal_ranking_scores")
  @classmethod
  def validate_internal_scores(cls, value: Optional[Dict[str, Any]]):
    if value is None:
      return None
    if not isinstance(value, dict):
      raise ValueError("internal_ranking_scores must be an object")
    return value


class SaveNetworkLogRequest(BaseModel):
  """Request schema for saving network_log mode data captured by frontend."""

  provider: str = Field(
    ...,
    description="LLM provider name",
    examples=["openai"]
  )

  model: str = Field(
    ...,
    description="Model name used",
    examples=["chatgpt-free"]
  )

  prompt: str = Field(
    ...,
    min_length=1,
    max_length=10000,
    description="The prompt text",
    examples=["What is AI?"]
  )

  response_text: str = Field(
    ...,
    description="The response text from the LLM"
  )

  search_queries: List[NetworkLogSearchQuery] = Field(
    default_factory=list,
    description="List of search queries (with query text and sources)"
  )

  sources: List[NetworkLogSource] = Field(
    default_factory=list,
    description="All sources found (for network_log mode)"
  )

  citations: List[NetworkLogCitation] = Field(
    default_factory=list,
    description="Citations extracted from response"
  )

  response_time_ms: int = Field(
    ...,
    ge=0,
    description="Response time in milliseconds"
  )

  raw_response: Optional[Dict[str, Any]] = Field(
    None,
    description="Raw response data"
  )

  extra_links_count: int = Field(
    default=0,
    ge=0,
    description="Count of extra links (citations not from search)"
  )

  @field_validator("provider")
  @classmethod
  def validate_provider(cls, v: str) -> str:
    """Validate provider name."""
    valid_providers = ["openai", "google", "anthropic", "chatgpt"]
    v_lower = v.lower()
    if v_lower not in valid_providers:
      raise ValueError(
        f"Invalid provider '{v}'. Must be one of: {', '.join(valid_providers)}"
      )
    return v_lower

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "provider": "openai",
          "model": "chatgpt-free",
          "prompt": "What is AI?",
          "response_text": "AI stands for Artificial Intelligence...",
          "search_queries": [
            {
              "query": "artificial intelligence definition",
              "sources": []
            }
          ],
          "sources": [
            {
              "url": "https://example.com",
              "title": "Example Source",
              "domain": "example.com",
              "rank": 1
            }
          ],
          "citations": [
            {
              "url": "https://example.com",
              "title": "Example Citation",
              "rank": 1
            }
          ],
          "response_time_ms": 5000,
          "raw_response": {},
          "extra_links_count": 0
        }
      ]
    }
  }
