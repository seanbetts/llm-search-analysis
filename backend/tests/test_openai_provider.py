"""Tests for OpenAI provider implementation."""

import pytest
from copy import deepcopy
from unittest.mock import Mock, MagicMock, patch
from app.services.providers.openai_provider import OpenAIProvider
from tests.fixtures import provider_payloads as payloads


class TestOpenAIProvider:
  """Tests for OpenAIProvider."""

  @pytest.fixture
  def provider(self):
    """Create OpenAIProvider with test API key."""
    with patch('app.services.providers.openai_provider.OpenAI'):
      return OpenAIProvider("test-api-key")

  def test_initialization(self):
    """Test provider initialization."""
    with patch('app.services.providers.openai_provider.OpenAI') as mock_openai:
      provider = OpenAIProvider("test-key-123")

      assert provider.api_key == "test-key-123"
      mock_openai.assert_called_once_with(api_key="test-key-123")

  def test_get_provider_name(self, provider):
    """Test get_provider_name returns 'openai'."""
    assert provider.get_provider_name() == "openai"

  def test_get_supported_models(self, provider):
    """Test get_supported_models returns list of models."""
    models = provider.get_supported_models()

    assert isinstance(models, list)
    assert "gpt-5.1" in models
    assert "gpt-5-mini" in models
    assert "gpt-5-nano" in models

  def test_validate_model_supported(self, provider):
    """Test validate_model returns True for supported models."""
    assert provider.validate_model("gpt-5.1") is True
    assert provider.validate_model("gpt-5-mini") is True
    assert provider.validate_model("gpt-5-nano") is True

  def test_validate_model_unsupported(self, provider):
    """Test validate_model returns False for unsupported models."""
    assert provider.validate_model("gpt-4") is False
    assert provider.validate_model("invalid-model") is False

  def test_send_prompt_unsupported_model(self, provider):
    """Test send_prompt raises ValueError for unsupported model."""
    with pytest.raises(ValueError) as exc_info:
      provider.send_prompt("Test prompt", "unsupported-model")

    assert "not supported" in str(exc_info.value).lower()
    assert "unsupported-model" in str(exc_info.value)

  def test_send_prompt_api_error(self, provider):
    """Test send_prompt handles API errors."""
    provider.client.responses.create = Mock(side_effect=Exception("API connection failed"))

    with pytest.raises(Exception) as exc_info:
      provider.send_prompt("Test prompt", "gpt-5.1")

    assert "OpenAI API error" in str(exc_info.value)
    assert "API connection failed" in str(exc_info.value)

  def test_send_prompt_success_with_sources_and_citations(self, provider):
    """Test send_prompt successfully parses response with sources and citations."""
    # Create mock response with web_search_call and message
    mock_response = Mock()

    # Mock web_search_call output
    mock_search_call = Mock()
    mock_search_call.type = "web_search_call"
    mock_search_call.status = "completed"

    # Mock action with query and sources
    mock_action = Mock()
    mock_action.query = "latest AI developments"

    mock_source1 = Mock()
    mock_source1.url = "https://example.com/article1"
    mock_source1.title = "AI Article 1"

    mock_source2 = Mock()
    mock_source2.url = "https://example.com/article2"
    mock_source2.title = "AI Article 2"

    mock_action.sources = [mock_source1, mock_source2]
    mock_search_call.action = mock_action

    # Mock message output
    mock_message = Mock()
    mock_message.type = "message"
    mock_message.status = "completed"

    # Mock content with text and citations
    mock_content = Mock()
    mock_content.type = "output_text"
    mock_content.text = "AI has advanced significantly."

    # Mock citation annotation
    mock_annotation = Mock()
    mock_annotation.type = "url_citation"
    mock_annotation.url = "https://example.com/article1"
    mock_annotation.title = "AI Article 1"

    mock_content.annotations = [mock_annotation]
    mock_message.content = [mock_content]

    mock_response.output = [mock_search_call, mock_message]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.OPENAI_RESPONSE))

    provider.client.responses.create = Mock(return_value=mock_response)

    # Send prompt
    result = provider.send_prompt("What's new in AI?", "gpt-5.1")

    # Verify response
    assert result.provider == "openai"
    assert result.model == "gpt-5.1"
    assert result.response_text == "AI has advanced significantly."
    assert len(result.search_queries) == 1
    assert result.search_queries[0].query == "latest AI developments"
    assert len(result.search_queries[0].sources) == 2
    assert result.search_queries[0].sources[0].url == "https://example.com/article1"
    assert len(result.sources) == 2
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/article1"
    assert result.citations[0].rank == 1  # Should match source rank

  def test_send_prompt_no_sources(self, provider):
    """Test send_prompt handles response without sources."""
    mock_response = Mock()

    # Mock message without web_search_call
    mock_message = Mock()
    mock_message.type = "message"
    mock_message.status = "completed"

    mock_content = Mock()
    mock_content.type = "output_text"
    mock_content.text = "Simple response without search."
    mock_content.annotations = []

    mock_message.content = [mock_content]
    mock_response.output = [mock_message]
    payload = deepcopy(payloads.OPENAI_RESPONSE)
    payload["output"] = []
    mock_response.model_dump = Mock(return_value=payload)

    provider.client.responses.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Simple question", "gpt-5.1")

    assert result.response_text == "Simple response without search."
    assert len(result.search_queries) == 0
    assert len(result.sources) == 0
    assert len(result.citations) == 0

  def test_parse_response_deduplicates_citations(self, provider):
    """Test _parse_response removes duplicate citations."""
    mock_response = Mock()

    mock_message = Mock()
    mock_message.type = "message"
    mock_message.status = "completed"

    # Create content with duplicate citations
    mock_content = Mock()
    mock_content.type = "output_text"
    mock_content.text = "Test response"

    mock_annotation1 = Mock()
    mock_annotation1.type = "url_citation"
    mock_annotation1.url = "https://example.com/same"
    mock_annotation1.title = "Same Article"

    mock_annotation2 = Mock()
    mock_annotation2.type = "url_citation"
    mock_annotation2.url = "https://example.com/same"  # Duplicate
    mock_annotation2.title = "Same Article"

    mock_content.annotations = [mock_annotation1, mock_annotation2]
    mock_message.content = [mock_content]
    mock_response.output = [mock_message]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.OPENAI_RESPONSE))

    provider.client.responses.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gpt-5.1")

    # Should only have one citation despite two annotations with same URL
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/same"

  def test_parse_response_handles_missing_attributes(self, provider):
    """Test _parse_response gracefully handles missing attributes."""
    mock_response = Mock()

    # Mock incomplete search call (missing action)
    mock_search_call = Mock()
    mock_search_call.type = "web_search_call"
    mock_search_call.status = "completed"
    # No action attribute
    mock_search_call.action = None

    mock_response.output = [mock_search_call]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.OPENAI_RESPONSE))

    provider.client.responses.create = Mock(return_value=mock_response)

    # Should not raise an error
    result = provider.send_prompt("Test", "gpt-5.1")

    assert result.response_text == ""
    assert len(result.search_queries) == 0

  def test_raw_payload_validation_failure(self, provider):
    """Ensure invalid raw payloads raise a ValueError."""
    mock_response = Mock()
    mock_response.output = []
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.OPENAI_INVALID))

    provider.client.responses.create = Mock(return_value=mock_response)

    with pytest.raises(ValueError) as exc_info:
      provider.send_prompt("Bad payload", "gpt-5.1")

    assert "raw payload" in str(exc_info.value)

  def test_send_prompt_includes_response_time(self, provider):
    """Test send_prompt calculates response time."""
    mock_response = Mock()
    mock_response.output = []
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.OPENAI_RESPONSE))

    provider.client.responses.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gpt-5.1")

    assert result.response_time_ms is not None
    assert isinstance(result.response_time_ms, int)
    assert result.response_time_ms >= 0
