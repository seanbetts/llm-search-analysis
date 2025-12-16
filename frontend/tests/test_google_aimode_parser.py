"""Tests for parsing Google AI Mode folif HTML payloads."""

from backend.app.services.providers.base_provider import SearchQuery
from frontend.network_capture.google_aimode_parser import parse_google_aimode_folif_html


def test_parse_google_aimode_folif_html_extracts_sidebar_sources_and_citations():
  """Parser should normalize sidebar sources and in-response citations."""
  uuid_block_primary = (
    '<!--Sv6Kpe[["9d06f938-e592-4929-a3c9-e91ed6852000",'
    '["Example One","Sidebar desc",'
    '"https://encrypted-tbn0.gstatic.com/faviconV2?url=https://example.com&client=AIM",'
    '"https://example.com",["Example"],"https://example.com/a",null,null,"1",null,[],[],0,[],'
    'null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,'
    'null,null,null,null,null,"23 Nov 2025",0]]]-->'
  )
  uuid_block_related = (
    '<!--Sv6Kpe[["9d06f938-e592-4929-a3c9-e91ed6852000",'
    '["Example Two","Other desc",'
    '"https://encrypted-tbn0.gstatic.com/faviconV2?url=https://example.org&client=AIM",'
    '"https://example.org",["Example"],"https://example.org/b",null,null,"1",null,[],[],0,[],'
    'null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,'
    'null,null,null,null,null,"11 Nov 2025",0]]]-->'
  )
  uuid_block_related_extra = (
    '<!--Sv6Kpe[["9d06f938-e592-4929-a3c9-e91ed6852000",'
    '["Example Extra","Extra desc",'
    '"https://encrypted-tbn0.gstatic.com/faviconV2?url=https://extra.example.net&client=AIM",'
    '"https://extra.example.net",["Example"],"https://extra.example.net/from-related",null,null,"1",null,[],[],0,[],'
    'null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,'
    'null,null,null,null,null,"11 Nov 2025",0]]]-->'
  )
  html = """
  <div data-target-container-id="13">
    <button aria-label="2 sites"></button>
    <a target="_blank" rel="noopener" aria-label="Example One" href="https://example.com/a"></a>
    <div>23 Nov 2025 Example One description.</div>
    <a target="_blank" rel="noopener" aria-label="Example Two" href="https://example.org/b"></a>
    <div>11 Nov 2025 Example Two description.</div>
    <a target="_blank" rel="noopener" aria-label="Example Three" href="https://example.net/c"></a>
    <div>01 Jan 2024 Example Three description.</div>
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

  """ + uuid_block_primary + uuid_block_related + uuid_block_related_extra
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
  assert "- " not in response.response_text  # no list in this fixture

  assert [s.url for s in response.sources] == [
    "https://example.com/a",
    "https://example.org/b",
    "https://extra.example.net/from-related",
  ]
  assert response.sources[0].pub_date == "23 Nov 2025"
  assert response.sources[0].search_description is not None

  citation_urls = [c.url for c in response.citations]
  assert "https://example.com/a" in citation_urls
  assert "https://example.org/b" in citation_urls
  assert "https://extra.example.net/x" in citation_urls
  # Related-link sources that aren't in the sidebar should still be treated as found/used.
  assert "https://extra.example.net/from-related" in citation_urls
  assert "https://policies.google.com/privacy" not in citation_urls

  used = [c for c in response.citations if c.url in {"https://example.com/a", "https://example.org/b", "https://extra.example.net/from-related"}]
  assert all(isinstance(c.rank, int) for c in used)
  assert all(isinstance(c.snippet_cited, str) for c in used)
  assert any("second sentence" in (c.snippet_cited or "").lower() for c in used)


def test_snippet_cited_includes_link_text_in_sentence():
  """Snippet extraction should not drop visible anchor text inside sentences."""
  uuid_block = (
    '<!--Sv6Kpe[["9d06f938-e592-4929-a3c9-e91ed6852000",'
    '["Steam Store","Desc",'
    '"https://encrypted-tbn0.gstatic.com/faviconV2?url=https://store.steampowered.com&client=AIM",'
    '"https://store.steampowered.com",["Steam"],"https://store.steampowered.com/sale/steammachine",'
    'null,null,"1",null,[],[],0,[],'
    'null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,'
    'null,null,null,null,null,"11 Nov 2025",0]]]-->'
  )
  html = """
  <div data-target-container-id="13">
    <button aria-label="1 sites"></button>
    <a target="_blank" rel="noopener" aria-label="Steam Machine" href="https://store.steampowered.com/sale/steammachine"></a>
    <div>11 Nov 2025 Steam Machine description.</div>
  </div>
  <div data-target-container-id="5">
    <p>Distribution: It will be sold directly through the
      <a href="https://store.steampowered.com/sale/steammachine">Official Steam Store</a>
      and Komodo, similar to the Steam Deck.
      <button data-icl-uuid="9d06f938-e592-4929-a3c9-e91ed6852000"></button>
    </p>
    <div>AI responses may include mistakes. Learn more</div>
  </div>
  """ + uuid_block
  response = parse_google_aimode_folif_html(
    html,
    response_time_ms=10,
    search_queries=[SearchQuery(query="test", order_index=0)],
  )
  used = [c for c in response.citations if c.rank]
  assert used
  assert any("official steam store" in (c.snippet_cited or "").lower() for c in used)


def test_markdown_extraction_does_not_add_blank_lines_between_list_items():
  """AI Mode bullets should render as a compact markdown list."""
  html = """
  <div data-target-container-id="5">
    <p>Intro.</p>
    <ul>
      <li>First bullet.</li>
      <li>Second bullet.</li>
    </ul>
    <div>AI responses may include mistakes. Learn more</div>
  </div>
  """
  response = parse_google_aimode_folif_html(html, response_time_ms=10)
  assert "Intro." in response.response_text
  assert "\n- First bullet.\n- Second bullet.\n" in (response.response_text + "\n")


def test_response_text_strips_trailing_sites_source_list():
  """AI Mode sometimes appends a raw 'N sites' dump into the answer container."""
  html = """
  <div data-target-container-id="5">
    <p>Answer paragraph.</p>
    <div>11 sites</div>
    <div>https://example.com Example 1 11 Nov 2025 — Desc</div>
    <div>https://example.org Example 2 12 Nov 2025 — Desc</div>
    <div>AI responses may include mistakes. Learn more</div>
  </div>
  """
  response = parse_google_aimode_folif_html(html, response_time_ms=10)
  assert response.response_text.strip() == "Answer paragraph."


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
