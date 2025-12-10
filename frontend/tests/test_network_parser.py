"""Tests for the ChatGPT network log parser."""

from frontend.network_capture.parser import NetworkLogParser


def _build_sse_body():
  """Helper to craft minimal SSE body with search queries and sources."""
  lines = [
    # Search query metadata
    'data: {"v":{"message":{"metadata":{"search_model_queries":{"queries":["latest ai news"]}}}}}',
    # Search result group with one entry
    'data: {"v":{"message":{"metadata":{"search_result_groups":[{"domain":"example.com","entries":[{"type":"search_result","url":"https://example.com/article","title":"Example Title","snippet":"Snippet text"}]}]}}}}'  # noqa: E501
  ]
  return "\n".join(lines)


def test_parse_chatgpt_log_extracts_queries_sources_and_citations():
  """Parser should create search queries, sources, and citations from SSE body."""
  response = NetworkLogParser.parse_chatgpt_log(
    network_response={"body": _build_sse_body()},
    model="chatgpt-free",
    response_time_ms=1500,
    extracted_response_text="Answer with [1]\n\n[1]: https://example.com/article \"Example Title\""
  )

  assert response.provider == "openai"
  assert response.model == "chatgpt-free"
  assert len(response.search_queries) == 1
  assert response.search_queries[0].query == "latest ai news"
  assert len(response.sources) == 1
  assert response.sources[0].url == "https://example.com/article"
  assert len(response.citations) == 1
  assert response.citations[0].url == "https://example.com/article"
  assert response.extra_links_count == 0
  assert response.data_source == "network_log"


def test_parse_chatgpt_log_handles_missing_body():
  """Empty network body should return an empty ProviderResponse."""
  response = NetworkLogParser.parse_chatgpt_log(
    network_response={"body": ""},
    model="chatgpt-free",
    response_time_ms=500,
  )
  assert response.response_text == ""
  assert response.sources == []
  assert response.search_queries == []
