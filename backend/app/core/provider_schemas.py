"""
Pydantic schemas for validating provider raw_response payloads.

Each provider (OpenAI, Google, Anthropic) emits a slightly different JSON
shape for its responses. These models capture the structures we persist so
we can enforce consistency before storing blobs in SQLite.
"""

from __future__ import annotations

from base64 import b64encode
from typing import Any, Dict, List, Mapping, Optional
from pydantic import BaseModel, ConfigDict, Field


class _BaseModel(BaseModel):
  """Base model with permissive extras but without alias generation."""

  model_config = ConfigDict(extra="allow", use_enum_values=True)


# ---------------------------------------------------------------------------
# OpenAI Responses API payloads
# ---------------------------------------------------------------------------

class OpenAIUrlSource(_BaseModel):
  """Source URL found during OpenAI web search."""

  url: Optional[str] = None
  title: Optional[str] = None
  type: Optional[str] = None


class OpenAIWebSearchAction(_BaseModel):
  """Web search action performed by OpenAI model."""

  type: Optional[str] = None
  query: Optional[str] = None
  sources: Optional[List[OpenAIUrlSource]] = None


class OpenAIAnnotation(_BaseModel):
  """Citation annotation in OpenAI response text."""

  type: Optional[str] = None
  url: Optional[str] = None
  title: Optional[str] = None
  start_index: Optional[int] = Field(default=None, ge=0)
  end_index: Optional[int] = Field(default=None, ge=0)


class OpenAIContentItem(_BaseModel):
  """Content block in OpenAI output with optional annotations."""

  type: str
  text: Optional[str] = None
  annotations: Optional[List[OpenAIAnnotation]] = None


class OpenAIOutputItem(_BaseModel):
  """Individual output item from OpenAI response."""

  type: str
  status: Optional[str] = None
  action: Optional[OpenAIWebSearchAction] = None
  content: Optional[List[OpenAIContentItem]] = None


class OpenAIResponse(_BaseModel):
  """Top-level OpenAI Responses API response structure."""

  id: str
  model: str
  output: List[OpenAIOutputItem]


# ---------------------------------------------------------------------------
# Anthropic Claude payloads
# ---------------------------------------------------------------------------

class AnthropicCitation(_BaseModel):
  """Citation embedded in Anthropic response text."""

  url: Optional[str] = None
  title: Optional[str] = None


class AnthropicTextBlock(_BaseModel):
  """Text content block with inline citations from Anthropic."""

  type: str
  text: Optional[str] = None
  citations: Optional[List[AnthropicCitation]] = None


class AnthropicServerToolUse(_BaseModel):
  """Server-side tool invocation from Anthropic model."""

  type: str
  name: Optional[str] = None
  input: Optional[Dict[str, Any]] = None


class AnthropicSearchResult(_BaseModel):
  """Individual search result from Anthropic web search."""

  url: Optional[str] = None
  title: Optional[str] = None


class AnthropicWebSearchResult(_BaseModel):
  """Web search tool result containing multiple search results."""

  type: str
  content: Optional[List[AnthropicSearchResult]] = None


class AnthropicContentBlock(_BaseModel):
  """Union wrapper for the different block types we care about."""

  type: str
  text: Optional[str] = None
  citations: Optional[List[AnthropicCitation]] = None
  name: Optional[str] = None
  input: Optional[Dict[str, Any]] = None
  content: Optional[List[Dict[str, Any]]] = None


class AnthropicResponse(_BaseModel):
  """Top-level Anthropic Claude API response structure."""

  id: str
  content: List[AnthropicContentBlock]
  model: Optional[str] = None


# ---------------------------------------------------------------------------
# Google Gemini payloads
# ---------------------------------------------------------------------------

class GoogleGroundingWeb(_BaseModel):
  """Web source used for grounding in Google Gemini response."""

  uri: Optional[str] = None
  title: Optional[str] = None


class GoogleGroundingChunk(_BaseModel):
  """Individual grounding chunk from Google Gemini."""

  web: Optional[GoogleGroundingWeb] = None


class GoogleGroundingMetadata(_BaseModel):
  """Metadata about grounding sources and queries from Google Gemini."""

  web_search_queries: Optional[List[str]] = None
  grounding_chunks: Optional[List[GoogleGroundingChunk]] = None


class GoogleCandidate(_BaseModel):
  """Response candidate from Google Gemini with grounding metadata."""

  grounding_metadata: Optional[GoogleGroundingMetadata] = None


class GoogleResponse(_BaseModel):
  """Top-level Google Gemini API response structure."""

  text: Optional[str] = None
  candidates: Optional[List[GoogleCandidate]] = None


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _sanitize_json_types(value: Any) -> Any:
  """
  Recursively convert unsupported JSON types (bytes, sets, tuples) into safe values.
  """
  if isinstance(value, Mapping):
    return {key: _sanitize_json_types(val) for key, val in value.items()}
  if isinstance(value, (list, tuple, set)):
    return [_sanitize_json_types(item) for item in value]
  if isinstance(value, (bytes, bytearray, memoryview)):
    # Encode binary blobs so we retain data while keeping JSON-friendly output.
    return b64encode(bytes(value)).decode("ascii")
  return value


def _ensure_dict(payload: Any) -> Dict[str, Any]:
  """
  Convert arbitrary SDK objects into dictionaries suitable for validation.

  Args:
    payload: The provider SDK object or dict.

  Returns:
    Dict representation of the payload.

  Raises:
    TypeError: If the payload cannot be coerced into a dictionary.
  """
  if payload is None:
    return {}
  if isinstance(payload, dict):
    return _sanitize_json_types(payload)
  if hasattr(payload, "model_dump"):
    data = payload.model_dump()
    if isinstance(data, dict):
      return _sanitize_json_types(data)
  if hasattr(payload, "to_dict"):
    data = payload.to_dict()
    if isinstance(data, dict):
      return _sanitize_json_types(data)
  raise TypeError(f"Cannot convert payload of type {type(payload)} to dict")


def validate_openai_raw_response(payload: Any) -> Dict[str, Any]:
  """Validate and normalize OpenAI Responses API payloads."""
  data = _ensure_dict(payload)
  try:
    return OpenAIResponse.model_validate(data).model_dump(
      exclude_none=True,
      mode="json",
    )
  except Exception as exc:
    raise ValueError(f"Invalid OpenAI raw response: {exc}") from exc


def validate_anthropic_raw_response(payload: Any) -> Dict[str, Any]:
  """Validate and normalize Anthropic Claude payloads."""
  data = _ensure_dict(payload)
  try:
    return AnthropicResponse.model_validate(data).model_dump(
      exclude_none=True,
      mode="json",
    )
  except Exception as exc:
    raise ValueError(f"Invalid Anthropic raw response: {exc}") from exc


def validate_google_raw_response(payload: Any) -> Dict[str, Any]:
  """Validate and normalize Google Gemini payloads."""
  data = _ensure_dict(payload)
  try:
    return GoogleResponse.model_validate(data).model_dump(
      exclude_none=True,
      mode="json",
    )
  except Exception as exc:
    raise ValueError(f"Invalid Google raw response: {exc}") from exc


__all__ = [
  "validate_openai_raw_response",
  "validate_anthropic_raw_response",
  "validate_google_raw_response",
  "OpenAIResponse",
  "AnthropicResponse",
  "GoogleResponse",
]
