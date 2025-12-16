"""Tests for parsing Google AI Mode folif HTML payloads."""

from backend.app.services.providers.base_provider import SearchQuery
from frontend.network_capture.google_aimode_parser import parse_google_aimode_folif_html


def test_parse_google_aimode_folif_html_extracts_sidebar_sources_and_citations():
  """Parser should normalize sidebar sources and in-response citations."""
  uuid_block = (
    '<!--Sv6Kpe[["9d06f938-e592-4929-a3c9-e91ed6852000",'
    '["Example One","Sidebar desc",'
    '"https://encrypted-tbn0.gstatic.com/faviconV2?url=https://example.com&client=AIM",'
    '"https://example.com",["Example"],"https://example.com/a",null,null,"1",null,[],[],0,[],'
    'null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,'
    'null,null,null,null,null,"23 Nov 2025",0]]]-->'
  )
  html = """
  <div data-target-container-id="13">
    <a target="_blank" rel="noopener" aria-label="Example One" href="https://example.com/a"></a>
    <div>23 Nov 2025 Example One description.</div>
    <a target="_blank" rel="noopener" aria-label="Example Two" href="https://example.org/b"></a>
    <div>11 Nov 2025 Example Two description.</div>
  </div>

  <div data-target-container-id="5">
    <p>This is the first sentence.</p>
    <p>This is the second sentence before a citation
      <button data-icl-uuid="9d06f938-e592-4929-a3c9-e91ed6852000"></button>.
    </p>
    <p>And here is an extra link <a href="https://extra.example.net/x">Extra</a>.</p>
    <p><a href="https://policies.google.com/privacy">Privacy</a></p>
    <div>AI responses may include mistakes. Learn more</div>
  </div>

  """ + uuid_block
  response = parse_google_aimode_folif_html(
    html,
    response_time_ms=1234,
    search_queries=[SearchQuery(query="test", order_index=0)],
  )
  assert response.provider == "google"
  assert response.model == "google-aimode"
  assert response.data_source == "web"
  assert response.response_time_ms == 1234
  assert "This is the first sentence." in response.response_text
  assert "AI responses may include mistakes" not in response.response_text

  assert [s.url for s in response.sources] == ["https://example.com/a", "https://example.org/b"]
  assert response.sources[0].pub_date == "23 Nov 2025"
  assert response.sources[0].search_description is not None

  citation_urls = [c.url for c in response.citations]
  assert "https://example.com/a" in citation_urls
  assert "https://extra.example.net/x" in citation_urls
  assert "https://policies.google.com/privacy" not in citation_urls

  used = [c for c in response.citations if c.url == "https://example.com/a"][0]
  assert used.rank == 1
  assert isinstance(used.snippet_cited, str)
  assert "second sentence" in used.snippet_cited.lower()


def test_parse_google_aimode_folif_html_without_search_queries_has_no_sources():
  """If we cannot confirm a search ran, sources should not be populated."""
  html = """
  <div data-target-container-id="5">
    <p>Hello world answer <a href="https://example.com/a">Example One</a>.</p>
  </div>
  """
  response = parse_google_aimode_folif_html(html, response_time_ms=10)
  assert response.search_queries == []
  assert response.sources == []
  assert [c.url for c in response.citations] == ["https://example.com/a"]
  assert response.citations[0].rank is None
