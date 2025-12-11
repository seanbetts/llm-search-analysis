"""Tests for Google Gemini provider implementation."""

from unittest.mock import Mock, patch

import pytest

from app.services.providers.google_provider import GoogleProvider


class TestGoogleProvider:
  """Tests for GoogleProvider."""

  @pytest.fixture
  def provider(self):
    """Create GoogleProvider with test API key."""
    with patch('app.services.providers.google_provider.Client'):
      return GoogleProvider("test-api-key")

  def test_initialization(self):
    """Test provider initialization."""
    with patch('app.services.providers.google_provider.Client') as mock_client:
      provider = GoogleProvider("test-key-123")

      assert provider.api_key == "test-key-123"
      mock_client.assert_called_once_with(api_key="test-key-123")

  def test_get_provider_name(self, provider):
    """Test get_provider_name returns 'google'."""
    assert provider.get_provider_name() == "google"

  def test_get_supported_models(self, provider):
    """Test get_supported_models returns list of models."""
    models = provider.get_supported_models()

    assert isinstance(models, list)
    assert "gemini-3-pro-preview" in models
    assert "gemini-2.5-flash" in models
    assert "gemini-2.5-flash-lite" in models

  def test_validate_model_supported(self, provider):
    """Test validate_model returns True for supported models."""
    assert provider.validate_model("gemini-3-pro-preview") is True
    assert provider.validate_model("gemini-2.5-flash") is True
    assert provider.validate_model("gemini-2.5-flash-lite") is True

  def test_validate_model_unsupported(self, provider):
    """Test validate_model returns False for unsupported models."""
    assert provider.validate_model("gemini-1.0") is False
    assert provider.validate_model("invalid-model") is False

  def test_send_prompt_unsupported_model(self, provider):
    """Test send_prompt raises ValueError for unsupported model."""
    with pytest.raises(ValueError) as exc_info:
      provider.send_prompt("Test prompt", "unsupported-model")

    assert "not supported" in str(exc_info.value).lower()
    assert "unsupported-model" in str(exc_info.value)

  def test_send_prompt_api_error(self, provider):
    """Test send_prompt handles API errors."""
    provider.client.models.generate_content = Mock(
      side_effect=Exception("API connection failed")
    )

    with pytest.raises(Exception) as exc_info:
      provider.send_prompt("Test prompt", "gemini-2.5-flash")

    assert "Google API error" in str(exc_info.value)
    assert "API connection failed" in str(exc_info.value)

  def test_send_prompt_success_with_grounding(self, provider):
    """Test send_prompt successfully parses response with grounding metadata."""
    # Create mock response with grounding metadata
    mock_response = Mock()
    snippet_value = "The latest cited sentence."
    mock_response.text = f"{snippet_value} Additional context for testing."

    # Mock candidate with grounding metadata
    mock_candidate = Mock()
    mock_metadata = Mock()
    mock_metadata.web_search_queries = ["latest AI developments", "AI breakthroughs"]

    # Mock grounding chunks (sources)
    mock_chunk1 = Mock()
    mock_web1 = Mock()
    mock_web1.uri = "https://example.com/article1"
    mock_web1.title = "AI Article 1"
    mock_chunk1.web = mock_web1

    mock_chunk2 = Mock()
    mock_web2 = Mock()
    mock_web2.uri = "https://example.com/article2"
    mock_web2.title = "AI Article 2"
    mock_chunk2.web = mock_web2

    mock_support = Mock()
    mock_support.grounding_chunk_indices = [0]
    mock_segment = Mock()
    mock_segment.text = snippet_value
    mock_segment.start_index = 0
    mock_segment.end_index = len(snippet_value)
    mock_support.segment = mock_segment

    mock_metadata.grounding_chunks = [mock_chunk1, mock_chunk2]
    mock_metadata.grounding_supports = [mock_support]
    mock_candidate.grounding_metadata = mock_metadata

    mock_response.candidates = [mock_candidate]
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": [{
        "grounding_metadata": {
          "web_search_queries": ["latest AI developments", "AI breakthroughs"],
          "grounding_chunks": [
            {"web": {"uri": "https://example.com/article1", "title": "AI Article 1"}},
            {"web": {"uri": "https://example.com/article2", "title": "AI Article 2"}}
          ]
        }
      }]
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    # Send prompt
    result = provider.send_prompt("What's new in AI?", "gemini-2.5-flash")

    # Verify response
    assert result.provider == "google"
    assert result.model == "gemini-2.5-flash"
    assert result.response_text == f"{snippet_value} Additional context for testing."
    assert len(result.search_queries) == 2
    assert result.search_queries[0].query == "latest AI developments"
    assert result.search_queries[1].query == "AI breakthroughs"
    assert len(result.sources) == 2
    assert result.sources[0].url == "https://example.com/article1"
    assert result.sources[0].title == "AI Article 1"
    assert result.sources[1].url == "https://example.com/article2"
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://example.com/article1"
    assert result.citations[0].text_snippet == "The latest cited sentence."
    assert result.citations[0].start_index == 0
    assert result.citations[0].end_index == len(snippet_value)
    assert result.citations[0].metadata["segment_start_index"] == 0
    assert result.citations[0].metadata["segment_end_index"] == len(snippet_value)

  def test_send_prompt_no_grounding(self, provider):
    """Test send_prompt handles response without grounding metadata."""
    mock_response = Mock()
    mock_response.text = "Simple response without search."
    mock_response.candidates = []
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": []
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    result = provider.send_prompt("Simple question", "gemini-2.5-flash")

    assert result.response_text == "Simple response without search."
    assert len(result.search_queries) == 0
    assert len(result.sources) == 0
    assert len(result.citations) == 0

  def test_parse_response_with_sources_no_queries(self, provider):
    """Test _parse_response creates generic query when sources exist without queries."""
    mock_response = Mock()
    mock_response.text = "Test response"

    # Mock candidate with sources but no queries
    mock_candidate = Mock()
    mock_metadata = Mock()
    mock_metadata.web_search_queries = []

    # Mock grounding chunks
    mock_chunk = Mock()
    mock_web = Mock()
    mock_web.uri = "https://example.com/source"
    mock_web.title = "Source Title"
    mock_chunk.web = mock_web
    mock_metadata.grounding_chunks = [mock_chunk]

    mock_candidate.grounding_metadata = mock_metadata
    mock_response.candidates = [mock_candidate]
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": [{
        "grounding_metadata": {
          "web_search_queries": [],
          "grounding_chunks": [
            {"web": {"uri": "https://example.com/source", "title": "Source Title"}}
          ]
        }
      }]
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gemini-2.5-flash")

    # Should create a generic "Search" query
    assert len(result.search_queries) == 1
    assert result.search_queries[0].query == "Search"
    assert len(result.search_queries[0].sources) == 1
    assert result.search_queries[0].sources[0].url == "https://example.com/source"

  def test_resolve_redirect_url_non_google(self, provider):
    """Test _resolve_redirect_url returns original URL for non-Google URLs."""
    url = "https://example.com/article"
    result = provider._resolve_redirect_url(url)
    assert result == url

  @patch('app.services.providers.google_provider.requests.head')
  def test_resolve_redirect_url_google_success(self, mock_head, provider):
    """Test _resolve_redirect_url follows Google redirect URLs."""
    redirect_url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/xxx"
    actual_url = "https://example.com/actual-article"

    mock_response = Mock()
    mock_response.url = actual_url
    mock_head.return_value = mock_response

    result = provider._resolve_redirect_url(redirect_url)

    assert result == actual_url
    mock_head.assert_called_once_with(redirect_url, allow_redirects=True, timeout=3)

  @patch('app.services.providers.google_provider.requests.head')
  def test_resolve_redirect_url_google_failure(self, mock_head, provider):
    """Test _resolve_redirect_url returns original URL on failure."""
    redirect_url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/xxx"
    mock_head.side_effect = Exception("Timeout")

    result = provider._resolve_redirect_url(redirect_url)

    # Should return original URL on failure
    assert result == redirect_url

  def test_parse_response_handles_missing_attributes(self, provider):
    """Test _parse_response gracefully handles missing attributes."""
    mock_response = Mock()
    mock_response.text = "Response text"

    # Mock candidate with incomplete grounding metadata
    mock_candidate = Mock()
    mock_metadata = Mock()
    # No web_search_queries attribute
    mock_metadata.web_search_queries = None
    # No grounding_chunks attribute
    mock_metadata.grounding_chunks = None
    mock_candidate.grounding_metadata = mock_metadata

    mock_response.candidates = [mock_candidate]
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": [{
        "grounding_metadata": {}
      }]
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    # Should not raise an error
    result = provider.send_prompt("Test", "gemini-2.5-flash")

    assert result.response_text == "Response text"
    assert len(result.search_queries) == 0
    assert len(result.sources) == 0

  def test_parse_response_skips_chunks_without_uri(self, provider):
    """Test _parse_response skips grounding chunks without valid URI."""
    mock_response = Mock()
    mock_response.text = "Test response"

    mock_candidate = Mock()
    mock_metadata = Mock()
    mock_metadata.web_search_queries = ["test query"]

    # Mock chunk without URI
    mock_chunk1 = Mock()
    mock_web1 = Mock()
    mock_web1.uri = None  # No URI
    mock_chunk1.web = mock_web1

    # Mock chunk with URI
    mock_chunk2 = Mock()
    mock_web2 = Mock()
    mock_web2.uri = "https://example.com/valid"
    mock_web2.title = "Valid Source"
    mock_chunk2.web = mock_web2

    mock_metadata.grounding_chunks = [mock_chunk1, mock_chunk2]
    mock_candidate.grounding_metadata = mock_metadata

    mock_response.candidates = [mock_candidate]
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": [{
        "grounding_metadata": {
          "web_search_queries": ["test query"],
          "grounding_chunks": [
            {"web": {"uri": None}},
            {"web": {"uri": "https://example.com/valid", "title": "Valid Source"}}
          ]
        }
      }]
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gemini-2.5-flash")

    # Should only have the chunk with a valid URI
    assert len(result.sources) == 1
    assert result.sources[0].url == "https://example.com/valid"

  def test_parse_response_distributes_sources_across_queries(self, provider):
    """Test _parse_response distributes sources evenly across queries."""
    mock_response = Mock()
    mock_response.text = "Test response"

    mock_candidate = Mock()
    mock_metadata = Mock()
    # 2 queries
    mock_metadata.web_search_queries = ["query 1", "query 2"]

    # 5 sources (should distribute 3 to first query, 2 to second)
    chunks = []
    for i in range(5):
      chunk = Mock()
      web = Mock()
      web.uri = f"https://example.com/source{i}"
      web.title = f"Source {i}"
      chunk.web = web
      chunks.append(chunk)

    mock_metadata.grounding_chunks = chunks
    mock_candidate.grounding_metadata = mock_metadata

    mock_response.candidates = [mock_candidate]
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": [{
        "grounding_metadata": {
          "web_search_queries": ["query 1", "query 2"],
          "grounding_chunks": [
            {"web": {"uri": f"https://example.com/source{i}", "title": f"Source {i}"}}
            for i in range(5)
          ]
        }
      }]
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gemini-2.5-flash")

    # Should have 2 queries
    assert len(result.search_queries) == 2
    # First query should have 3 sources (5 // 2 + 1)
    assert len(result.search_queries[0].sources) == 3
    # Second query should have 2 sources (5 // 2)
    assert len(result.search_queries[1].sources) == 2

  def test_parse_response_creates_citations_from_supports(self, provider):
    """Grounding supports should be converted into citations."""
    mock_response = Mock()
    snippet_value = "Snippet referencing the source."
    prefix = "Prefix "
    mock_response.text = f"{prefix}{snippet_value} Suffix"

    mock_candidate = Mock()
    mock_metadata = Mock()
    mock_metadata.web_search_queries = ["query"]

    chunk = Mock()
    web = Mock()
    web.uri = "https://example.com/source"
    web.title = "Source Title"
    chunk.web = web
    mock_metadata.grounding_chunks = [chunk]

    support = Mock()
    support.grounding_chunk_indices = [0]
    segment = Mock()
    segment.text = snippet_value
    segment.start_index = len(prefix)
    segment.end_index = len(prefix) + len(snippet_value)
    support.segment = segment
    mock_metadata.grounding_supports = [support]

    mock_candidate.grounding_metadata = mock_metadata
    mock_response.candidates = [mock_candidate]
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": [{
        "grounding_metadata": {
          "web_search_queries": ["query"],
          "grounding_chunks": [
            {"web": {"uri": "https://example.com/source", "title": "Source Title"}}
          ],
          "grounding_supports": [{
            "grounding_chunk_indices": [0],
            "segment": {"text": "Snippet referencing the source."}
          }]
        }
      }]
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gemini-2.5-flash")

    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.url == "https://example.com/source"
    assert citation.text_snippet == "Snippet referencing the source."
    assert citation.start_index == len(prefix)
    assert citation.end_index == len(prefix) + len(snippet_value)
    assert citation.metadata["segment_start_index"] == len(prefix)
    assert citation.metadata["segment_end_index"] == len(prefix) + len(snippet_value)

  def test_extract_span_clamps_before_next_heading(self):
    """Double newlines should prevent spans from absorbing the next heading."""
    text = "Bullet detail ends here.\n\n## Next Section"
    start, end, snippet = GoogleProvider._extract_segment_span(
      text=text,
      segment_text=None,
      start_index=0,
      end_index=len(text)
    )
    assert snippet == "Bullet detail ends here."
    assert text[start:end] == "Bullet detail ends here."

  def test_extract_span_skips_heading_lines(self):
    """Spans starting inside a heading should begin at the next line of text."""
    text = "### **Heading Title**\nParagraph content follows."
    start, end, snippet = GoogleProvider._extract_segment_span(
      text=text,
      segment_text=None,
      start_index=0,
      end_index=len(text)
    )
    assert snippet == "Paragraph content follows."
    assert text[start:end] == "Paragraph content follows."

  def test_send_prompt_includes_response_time(self, provider):
    """Test send_prompt calculates response time."""
    mock_response = Mock()
    mock_response.text = "Test response"
    mock_response.candidates = []
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": []
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    result = provider.send_prompt("Test", "gemini-2.5-flash")

    assert result.response_time_ms is not None
    assert isinstance(result.response_time_ms, int)
    assert result.response_time_ms >= 0

  def test_raw_payload_validation_failure(self, provider):
    """Ensure invalid raw payloads trigger ValueError."""
    mock_response = Mock()
    mock_response.text = "Test response"
    mock_response.candidates = []
    mock_response.to_dict = Mock(return_value={
      "text": mock_response.text,
      "candidates": "oops"
    })

    provider.client.models.generate_content = Mock(return_value=mock_response)

    with pytest.raises(ValueError) as exc_info:
      provider.send_prompt("Test", "gemini-2.5-flash")

    assert "raw payload" in str(exc_info.value)
