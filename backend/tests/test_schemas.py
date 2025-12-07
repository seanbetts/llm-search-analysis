"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.api.v1.schemas.requests import SendPromptRequest, BatchRequest
from app.api.v1.schemas.responses import (
  Source,
  SearchQuery,
  Citation,
  SendPromptResponse,
  InteractionSummary,
  BatchStatus,
  ProviderInfo,
  HealthResponse,
  ErrorResponse,
)


class TestSendPromptRequest:
  """Tests for SendPromptRequest schema."""

  def test_valid_request(self):
    """Test valid SendPromptRequest."""
    request = SendPromptRequest(
      prompt="What is AI?",
      provider="openai",
      model="gpt-5.1",
      data_mode="api",
      headless=True
    )
    assert request.prompt == "What is AI?"
    assert request.provider == "openai"
    assert request.model == "gpt-5.1"

  def test_prompt_too_short(self):
    """Test prompt validation - too short."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="",
        provider="openai",
        model="gpt-5.1"
      )
    assert "prompt" in str(exc_info.value).lower()

  def test_prompt_whitespace_only(self):
    """Test prompt validation - whitespace only."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="   ",
        provider="openai",
        model="gpt-5.1"
      )
    assert "empty or whitespace" in str(exc_info.value).lower()

  def test_prompt_too_long(self):
    """Test prompt validation - exceeds max length."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="a" * 10001,
        provider="openai",
        model="gpt-5.1"
      )
    assert "10000" in str(exc_info.value)

  def test_prompt_xss_script_tag(self):
    """Test XSS prevention - script tags."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="<script>alert('xss')</script>What is AI?",
        provider="openai",
        model="gpt-5.1"
      )
    assert "script" in str(exc_info.value).lower()

  def test_prompt_xss_iframe_tag(self):
    """Test XSS prevention - iframe tags."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="<iframe src='evil.com'>What is AI?</iframe>",
        provider="openai",
        model="gpt-5.1"
      )
    assert "iframe" in str(exc_info.value).lower()

  def test_invalid_provider(self):
    """Test provider validation - invalid provider."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="What is AI?",
        provider="invalid_provider",
        model="gpt-5.1"
      )
    assert "invalid provider" in str(exc_info.value).lower()

  def test_invalid_data_mode(self):
    """Test data_mode validation."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        prompt="What is AI?",
        provider="openai",
        model="gpt-5.1",
        data_mode="invalid_mode"
      )
    assert "invalid data_mode" in str(exc_info.value).lower()

  def test_provider_case_insensitive(self):
    """Test provider validation is case-insensitive."""
    request = SendPromptRequest(
      prompt="What is AI?",
      provider="OpenAI",
      model="gpt-5.1"
    )
    assert request.provider == "openai"


class TestBatchRequest:
  """Tests for BatchRequest schema."""

  def test_valid_batch_request(self):
    """Test valid BatchRequest."""
    request = BatchRequest(
      prompts=["What is AI?", "What is ML?"],
      provider="openai",
      models=["gpt-5.1", "gpt-5.1-mini"]
    )
    assert len(request.prompts) == 2
    assert len(request.models) == 2

  def test_empty_prompts_list(self):
    """Test validation - empty prompts list."""
    with pytest.raises(ValidationError) as exc_info:
      BatchRequest(
        prompts=[],
        provider="openai",
        models=["gpt-5.1"]
      )
    assert "prompts" in str(exc_info.value).lower()

  def test_empty_models_list(self):
    """Test validation - empty models list."""
    with pytest.raises(ValidationError) as exc_info:
      BatchRequest(
        prompts=["What is AI?"],
        provider="openai",
        models=[]
      )
    assert "models" in str(exc_info.value).lower()

  def test_whitespace_prompt_in_list(self):
    """Test validation - whitespace prompt in list."""
    with pytest.raises(ValidationError) as exc_info:
      BatchRequest(
        prompts=["What is AI?", "   "],
        provider="openai",
        models=["gpt-5.1"]
      )
    assert "index 1" in str(exc_info.value).lower()

  def test_too_many_prompts(self):
    """Test validation - exceeds max prompts."""
    with pytest.raises(ValidationError) as exc_info:
      BatchRequest(
        prompts=["prompt"] * 101,
        provider="openai",
        models=["gpt-5.1"]
      )
    assert "100" in str(exc_info.value)


class TestResponseSchemas:
  """Tests for response schemas."""

  def test_source_schema(self):
    """Test Source schema."""
    source = Source(
      url="https://example.com",
      title="Example Title",
      domain="example.com",
      rank=1
    )
    assert source.url == "https://example.com"
    assert source.rank == 1

  def test_source_rank_validation(self):
    """Test Source rank must be >= 1."""
    with pytest.raises(ValidationError):
      Source(url="https://example.com", rank=0)

  def test_search_query_schema(self):
    """Test SearchQuery schema."""
    query = SearchQuery(
      query="AI developments",
      sources=[],
      order_index=0
    )
    assert query.query == "AI developments"
    assert len(query.sources) == 0

  def test_citation_schema(self):
    """Test Citation schema."""
    citation = Citation(
      url="https://example.com",
      title="Example",
      rank=1
    )
    assert citation.url == "https://example.com"

  def test_citation_confidence_validation(self):
    """Test Citation confidence score validation."""
    # Valid confidence
    citation = Citation(
      url="https://example.com",
      citation_confidence=0.95
    )
    assert citation.citation_confidence == 0.95

    # Invalid confidence > 1.0
    with pytest.raises(ValidationError):
      Citation(url="https://example.com", citation_confidence=1.5)

    # Invalid confidence < 0.0
    with pytest.raises(ValidationError):
      Citation(url="https://example.com", citation_confidence=-0.1)

  def test_send_prompt_response_schema(self):
    """Test SendPromptResponse schema."""
    response = SendPromptResponse(
      prompt="What is AI?",
      response_text="AI is...",
      provider="openai",
      model="gpt-5.1",
      response_time_ms=1500,
      data_source="api"
    )
    assert response.prompt == "What is AI?"
    assert response.response_text == "AI is..."
    assert response.response_time_ms == 1500

  def test_interaction_summary_schema(self):
    """Test InteractionSummary schema."""
    from datetime import datetime
    summary = InteractionSummary(
      interaction_id=1,
      prompt="What is AI?",
      provider="openai",
      model="gpt-5.1",
      response_preview="AI is...",
      created_at=datetime.utcnow()
    )
    assert summary.interaction_id == 1
    assert summary.search_query_count == 0

  def test_batch_status_schema(self):
    """Test BatchStatus schema."""
    status = BatchStatus(
      batch_id="batch_123",
      total_tasks=10,
      completed_tasks=7,
      status="processing"
    )
    assert status.batch_id == "batch_123"
    assert status.total_tasks == 10

  def test_provider_info_schema(self):
    """Test ProviderInfo schema."""
    info = ProviderInfo(
      name="openai",
      display_name="OpenAI",
      is_active=True,
      supported_models=["gpt-5.1", "gpt-5.1-mini"]
    )
    assert info.name == "openai"
    assert len(info.supported_models) == 2

  def test_health_response_schema(self):
    """Test HealthResponse schema."""
    health = HealthResponse(
      status="healthy",
      version="1.0.0",
      database="connected"
    )
    assert health.status == "healthy"

  def test_error_response_schema(self):
    """Test ErrorResponse schema."""
    error = ErrorResponse(
      message="Invalid request",
      detail="Prompt cannot be empty",
      code="VALIDATION_ERROR"
    )
    assert error.status == "error"
    assert error.message == "Invalid request"


class TestSchemaExamples:
  """Test that schema examples are valid."""

  def test_send_prompt_request_example(self):
    """Test SendPromptRequest example is valid."""
    example = SendPromptRequest.model_config["json_schema_extra"]["examples"][0]
    request = SendPromptRequest(**example)
    assert request.prompt is not None

  def test_batch_request_example(self):
    """Test BatchRequest example is valid."""
    example = BatchRequest.model_config["json_schema_extra"]["examples"][0]
    request = BatchRequest(**example)
    assert len(request.prompts) > 0

  def test_source_example(self):
    """Test Source example is valid."""
    example = Source.model_config["json_schema_extra"]["examples"][0]
    source = Source(**example)
    assert source.url is not None

  def test_send_prompt_response_example(self):
    """Test SendPromptResponse example is valid."""
    example = SendPromptResponse.model_config["json_schema_extra"]["examples"][0]
    response = SendPromptResponse(**example)
    assert response.response_text is not None
