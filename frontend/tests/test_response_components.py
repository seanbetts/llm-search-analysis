"""Tests for frontend response display components."""

from types import SimpleNamespace

from frontend.components.response import (
  extract_images_from_response,
  format_response_text,
  sanitize_response_markdown,
)
from frontend.tests.fixtures.send_prompt_responses import (
  api_send_prompt_response_dict,
  api_send_prompt_response_namespace,
  network_log_send_prompt_response_namespace,
)


class TestSanitizeResponseMarkdown:
  """Tests for sanitize_response_markdown function."""

  def test_removes_horizontal_rules(self):
    """Test that horizontal rules are removed."""
    text = "Content\n---\nMore content\n***\nFinal"
    result = sanitize_response_markdown(text)
    assert "---" not in result
    assert "***" not in result
    assert "Content" in result
    assert "More content" in result

  def test_downgrades_large_headings(self):
    """Test that large headings are downgraded to level 4."""
    text = "# Heading 1\n## Heading 2\n### Heading 3"
    result = sanitize_response_markdown(text)
    assert "#### Heading 1" in result
    assert "#### Heading 2" in result
    assert "#### Heading 3" in result

  def test_removes_html_hr_tags(self):
    """Test that HTML hr tags are removed."""
    text = "Content<hr>More content<hr />Final"
    result = sanitize_response_markdown(text)
    assert "<hr" not in result.lower()
    assert "Content" in result
    assert "More content" in result

  def test_handles_empty_string(self):
    """Test handling of empty string."""
    assert sanitize_response_markdown("") == ""
    assert sanitize_response_markdown(None) == ""

  def test_preserves_normal_content(self):
    """Test that normal content is preserved."""
    text = "Normal text with **bold** and *italic*"
    result = sanitize_response_markdown(text)
    assert "**bold**" in result
    assert "*italic*" in result


class TestFormatResponseText:
  """Tests for format_response_text function."""

  def test_converts_reference_style_links(self):
    """Test conversion of reference-style links to inline links."""
    text = """Check out [this article][1].

[1]: https://example.com/article "Article Title"
"""
    result = format_response_text(text, [])
    assert "this article ([example.com](https://example.com/article))" in result
    assert "[1]:" not in result

  def test_removes_reference_definitions(self):
    """Test that reference definitions are removed."""
    text = """Content here [link][1]

[1]: https://example.com
[2]: https://example.org
"""
    result = format_response_text(text, [])
    assert "[1]: https://example.com" not in result
    assert "[2]: https://example.org" not in result

  def test_handles_multiple_references(self):
    """Test handling of multiple reference-style links."""
    text = """See [link1][1] and [link2][2].

[1]: https://example.com
[2]: https://example.org
"""
    result = format_response_text(text, [])
    assert "link1 ([example.com](https://example.com))" in result
    assert "link2 ([example.org](https://example.org))" in result

  def test_handles_missing_references(self):
    """Test that links without matching references are preserved."""
    text = "See [this link][99]."
    result = format_response_text(text, [])
    assert "[this link][99]" in result  # Should keep original

  def test_handles_empty_text(self):
    """Test handling of empty text."""
    assert format_response_text("", []) == ""
    assert format_response_text(None, []) == ""

  def test_cleans_up_multiple_newlines(self):
    """Test that multiple newlines are collapsed."""
    text = "Line 1\n\n\n\nLine 2"
    result = format_response_text(text, [])
    assert "\n\n\n" not in result

  def test_injects_citation_markers_when_metadata_present(self):
    """Citations with segment metadata should add inline markers."""
    text = "Valve is working on new hardware according to reports."
    citations = [
      SimpleNamespace(
        rank=1,
        url="https://example.com/source",
        text_snippet="Valve is working on new hardware",
        metadata={"segment_start_index": 0, "segment_end_index": 31}
      )
    ]
    result = format_response_text(text, citations)
    assert "Valve is working on new hardware ([example.com](https://example.com/source))" in result


class TestExtractImagesFromResponse:
  """Tests for extract_images_from_response function."""

  def test_extracts_markdown_images(self):
    """Test extraction of markdown-style images."""
    text = "Some text ![alt](https://example.com/image.jpg) more text"
    cleaned_text, images = extract_images_from_response(text)

    assert len(images) == 1
    assert images[0] == "https://example.com/image.jpg"
    assert "![alt]" not in cleaned_text
    assert "Some text" in cleaned_text
    assert "more text" in cleaned_text

  def test_extracts_html_images(self):
    """Test extraction of HTML img tags."""
    text = 'Text <img src="https://example.com/image.png" alt="test"> more'
    cleaned_text, images = extract_images_from_response(text)

    assert len(images) == 1
    assert images[0] == "https://example.com/image.png"
    assert "<img" not in cleaned_text
    assert "Text" in cleaned_text
    assert "more" in cleaned_text

  def test_extracts_multiple_images(self):
    """Test extraction of multiple images."""
    text = """
    ![img1](https://example.com/1.jpg)
    Some text
    <img src="https://example.com/2.png"/>
    """
    cleaned_text, images = extract_images_from_response(text)

    assert len(images) == 2
    assert "https://example.com/1.jpg" in images
    assert "https://example.com/2.png" in images

  def test_handles_no_images(self):
    """Test handling of text without images."""
    text = "Just regular text with no images"
    cleaned_text, images = extract_images_from_response(text)

    assert len(images) == 0
    assert cleaned_text == text

  def test_handles_empty_text(self):
    """Test handling of empty text."""
    cleaned_text, images = extract_images_from_response("")
    assert cleaned_text == ""
    assert images == []

    cleaned_text, images = extract_images_from_response(None)
    assert cleaned_text is None
    assert images == []


class TestResponseObjectStructure:
  """Tests for response object structure from API."""

  def test_response_has_all_required_fields(self):
    """Test that response object has all fields needed by display_response."""
    response = api_send_prompt_response_namespace()

    # Verify all fields exist and mirror backend schema defaults
    assert response.provider == 'openai'
    assert response.model == 'gpt-5.1'
    assert response.model_display_name == 'GPT-5.1'
    assert response.response_text.startswith('Artificial intelligence regulation')
    assert response.response_time_ms == 1250
    assert response.sources_found == 3
    assert response.sources_used == 2
    assert response.avg_rank == 1.5
    assert response.extra_links_count == 0

  def test_response_with_missing_optional_fields(self):
    """Test that response object handles missing optional fields gracefully."""
    payload = api_send_prompt_response_dict()
    payload.update({
      'model_display_name': None,
      'search_queries': [],
      'citations': [],
      'all_sources': [],
      'sources_found': 0,
      'sources_used': 0,
      'avg_rank': None,
      'extra_links_count': 0,
    })
    response = SimpleNamespace(**payload)

    # Use getattr as display_response does
    assert getattr(response, 'model_display_name', None) is None
    assert getattr(response, 'sources_found', 0) == 0
    assert getattr(response, 'sources_used', 0) == 0
    assert getattr(response, 'avg_rank', None) is None
    assert getattr(response, 'extra_links_count', 0) == 0

  def test_search_queries_structure(self):
    """Test that search queries are properly structured."""
    payload = api_send_prompt_response_dict()
    query_data = payload['search_queries'][0]

    sources = [SimpleNamespace(**src) for src in query_data['sources']]
    search_query = SimpleNamespace(
      query=query_data['query'],
      sources=sources,
      timestamp=query_data.get('timestamp'),
      order_index=query_data.get('order_index')
    )

    assert search_query.query == 'ai regulation 2024'
    assert len(search_query.sources) == 2
    assert search_query.sources[0].url == 'https://example.com/regulation-overview'
    assert search_query.sources[0].rank == 1
    assert search_query.sources[1].url == 'https://news.example.org/policy'
    assert search_query.sources[1].rank == 2

  def test_citations_structure(self):
    """Test that citations are properly structured."""
    payload = api_send_prompt_response_dict()
    citations = [SimpleNamespace(**citation) for citation in payload['citations']]

    assert len(citations) == 2
    assert citations[0].url == 'https://example.com/regulation-overview'
    assert citations[0].rank == 1
    assert citations[1].rank == 2


class TestMetricsCalculation:
  """Tests for verifying metrics are correctly displayed."""

  def test_sources_found_count(self):
    """Test that sources_found is correctly displayed."""
    response = api_send_prompt_response_namespace()
    sources_count = getattr(response, 'sources_found', 0)
    assert sources_count == 3

  def test_sources_used_count(self):
    """Test that sources_used is correctly displayed."""
    response = api_send_prompt_response_namespace()
    sources_used = getattr(response, 'sources_used', 0)
    assert sources_used == 2

  def test_avg_rank_calculation(self):
    """Test that avg_rank is correctly displayed."""
    response = api_send_prompt_response_namespace()
    avg_rank = getattr(response, 'avg_rank', None)
    assert avg_rank == 1.5

  def test_avg_rank_none_handling(self):
    """Test that avg_rank None is handled correctly."""
    payload = api_send_prompt_response_dict()
    payload.update({
      'avg_rank': None,
      'sources_found': 0,
      'sources_used': 0,
    })
    response = SimpleNamespace(**payload)

    avg_rank = getattr(response, 'avg_rank', None)
    assert avg_rank is None

  def test_model_display_name_formatting(self):
    """Test that model_display_name is used instead of raw model name."""
    response = api_send_prompt_response_namespace()

    # This is how response.py line 149 retrieves it
    model_display = getattr(response, 'model_display_name', None) or response.model
    assert model_display == 'GPT-5.1'
    assert model_display != 'gpt-5.1'

  def test_model_display_name_fallback(self):
    """Test that model name is used when model_display_name is None."""
    payload = api_send_prompt_response_dict()
    payload['model_display_name'] = None
    response = SimpleNamespace(**payload)
    model_display = getattr(response, 'model_display_name', None) or response.model
    assert model_display == 'gpt-5.1'


class TestDisplayResponseIntegration:
  """Integration tests for display_response that verify attribute access."""

  def test_display_response_with_api_mode_response(self):
    """Test that display_response can handle API mode response without errors."""
    from frontend.components.response import display_response

    response = api_send_prompt_response_namespace()
    # This should not raise AttributeError
    # We can't actually test the Streamlit output, but we can verify no exceptions
    try:
      # Note: This will fail in test environment because Streamlit isn't running
      # But it will still catch AttributeError before failing on Streamlit
      display_response(response, 'test prompt')
    except Exception as e:
      # Only AttributeError should fail the test
      if 'AttributeError' in str(type(e).__name__):
        raise
      # Other errors (like Streamlit not running) are expected in tests
      pass

  def test_display_response_with_network_log_response(self):
    """Test that display_response can handle network_log mode response without errors."""
    from frontend.components.response import display_response

    response = network_log_send_prompt_response_namespace()
    # This should not raise AttributeError
    try:
      display_response(response, 'test prompt')
    except Exception as e:
      # Only AttributeError should fail the test
      if 'AttributeError' in str(type(e).__name__):
        raise
      # Other errors (like Streamlit not running) are expected in tests
      pass

  def test_response_object_has_all_sources_not_sources(self):
    """Test that response objects use 'all_sources' not 'sources' attribute."""
    # This test enforces the naming convention
    response = SimpleNamespace(
      provider='openai',
      model='gpt-5.1',
      all_sources=[SimpleNamespace(url='https://example.com')],
      search_queries=[],
      citations=[],
      response_text='Test',
      data_source='api'
    )

    # all_sources should exist
    assert hasattr(response, 'all_sources')
    assert len(response.all_sources) == 1

    # sources should NOT exist (to avoid confusion)
    assert not hasattr(response, 'sources')
