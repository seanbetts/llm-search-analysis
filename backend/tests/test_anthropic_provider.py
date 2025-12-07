"""Tests for Anthropic Claude provider implementation."""

import pytest
from copy import deepcopy
from unittest.mock import Mock, MagicMock, patch
from app.services.providers.anthropic_provider import AnthropicProvider
from tests.fixtures import provider_payloads as payloads


class TestAnthropicProvider:
  """Tests for AnthropicProvider."""

  @pytest.fixture
  def provider(self):
    """Create AnthropicProvider with test API key."""
    with patch('app.services.providers.anthropic_provider.Anthropic'):
      return AnthropicProvider("test-api-key")

  def test_initialization(self):
    """Test provider initialization."""
    with patch('app.services.providers.anthropic_provider.Anthropic') as mock_anthropic:
      provider = AnthropicProvider("test-key-123")

      assert provider.api_key == "test-key-123"
      mock_anthropic.assert_called_once_with(api_key="test-key-123")

  def test_get_provider_name(self, provider):
    """Test get_provider_name returns 'anthropic'."""
    assert provider.get_provider_name() == "anthropic"

  def test_get_supported_models(self, provider):
    """Test get_supported_models returns list of models."""
    models = provider.get_supported_models()

    assert isinstance(models, list)
    assert "claude-sonnet-4-5-20250929" in models
    assert "claude-haiku-4-5-20251001" in models
    assert "claude-opus-4-1-20250805" in models

  def test_validate_model_supported(self, provider):
    """Test validate_model returns True for supported models."""
    assert provider.validate_model("claude-sonnet-4-5-20250929") is True
    assert provider.validate_model("claude-haiku-4-5-20251001") is True
    assert provider.validate_model("claude-opus-4-1-20250805") is True

  def test_validate_model_unsupported(self, provider):
    """Test validate_model returns False for unsupported models."""
    assert provider.validate_model("claude-2") is False
    assert provider.validate_model("invalid-model") is False

  def test_send_prompt_unsupported_model(self, provider):
    """Test send_prompt raises ValueError for unsupported model."""
    with pytest.raises(ValueError) as exc_info:
      provider.send_prompt("Test prompt", "unsupported-model")

    assert "not supported" in str(exc_info.value).lower()
    assert "unsupported-model" in str(exc_info.value)

  def test_send_prompt_api_error(self, provider):
    """Test send_prompt handles API errors."""
    provider.client.messages.create = Mock(
      side_effect=Exception("API connection failed")
    )

    with pytest.raises(Exception) as exc_info:
      provider.send_prompt("Test prompt", "claude-sonnet-4-5-20250929")

    assert "Anthropic API error" in str(exc_info.value)
    assert "API connection failed" in str(exc_info.value)

  def test_send_prompt_success_with_web_search(self, provider):
    """Test send_prompt successfully parses response with web search results."""
    # Create mock response with web search blocks
    mock_response = Mock()

    # Mock server_tool_use block (search query)
    mock_query_block = Mock()
    mock_query_block.type = "server_tool_use"
    mock_query_block.name = "web_search"
    mock_query_block.input = {"query": "latest AI developments"}

    # Mock web_search_tool_result block (search results)
    # NOTE: Real Anthropic SDK returns dicts, not objects with attributes
    mock_result_block = Mock()
    mock_result_block.type = "web_search_tool_result"

    mock_result1 = {
      'type': 'web_search_result',
      'url': 'https://example.com/article1',
      'title': 'AI Article 1'
    }

    mock_result2 = {
      'type': 'web_search_result',
      'url': 'https://example.com/article2',
      'title': 'AI Article 2'
    }

    mock_result_block.content = [mock_result1, mock_result2]

    # Mock text block with citations
    # NOTE: Real Anthropic SDK returns citation dicts, not objects
    mock_text_block = Mock()
    mock_text_block.type = "text"
    mock_text_block.text = "AI has advanced significantly."

    mock_citation = {
      'url': 'https://example.com/article1',
      'title': 'AI Article 1'
    }
    mock_text_block.citations = [mock_citation]

    mock_response.content = [mock_query_block, mock_result_block, mock_text_block]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    # Send prompt
    result = provider.send_prompt("What's new in AI?", "claude-sonnet-4-5-20250929")

    # Verify response
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-5-20250929"
    assert result.response_text == "AI has advanced significantly."
    assert len(result.search_queries) == 1
    assert result.search_queries[0].query == "latest AI developments"
    assert len(result.search_queries[0].sources) == 2
    assert result.search_queries[0].sources[0].url == "https://example.com/article1"
    assert len(result.sources) == 2
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/article1"
    assert result.citations[0].rank == 1  # Should match source rank

  def test_send_prompt_no_web_search(self, provider):
    """Test send_prompt handles response without web search."""
    mock_response = Mock()

    # Mock text block only
    mock_text_block = Mock()
    mock_text_block.type = "text"
    mock_text_block.text = "Simple response without search."
    mock_text_block.citations = []

    mock_response.content = [mock_text_block]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Simple question", "claude-sonnet-4-5-20250929")

    assert result.response_text == "Simple response without search."
    assert len(result.search_queries) == 0
    assert len(result.sources) == 0
    assert len(result.citations) == 0

  def test_parse_response_multiple_text_blocks(self, provider):
    """Test _parse_response concatenates multiple text blocks."""
    mock_response = Mock()

    # Mock multiple text blocks
    mock_text1 = Mock()
    mock_text1.type = "text"
    mock_text1.text = "First part. "
    mock_text1.citations = []

    mock_text2 = Mock()
    mock_text2.type = "text"
    mock_text2.text = "Second part."
    mock_text2.citations = []

    mock_response.content = [mock_text1, mock_text2]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    assert result.response_text == "First part. Second part."

  def test_parse_response_deduplicates_citations(self, provider):
    """Test _parse_response removes duplicate citations."""
    mock_response = Mock()

    # Mock text block with duplicate citations (use dicts)
    mock_text_block = Mock()
    mock_text_block.type = "text"
    mock_text_block.text = "Test response"

    mock_citation1 = {
      'url': 'https://example.com/same',
      'title': 'Same Article'
    }

    mock_citation2 = {
      'url': 'https://example.com/same',  # Duplicate
      'title': 'Same Article'
    }

    mock_text_block.citations = [mock_citation1, mock_citation2]

    mock_response.content = [mock_text_block]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    # Should only have one citation despite two citations with same URL
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/same"

  def test_parse_response_links_queries_to_results(self, provider):
    """Test _parse_response correctly links queries to their search results."""
    mock_response = Mock()

    # First query
    mock_query1 = Mock()
    mock_query1.type = "server_tool_use"
    mock_query1.name = "web_search"
    mock_query1.input = {"query": "query 1"}

    # First result (use dict to match real API)
    mock_result1 = Mock()
    mock_result1.type = "web_search_tool_result"
    mock_result1_source = {
      'type': 'web_search_result',
      'url': 'https://example.com/result1',
      'title': 'Result 1'
    }
    mock_result1.content = [mock_result1_source]

    # Second query
    mock_query2 = Mock()
    mock_query2.type = "server_tool_use"
    mock_query2.name = "web_search"
    mock_query2.input = {"query": "query 2"}

    # Second result (use dict to match real API)
    mock_result2 = Mock()
    mock_result2.type = "web_search_tool_result"
    mock_result2_source = {
      'type': 'web_search_result',
      'url': 'https://example.com/result2',
      'title': 'Result 2'
    }
    mock_result2.content = [mock_result2_source]

    mock_response.content = [mock_query1, mock_result1, mock_query2, mock_result2]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    # Should have 2 queries, each with their own sources
    assert len(result.search_queries) == 2
    assert result.search_queries[0].query == "query 1"
    assert len(result.search_queries[0].sources) == 1
    assert result.search_queries[0].sources[0].url == "https://example.com/result1"
    assert result.search_queries[1].query == "query 2"
    assert len(result.search_queries[1].sources) == 1
    assert result.search_queries[1].sources[0].url == "https://example.com/result2"

  def test_parse_response_handles_missing_attributes(self, provider):
    """Test _parse_response gracefully handles missing attributes."""
    mock_response = Mock()

    # Mock incomplete search query (no input)
    mock_query_block = Mock()
    mock_query_block.type = "server_tool_use"
    mock_query_block.name = "web_search"
    mock_query_block.input = None

    mock_response.content = [mock_query_block]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    # Should not raise an error
    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    assert result.response_text == ""
    assert len(result.search_queries) == 0

  def test_parse_response_skips_results_without_url(self, provider):
    """Test _parse_response skips search results without valid URL."""
    mock_response = Mock()

    # Mock query
    mock_query = Mock()
    mock_query.type = "server_tool_use"
    mock_query.name = "web_search"
    mock_query.input = {"query": "test query"}

    # Mock result with one valid and one invalid source (use dicts)
    mock_result = Mock()
    mock_result.type = "web_search_tool_result"

    mock_result1 = {
      'type': 'web_search_result',
      'url': None,  # No URL
      'title': 'Invalid'
    }

    mock_result2 = {
      'type': 'web_search_result',
      'url': 'https://example.com/valid',
      'title': 'Valid'
    }

    mock_result.content = [mock_result1, mock_result2]

    mock_response.content = [mock_query, mock_result]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    # Should only have the valid source
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://example.com/valid"

  def test_parse_response_ignores_non_web_search_server_tool_use(self, provider):
    """Test _parse_response ignores server_tool_use blocks that aren't web_search."""
    mock_response = Mock()

    # Mock server_tool_use with different name
    mock_other_tool = Mock()
    mock_other_tool.type = "server_tool_use"
    mock_other_tool.name = "other_tool"
    mock_other_tool.input = {"query": "should be ignored"}

    mock_response.content = [mock_other_tool]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    # Should not create any search queries
    assert len(result.search_queries) == 0

  def test_parse_response_handles_input_as_dict(self, provider):
    """Test _parse_response handles input as dict (normal case)."""
    mock_response = Mock()

    # Mock query with dict input
    mock_query = Mock()
    mock_query.type = "server_tool_use"
    mock_query.name = "web_search"
    mock_query.input = {"query": "test query"}

    mock_response.content = [mock_query]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    assert len(result.search_queries) == 1
    assert result.search_queries[0].query == "test query"

  def test_parse_response_handles_input_as_non_dict(self, provider):
    """Test _parse_response handles input as non-dict gracefully."""
    mock_response = Mock()

    # Mock query with non-dict input
    mock_query = Mock()
    mock_query.type = "server_tool_use"
    mock_query.name = "web_search"
    mock_query.input = "not a dict"

    mock_response.content = [mock_query]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    # Should not raise an error
    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    assert len(result.search_queries) == 0

  def test_parse_response_citation_matches_source_rank(self, provider):
    """Test _parse_response sets citation rank from matching source."""
    mock_response = Mock()

    # Mock query and result to create sources
    mock_query = Mock()
    mock_query.type = "server_tool_use"
    mock_query.name = "web_search"
    mock_query.input = {"query": "test"}

    mock_result = Mock()
    mock_result.type = "web_search_tool_result"
    mock_source1 = {
      'type': 'web_search_result',
      'url': 'https://example.com/first',
      'title': 'First'
    }
    mock_source2 = {
      'type': 'web_search_result',
      'url': 'https://example.com/second',
      'title': 'Second'
    }
    mock_result.content = [mock_source1, mock_source2]

    # Mock text with citation to second source (use dict)
    mock_text = Mock()
    mock_text.type = "text"
    mock_text.text = "Test"
    mock_citation = {
      'url': 'https://example.com/second',
      'title': 'Second'
    }
    mock_text.citations = [mock_citation]

    mock_response.content = [mock_query, mock_result, mock_text]
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    # Citation should have rank 2 (matching the second source)
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/second"
    assert result.citations[0].rank == 2

  def test_send_prompt_includes_response_time(self, provider):
    """Test send_prompt calculates response time."""
    mock_response = Mock()
    mock_response.content = []
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_RESPONSE))

    provider.client.messages.create = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "claude-sonnet-4-5-20250929")

    assert result.response_time_ms is not None
    assert isinstance(result.response_time_ms, int)
    assert result.response_time_ms >= 0

  def test_raw_payload_validation_failure(self, provider):
    """Ensure malformed payloads raise ValueError during validation."""
    mock_response = Mock()
    # Missing required content list
    mock_response.model_dump = Mock(return_value=deepcopy(payloads.ANTHROPIC_INVALID))
    mock_response.content = []

    provider.client.messages.create = Mock(return_value=mock_response)

    with pytest.raises(ValueError) as exc_info:
      provider.send_prompt("Broken", "claude-sonnet-4-5-20250929")

    assert "raw payload" in str(exc_info.value)
