"""Tests for parsing Google AI Mode folif HTML payloads."""

from frontend.network_capture.google_aimode_parser import (
  extract_sources_from_folif_html,
  parse_google_aimode_folif_html,
)


def test_extract_sources_from_folif_html_filters_favicon_and_dedupes():
  """Extracted sources should ignore favicon URLs and dedupe repeated sources."""
  html = """
  <!--Sv6Kpe[[0,[[&quot;Example One&quot;,null,
  &quot;https://encrypted-tbn0.gstatic.com/faviconV2?url\\u003dhttps://example.com&amp;client\\u003dAIM&quot;,
  null,null,&quot;https://example.com/article&quot;]]]]-->
  <!--Sv6Kpe[[0,[[&quot;Example One&quot;,null,&quot;https://example.com/article&quot;]]]]-->
  <!--Sv6Kpe[[0,[[&quot;Example Two&quot;,null,&quot;https://news.google.com/articles/abc123&quot;]]]]-->
  """
  sources = extract_sources_from_folif_html(html)
  assert [s.url for s in sources] == [
    "https://example.com/article",
    "https://news.google.com/articles/abc123",
  ]


def test_parse_google_aimode_folif_html_extracts_answer_and_sources():
  """Parser should return ProviderResponse compatible with web persistence."""
  html = """
  <div>
    <p>Hello world answer.</p>
    <p>Second paragraph.</p>
    <div>AI responses may include mistakes. Learn more</div>
  </div>
  <!--Sv6Kpe[[0,[[&quot;Example One&quot;,null,&quot;https://example.com/article&quot;]]]]-->
  <!--Sv6Kpe[[0,[[&quot;Example Two&quot;,null,&quot;https://example.org/post&quot;]]]]-->
  """
  response = parse_google_aimode_folif_html(html, response_time_ms=1234)
  assert response.provider == "google"
  assert response.model == "google-aimode"
  assert response.data_source == "web"
  assert response.response_time_ms == 1234
  assert response.response_text == "Hello world answer. Second paragraph."
  assert [s.url for s in response.sources] == ["https://example.com/article", "https://example.org/post"]
  assert [c.url for c in response.citations] == ["https://example.com/article", "https://example.org/post"]

