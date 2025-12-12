"""Tests for InteractionRepository."""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.repositories.interaction_repository import InteractionRepository


@pytest.fixture
def db_session():
  """Create an in-memory SQLite database for testing."""
  # Create in-memory database
  engine = create_engine("sqlite:///:memory:")
  Base.metadata.create_all(engine)

  # Create session
  SessionLocal = sessionmaker(bind=engine)
  session = SessionLocal()

  yield session

  session.close()


@pytest.fixture
def repository(db_session):
  """Create repository instance with test database session."""
  return InteractionRepository(db_session)


class TestInteractionRepository:
  """Tests for InteractionRepository CRUD operations."""

  def test_save_basic_interaction(self, repository):
    """Test saving a basic interaction."""
    response_id = repository.save(
      prompt_text="What is AI?",
      provider_name="openai",
      model_name="gpt-4o",
      response_text="AI is...",
      response_time_ms=1500,
      search_queries=[],
      sources_used=[],
      raw_response={"content": "AI is..."},
      data_source="api",
      extra_links_count=0
    )

    assert response_id > 0

  def test_save_with_search_queries_and_sources(self, repository):
    """Test saving interaction with search queries and sources."""
    search_queries = [
      {
        "query": "AI definition",
        "order_index": 0,
        "sources": [
          {
            "url": "https://example.com/ai",
            "title": "What is AI",
            "domain": "example.com",
            "rank": 1
          },
          {
            "url": "https://example.com/ml",
            "title": "Machine Learning",
            "domain": "example.com",
            "rank": 2
          }
        ]
      }
    ]

    sources_used = [
      {
        "url": "https://example.com/ai",
        "title": "What is AI",
        "rank": 1
      }
    ]

    response_id = repository.save(
      prompt_text="What is AI?",
      provider_name="openai",
      model_name="gpt-4o",
      response_text="AI is...",
      response_time_ms=1500,
      search_queries=search_queries,
      sources_used=sources_used,
      raw_response={"content": "AI is..."},
      data_source="api"
    )

    assert response_id > 0

    # Verify saved correctly
    response = repository.get_by_id(response_id)
    assert response is not None
    assert len(response.search_queries) == 1
    assert len(response.search_queries[0].sources) == 2
    assert len(response.sources_used) == 1

  def test_get_by_id_with_eager_loading(self, repository):
    """Test get_by_id loads all relationships."""
    # Save an interaction
    response_id = repository.save(
      prompt_text="Test prompt",
      provider_name="google",
      model_name="gemini-2.0-flash-exp",
      response_text="Test response",
      response_time_ms=2000,
      search_queries=[
        {
          "query": "test query",
          "order_index": 0,
          "sources": [
            {"url": "https://test.com", "title": "Test", "rank": 1}
          ]
        }
      ],
      sources_used=[{"url": "https://test.com", "rank": 1}],
      raw_response={}
    )

    # Get by ID
    response = repository.get_by_id(response_id)

    # Verify all relationships loaded
    assert response is not None
    assert response.interaction is not None
    assert response.interaction.provider is not None
    assert len(response.search_queries) == 1
    assert len(response.search_queries[0].sources) == 1
    assert len(response.sources_used) == 1

  def test_get_by_id_not_found(self, repository):
    """Test get_by_id returns None for non-existent ID."""
    response = repository.get_by_id(999)
    assert response is None

  def test_get_recent_all(self, repository):
    """Test get_recent returns recent interactions."""
    # Save multiple interactions
    for i in range(5):
      repository.save(
        prompt_text=f"Prompt {i}",
        provider_name="openai",
        model_name="gpt-4o",
        response_text=f"Response {i}",
        response_time_ms=1000,
        search_queries=[],
        sources_used=[],
        raw_response={}
      )

    # Get recent
    results, total = repository.get_recent(page_size=10)

    assert total == 5
    assert len(results) == 5
    # Should be in descending order by created_at
    assert results[0].response_text == "Response 4"
    assert results[4].response_text == "Response 0"

  def test_get_recent_with_data_source_filter(self, repository):
    """Test get_recent filters by data_source."""
    # Save interactions with different data sources
    repository.save(
      prompt_text="API prompt",
      provider_name="openai",
      model_name="gpt-4o",
      response_text="API response",
      response_time_ms=1000,
      search_queries=[],
      sources_used=[],
      raw_response={},
      data_source="api"
    )

    repository.save(
      prompt_text="Network log prompt",
      provider_name="chatgpt",
      model_name="gpt-4o",
      response_text="Network log response",
      response_time_ms=2000,
      search_queries=[],
      sources_used=[],
      raw_response={},
      data_source="web"
    )

    # Get API interactions only
    api_results, api_total = repository.get_recent(data_source="api")
    assert api_total == 1
    assert len(api_results) == 1
    assert api_results[0].data_source == "api"

    # Get web interactions only
    network_results, network_total = repository.get_recent(data_source="web")
    assert network_total == 1
    assert len(network_results) == 1
    assert network_results[0].data_source == "web"

  def test_get_recent_with_limit(self, repository):
    """Test get_recent respects limit parameter."""
    # Save many interactions
    for i in range(20):
      repository.save(
        prompt_text=f"Prompt {i}",
        provider_name="openai",
        model_name="gpt-4o",
        response_text=f"Response {i}",
        response_time_ms=1000,
        search_queries=[],
        sources_used=[],
        raw_response={}
      )

    # Get with limit
    results, total = repository.get_recent(page_size=5)
    assert total == 20
    assert len(results) == 5

  def test_get_recent_defers_raw_payload(self, repository):
    """Recent list should not load raw_response_json to avoid OOMs."""
    repository.save(
      prompt_text="Heavy payload prompt",
      provider_name="openai",
      model_name="gpt-4o",
      response_text="ok",
      response_time_ms=1000,
      search_queries=[],
      sources_used=[],
      raw_response={"blob": "x" * 100_000},
    )

    results, total = repository.get_recent(page_size=1)

    assert total == 1
    assert len(results) == 1
    state = inspect(results[0])
    assert "raw_response_json" in state.unloaded

  def test_delete_existing_interaction(self, repository):
    """Test deleting an existing interaction."""
    # Save an interaction
    response_id = repository.save(
      prompt_text="Test prompt",
      provider_name="openai",
      model_name="gpt-4o",
      response_text="Test response",
      response_time_ms=1500,
      search_queries=[
        {
          "query": "test",
          "order_index": 0,
          "sources": [{"url": "https://test.com", "rank": 1}]
        }
      ],
      sources_used=[{"url": "https://test.com", "rank": 1}],
      raw_response={}
    )

    # Delete it
    result = repository.delete(response_id)
    assert result is True

    # Verify it's gone
    response = repository.get_by_id(response_id)
    assert response is None

  def test_delete_non_existent_interaction(self, repository):
    """Test deleting non-existent interaction returns False."""
    result = repository.delete(999)
    assert result is False

  def test_provider_reuse(self, repository):
    """Test that providers are reused, not recreated."""
    # Save two interactions with same provider
    repository.save(
      prompt_text="Prompt 1",
      provider_name="openai",
      model_name="gpt-4o",
      response_text="Response 1",
      response_time_ms=1000,
      search_queries=[],
      sources_used=[],
      raw_response={}
    )

    repository.save(
      prompt_text="Prompt 2",
      provider_name="openai",
      model_name="gpt-4o-mini",
      response_text="Response 2",
      response_time_ms=1500,
      search_queries=[],
      sources_used=[],
      raw_response={}
    )

    # Verify only one provider was created
    from app.models.database import Provider
    providers = repository.db.query(Provider).filter_by(name="openai").all()
    assert len(providers) == 1

  def test_network_log_exclusive_fields(self, repository):
    """Test saving network log exclusive fields."""
    search_queries = [
      {
        "query": "AI research",
        "order_index": 0,
        "internal_ranking_scores": {"score_1": 0.95},
        "query_reformulations": ["AI", "artificial intelligence"],
        "sources": [
          {
            "url": "https://example.com",
            "title": "AI Research",
            "rank": 1,
            "snippet_text": "AI is a field...",
            "internal_score": 0.92,
            "metadata": {"extra": "data"}
          }
        ]
      }
    ]

    sources_used = [
      {
        "url": "https://example.com",
        "rank": 1,
        "snippet_cited": "AI is a field...",
        "citation_confidence": 0.95,
        "metadata": {"citation_id": "1"}
      }
    ]

    response_id = repository.save(
      prompt_text="What is AI research?",
      provider_name="chatgpt",
      model_name="gpt-4o",
      response_text="AI research involves...",
      response_time_ms=2500,
      search_queries=search_queries,
      sources_used=sources_used,
      raw_response={},
      data_source="web",
      extra_links_count=2
    )

    # Verify all fields saved
    response = repository.get_by_id(response_id)
    assert response.data_source == "web"
    assert response.extra_links_count == 2

    search_query = response.search_queries[0]
    assert search_query.internal_ranking_scores == {"score_1": 0.95}
    assert search_query.query_reformulations == ["AI", "artificial intelligence"]

    source = search_query.sources[0]
    assert source.snippet_text == "AI is a field..."
    assert source.internal_score == 0.92
    assert source.metadata_json == {"extra": "data"}

    citation = response.sources_used[0]
    assert citation.snippet_cited == "AI is a field..."
    assert citation.citation_confidence == 0.95
    assert citation.metadata_json == {"citation_id": "1"}
