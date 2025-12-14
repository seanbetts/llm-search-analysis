"""Unit tests for ExportService."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from app.api.v1.schemas.responses import (
  Citation,
  SearchQuery,
  SendPromptResponse,
  Source,
)
from app.services.export_service import ExportService


@pytest.fixture
def mock_interaction_service():
  return Mock()


@pytest.fixture
def export_service(mock_interaction_service):
  return ExportService(mock_interaction_service)


def _api_response():
  return SendPromptResponse(
    interaction_id=123,
    prompt="What is AI?",
    response_text="Answer referencing [Source][1]\n\n[1]: https://example.com \"Example\"",
    search_queries=[
      SearchQuery(
        query="ai news",
        order_index=0,
        sources=[
          Source(
            url="https://example.com",
            title="Example Source",
            domain="example.com",
            rank=1,
            search_description="Snippet text",
            pub_date="2024-01-01",
          )
        ],
      )
    ],
    citations=[
      Citation(
        url="https://example.com",
        title="Example Source",
        rank=1,
        snippet_cited="Snippet text",
      )
    ],
    provider="OpenAI",
    model="gpt-5.1",
    model_display_name="GPT-5.1",
    response_time_ms=1200,
    data_source="api",
    sources_found=1,
    sources_used=1,
    avg_rank=1.0,
    extra_links_count=0,
    created_at=datetime.utcnow(),
  )


def _network_log_response():
  return SendPromptResponse(
    interaction_id=456,
    prompt="Network mode prompt",
    response_text="Network response body",
    search_queries=[
      SearchQuery(
        query="network capture",
        order_index=0,
        sources=[]
      )
    ],
    citations=[],
    all_sources=[
      Source(
        url="https://example.org",
        title="Network Source",
        domain="example.org",
        rank=None,
        search_description="Captured snippet",
      )
    ],
    provider="OpenAI",
    model="chatgpt-free",
    model_display_name="ChatGPT (Free)",
    response_time_ms=2000,
    data_source="web",
    sources_found=1,
    sources_used=0,
    avg_rank=None,
    extra_links_count=2,
    created_at=datetime.utcnow(),
  )


def test_build_markdown_returns_none_when_not_found(export_service, mock_interaction_service):
  """Exporting a missing interaction should return None."""
  mock_interaction_service.get_interaction_details.return_value = None
  assert export_service.build_markdown(999) is None
  mock_interaction_service.get_interaction_details.assert_called_once_with(999)


def test_build_markdown_formats_api_interaction(export_service, mock_interaction_service):
  """Exported markdown should include key sections for API data."""
  mock_interaction_service.get_interaction_details.return_value = _api_response()

  markdown = export_service.build_markdown(123)

  assert markdown is not None
  assert "# Interaction 123" in markdown
  assert "## Prompt" in markdown and "What is AI?" in markdown
  assert "## Search Queries" in markdown
  assert "### Query 1 Sources (1)" in markdown
  # Reference-style links should be converted inline
  assert "[Source](https://example.com)" in markdown


def test_build_markdown_handles_network_log_sources(export_service, mock_interaction_service):
  """Network log exports should list Sources Found section."""
  mock_interaction_service.get_interaction_details.return_value = _network_log_response()

  markdown = export_service.build_markdown(456)

  assert "Analysis: Web" in markdown
  assert "## Sources Found (1)" in markdown
  assert "Network Source" in markdown
