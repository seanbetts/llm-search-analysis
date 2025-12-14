"""Test web snippet extraction from response_text footnotes."""

import pytest
from sqlalchemy import create_engine
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


class TestWebSnippetExtraction:
  """Test citation snippet extraction for web analyses."""

  def test_extract_snippets_from_footnotes(self, repository):
    """Snippets should be extracted from response_text footnotes for web sources."""
    # Realistic response_text with inline citations and footnotes
    response_text = """Based on my analysis of recent developments:

The M4 chip represents Apple's latest advancement ([Apple Newsroom][1]).
According to industry reports, the new MacBook Pro features significant performance improvements ([The Verge][2]).

Key features include:
* Enhanced neural engine capabilities ([Apple Newsroom][1])
* Up to 24GB unified memory ([The Verge][2])

[1]: https://www.apple.com/newsroom/2024/11/new-macbook-pro "Apple Newsroom"
[2]: https://www.theverge.com/2024/11/macbook-pro-m4 "The Verge"
"""

    sources_used = [
      {
        "url": "https://www.apple.com/newsroom/2024/11/new-macbook-pro",
        "title": "Apple Newsroom",
        "rank": 1,
      },
      {
        "url": "https://www.theverge.com/2024/11/macbook-pro-m4",
        "title": "The Verge",
        "rank": 2,
      }
    ]

    response_id = repository.save(
      prompt_text="What are the new MacBook Pro features?",
      provider_name="openai",
      model_name="gpt-4o",
      response_text=response_text,
      response_time_ms=1500,
      search_queries=[],
      sources_used=sources_used,
      raw_response={},
      data_source="web",
    )

    # Verify snippets were extracted
    response = repository.get_by_id(response_id)
    sources = response.sources_used

    assert len(sources) == 2

    # Check first source
    source1 = next(s for s in sources if "apple.com" in s.url)
    assert source1.snippet_cited is not None
    assert "M4 chip" in source1.snippet_cited or "latest advancement" in source1.snippet_cited
    assert source1.metadata_json.get("citation_number") == 1

    # Check second source
    source2 = next(s for s in sources if "theverge.com" in s.url)
    assert source2.snippet_cited is not None
    assert "performance improvements" in source2.snippet_cited or "industry reports" in source2.snippet_cited
    assert source2.metadata_json.get("citation_number") == 2

  def test_web_sources_without_footnotes(self, repository):
    """Web sources without footnotes should have None snippets."""
    response_text = "Simple response without citations."

    sources_used = [
      {
        "url": "https://example.com",
        "title": "Example",
        "rank": 1,
      }
    ]

    response_id = repository.save(
      prompt_text="Test query",
      provider_name="openai",
      model_name="gpt-4o",
      response_text=response_text,
      response_time_ms=1000,
      search_queries=[],
      sources_used=sources_used,
      raw_response={},
      data_source="web",
    )

    response = repository.get_by_id(response_id)
    source = response.sources_used[0]

    # No footnotes in response_text, so snippet should be None
    assert source.snippet_cited is None
    assert source.metadata_json.get("citation_number") is None

  def test_url_normalization_in_footnote_matching(self, repository):
    """URLs with query params should still match footnotes."""
    response_text = """Recent research shows interesting findings ([Source][1]).

[1]: https://example.com/article "Source"
"""

    sources_used = [
      {
        "url": "https://example.com/article?utm_source=chatgpt.com",  # Has query params
        "title": "Source",
        "rank": 1,
      }
    ]

    response_id = repository.save(
      prompt_text="Test query",
      provider_name="openai",
      model_name="gpt-4o",
      response_text=response_text,
      response_time_ms=1000,
      search_queries=[],
      sources_used=sources_used,
      raw_response={},
      data_source="web",
    )

    response = repository.get_by_id(response_id)
    source = response.sources_used[0]

    # Should match despite query params difference
    assert source.snippet_cited is not None
    assert "Recent research" in source.snippet_cited
    assert source.metadata_json.get("citation_number") == 1
