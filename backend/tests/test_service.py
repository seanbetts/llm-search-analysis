"""Tests for InteractionService business logic."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from app.services.interaction_service import InteractionService
from app.core.utils import normalize_model_name, extract_domain, calculate_average_rank


class TestInteractionService:
  """Tests for InteractionService with mocked repository."""

  @pytest.fixture
  def mock_repository(self):
    """Create a mock repository."""
    return Mock()

  @pytest.fixture
  def service(self, mock_repository):
    """Create service with mocked repository."""
    return InteractionService(mock_repository)

  def test_save_interaction_normalizes_model_name(self, service, mock_repository):
    """Test that save_interaction normalizes model names."""
    mock_repository.save.return_value = 1

    # Test with gpt-5-1 should normalize to gpt-5.1
    service.save_interaction(
      prompt="Test",
      provider="openai",
      model="gpt-5-1",
      response_text="Response",
      response_time_ms=1000,
      search_queries=[],
      citations=[],
      raw_response={}
    )

    # Verify repository was called with normalized model name
    mock_repository.save.assert_called_once()
    args, kwargs = mock_repository.save.call_args
    assert kwargs["model_name"] == "gpt-5.1"

  def test_save_interaction_extracts_domains_from_sources(self, service, mock_repository):
    """Test that save_interaction extracts domains from source URLs."""
    mock_repository.save.return_value = 1

    search_queries = [{
      "query": "test",
      "sources": [
        {"url": "https://www.example.com/page"},
        {"url": "https://test.org/article"},
      ]
    }]

    service.save_interaction(
      prompt="Test",
      provider="openai",
      model="gpt-4o",
      response_text="Response",
      response_time_ms=1000,
      search_queries=search_queries,
      citations=[],
      raw_response={}
    )

    # Verify domains were extracted
    args, kwargs = mock_repository.save.call_args
    saved_queries = kwargs["search_queries"]
    assert saved_queries[0]["sources"][0]["domain"] == "example.com"
    assert saved_queries[0]["sources"][1]["domain"] == "test.org"

  def test_save_interaction_extracts_domains_from_citations(self, service, mock_repository):
    """Test that save_interaction extracts domains from citation URLs."""
    mock_repository.save.return_value = 1

    citations = [
      {"url": "https://www.example.com/cited"},
      {"url": "https://source.net/article"},
    ]

    service.save_interaction(
      prompt="Test",
      provider="openai",
      model="gpt-4o",
      response_text="Response",
      response_time_ms=1000,
      search_queries=[],
      citations=citations,
      raw_response={}
    )

    # Verify domains were extracted
    args, kwargs = mock_repository.save.call_args
    saved_citations = kwargs["sources_used"]
    assert saved_citations[0]["domain"] == "example.com"
    assert saved_citations[1]["domain"] == "source.net"

  def test_get_recent_interactions_calculates_counts(self, service, mock_repository):
    """Test that get_recent_interactions calculates query/source/citation counts."""
    # Create mock response object
    mock_response = MagicMock()
    mock_response.id = 1
    mock_response.response_text = "Test response"
    mock_response.response_time_ms = 1500
    mock_response.data_source = "api"
    mock_response.created_at = datetime.utcnow()

    # Create mock prompt/session/provider
    mock_response.prompt = MagicMock()
    mock_response.prompt.prompt_text = "Test prompt"
    mock_response.prompt.session = MagicMock()
    mock_response.prompt.session.provider = MagicMock()
    mock_response.prompt.session.provider.name = "openai"
    mock_response.prompt.session.provider.display_name = "OpenAI"
    mock_response.prompt.session.model_used = "gpt-4o"

    # Create 2 search queries with 3 and 2 sources
    mock_query1 = MagicMock()
    mock_query1.sources = [MagicMock(), MagicMock(), MagicMock()]
    mock_query2 = MagicMock()
    mock_query2.sources = [MagicMock(), MagicMock()]
    mock_response.search_queries = [mock_query1, mock_query2]

    # Create 4 citations
    mock_response.sources_used = [
      MagicMock(rank=1),
      MagicMock(rank=3),
      MagicMock(rank=5),
      MagicMock(rank=None),
    ]

    mock_repository.get_recent.return_value = [mock_response]

    # Get recent interactions
    summaries = service.get_recent_interactions(limit=10)

    # Verify counts
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.search_query_count == 2  # 2 queries
    assert summary.source_count == 5  # 3 + 2 = 5 sources
    assert summary.citation_count == 4  # 4 citations

  def test_get_recent_interactions_calculates_average_rank(self, service, mock_repository):
    """Test that get_recent_interactions calculates average rank."""
    mock_response = MagicMock()
    mock_response.id = 1
    mock_response.response_text = "Test"
    mock_response.response_time_ms = 1000
    mock_response.data_source = "api"
    mock_response.created_at = datetime.utcnow()
    mock_response.prompt = MagicMock()
    mock_response.prompt.prompt_text = "Test"
    mock_response.prompt.session = MagicMock()
    mock_response.prompt.session.provider = MagicMock()
    mock_response.prompt.session.provider.name = "openai"
    mock_response.prompt.session.provider.display_name = "OpenAI"
    mock_response.prompt.session.model_used = "gpt-4o"
    mock_response.search_queries = []

    # Citations with ranks 1, 3, 5 -> average = 3.0
    mock_response.sources_used = [
      MagicMock(rank=1),
      MagicMock(rank=3),
      MagicMock(rank=5),
    ]

    mock_repository.get_recent.return_value = [mock_response]

    summaries = service.get_recent_interactions()

    assert summaries[0].average_rank == 3.0

  def test_get_recent_interactions_handles_none_ranks(self, service, mock_repository):
    """Test that average rank calculation ignores None ranks."""
    mock_response = MagicMock()
    mock_response.id = 1
    mock_response.response_text = "Test"
    mock_response.response_time_ms = 1000
    mock_response.data_source = "api"
    mock_response.created_at = datetime.utcnow()
    mock_response.prompt = MagicMock()
    mock_response.prompt.prompt_text = "Test"
    mock_response.prompt.session = MagicMock()
    mock_response.prompt.session.provider = MagicMock()
    mock_response.prompt.session.provider.name = "openai"
    mock_response.prompt.session.provider.display_name = "OpenAI"
    mock_response.prompt.session.model_used = "gpt-4o"
    mock_response.search_queries = []

    # Mix of ranks and None
    mock_response.sources_used = [
      MagicMock(rank=2),
      MagicMock(rank=None),
      MagicMock(rank=4),
    ]

    mock_repository.get_recent.return_value = [mock_response]

    summaries = service.get_recent_interactions()

    # Should only average 2 and 4 -> 3.0
    assert summaries[0].average_rank == 3.0

  def test_get_recent_interactions_with_data_source_filter(self, service, mock_repository):
    """Test filtering by data source."""
    mock_repository.get_recent.return_value = []

    service.get_recent_interactions(limit=50, data_source="network_log")

    # Verify filter was passed to repository
    mock_repository.get_recent.assert_called_once_with(
      limit=50,
      data_source="network_log"
    )

  def test_get_interaction_details_returns_full_response(self, service, mock_repository):
    """Test that get_interaction_details returns full SendPromptResponse."""
    # Create comprehensive mock response
    mock_response = MagicMock()
    mock_response.id = 123
    mock_response.response_text = "Full response text"
    mock_response.response_time_ms = 2500
    mock_response.data_source = "api"
    mock_response.extra_links_count = 2
    mock_response.created_at = datetime.utcnow()
    mock_response.raw_response_json = {"key": "value"}

    # Mock prompt/session/provider
    mock_response.prompt = MagicMock()
    mock_response.prompt.prompt_text = "What is the future of AI?"
    mock_response.prompt.session = MagicMock()
    mock_response.prompt.session.provider = MagicMock()
    mock_response.prompt.session.provider.name = "google"
    mock_response.prompt.session.provider.display_name = "Google"
    mock_response.prompt.session.model_used = "gemini-2.5-flash"

    # Mock search queries
    mock_source = MagicMock()
    mock_source.url = "https://example.com"
    mock_source.title = "Example"
    mock_source.domain = "example.com"
    mock_source.rank = 1
    mock_source.pub_date = None
    mock_source.snippet_text = None
    mock_source.internal_score = None
    mock_source.metadata_json = None

    mock_query = MagicMock()
    mock_query.search_query = "test query"
    mock_query.sources = [mock_source]
    mock_query.created_at = datetime.utcnow()
    mock_query.order_index = 0
    mock_query.internal_ranking_scores = None
    mock_query.query_reformulations = None
    mock_response.search_queries = [mock_query]

    # Mock citations
    mock_citation = MagicMock()
    mock_citation.url = "https://example.com"
    mock_citation.title = "Example"
    mock_citation.rank = 1
    mock_citation.snippet_used = None
    mock_citation.citation_confidence = None
    mock_citation.metadata_json = None
    mock_response.sources_used = [mock_citation]

    mock_repository.get_by_id.return_value = mock_response

    # Get details
    result = service.get_interaction_details(123)

    # Verify full response
    assert result is not None
    assert result.response_text == "Full response text"
    assert result.provider == "Google"  # API returns display name
    assert result.model == "gemini-2.5-flash"
    assert result.response_time_ms == 2500
    assert result.interaction_id == 123
    assert len(result.search_queries) == 1
    assert len(result.citations) == 1

  def test_get_interaction_details_not_found(self, service, mock_repository):
    """Test get_interaction_details returns None when not found."""
    mock_repository.get_by_id.return_value = None

    result = service.get_interaction_details(999)

    assert result is None

  def test_delete_interaction(self, service, mock_repository):
    """Test delete_interaction delegates to repository."""
    mock_repository.delete.return_value = True

    result = service.delete_interaction(123)

    assert result is True
    mock_repository.delete.assert_called_once_with(123)

  def test_delete_interaction_not_found(self, service, mock_repository):
    """Test delete returns False when interaction not found."""
    mock_repository.delete.return_value = False

    result = service.delete_interaction(999)

    assert result is False


class TestUtilityFunctions:
  """Tests for utility functions."""

  def test_normalize_model_name_gpt(self):
    """Test normalizing GPT model names."""
    assert normalize_model_name("gpt-5-1") == "gpt-5.1"
    assert normalize_model_name("gpt-5-2") == "gpt-5.2"
    assert normalize_model_name("gpt-4o") == "gpt-4o"  # No change

  def test_normalize_model_name_gemini(self):
    """Test normalizing Gemini model names."""
    # Gemini models with text suffix don't get normalized (last part doesn't start with digit)
    assert normalize_model_name("gemini-3-0-flash") == "gemini-3-0-flash"
    assert normalize_model_name("gemini-2-5-pro") == "gemini-2-5-pro"
    # But if they did end with digits, they would normalize
    assert normalize_model_name("gemini-2-5") == "gemini-2.5"

  def test_normalize_model_name_claude(self):
    """Test normalizing Claude model names."""
    # Claude models with text suffix don't get normalized
    assert normalize_model_name("claude-3-7-sonnet") == "claude-3-7-sonnet"
    # Canonical models from MODEL_PROVIDER_MAP are preserved exactly (bug fix)
    # Previously this would be corrupted to "claude-sonnet-4-5.2-0250929"
    assert normalize_model_name("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5-20250929"
    # The function works best with simple two-digit versions
    assert normalize_model_name("claude-4-5") == "claude-4.5"

  def test_extract_domain_basic(self):
    """Test basic domain extraction."""
    assert extract_domain("https://www.example.com/path") == "example.com"
    assert extract_domain("https://example.com/path") == "example.com"
    assert extract_domain("http://subdomain.example.com") == "subdomain.example.com"

  def test_extract_domain_with_port(self):
    """Test domain extraction with port."""
    assert extract_domain("https://example.com:8080/path") == "example.com:8080"

  def test_extract_domain_invalid(self):
    """Test domain extraction with invalid URLs."""
    assert extract_domain("not a url") is None
    assert extract_domain("") is None

  def test_calculate_average_rank(self):
    """Test average rank calculation."""
    citations = [
      MagicMock(rank=1),
      MagicMock(rank=3),
      MagicMock(rank=5),
    ]
    assert calculate_average_rank(citations) == 3.0

  def test_calculate_average_rank_with_none(self):
    """Test average rank ignores None values."""
    citations = [
      MagicMock(rank=2),
      MagicMock(rank=None),
      MagicMock(rank=4),
    ]
    assert calculate_average_rank(citations) == 3.0

  def test_calculate_average_rank_all_none(self):
    """Test average rank returns None when all ranks are None."""
    citations = [
      MagicMock(rank=None),
      MagicMock(rank=None),
    ]
    assert calculate_average_rank(citations) is None

  def test_calculate_average_rank_empty(self):
    """Test average rank returns None for empty list."""
    assert calculate_average_rank([]) is None
