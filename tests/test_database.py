"""
Tests for database operations.
"""

import pytest
from src.database import Database, Provider, SessionModel, Prompt, Response
from src.providers.base_provider import SearchQuery, Source, Citation


class TestDatabase:
    """Test suite for database operations."""

    @pytest.fixture
    def test_db(self):
        """Create an in-memory test database."""
        db = Database(database_url="sqlite:///:memory:")
        db.create_tables()
        db.ensure_providers()
        return db

    def test_create_tables(self, test_db):
        """Test database tables are created successfully."""
        session = test_db.get_session()
        try:
            # Check providers table
            providers = session.query(Provider).all()
            assert len(providers) == 3
            provider_names = [p.name for p in providers]
            assert "openai" in provider_names
            assert "google" in provider_names
            assert "anthropic" in provider_names
        finally:
            session.close()

    def test_save_interaction(self, test_db):
        """Test saving a complete interaction to database."""
        # Create test data
        search_queries = [SearchQuery(query="test query")]
        sources = [Source(url="https://example.com", title="Example", domain="example.com")]
        citations = [Citation(url="https://example.com", title="Example")]

        # Save interaction
        response_id = test_db.save_interaction(
            provider_name="openai",
            model="gpt-5.1",
            prompt="test prompt",
            response_text="test response",
            search_queries=search_queries,
            sources=sources,
            citations=citations,
            response_time_ms=1000,
            raw_response={}
        )

        assert response_id is not None

        # Verify saved data
        session = test_db.get_session()
        try:
            response = session.query(Response).filter_by(id=response_id).first()
            assert response is not None
            assert response.response_text == "test response"
            assert response.response_time_ms == 1000

            # Check prompt
            prompt = response.prompt
            assert prompt.prompt_text == "test prompt"

            # Check session
            prompt_session = prompt.session
            assert prompt_session.model_used == "gpt-5.1"

            # Check provider
            provider = prompt_session.provider
            assert provider.name == "openai"

            # Check search calls
            assert len(response.search_calls) >= 1
            search_call = response.search_calls[0]
            assert search_call.search_query == "test query"

            # Check sources
            assert len(search_call.sources) == 1
            source = search_call.sources[0]
            assert source.url == "https://example.com"
            assert source.title == "Example"

            # Check citations
            assert len(response.citations) == 1
            citation = response.citations[0]
            assert citation.url == "https://example.com"

        finally:
            session.close()

    def test_get_recent_interactions(self, test_db):
        """Test retrieving recent interactions."""
        # Save multiple interactions
        for i in range(3):
            test_db.save_interaction(
                provider_name="openai",
                model="gpt-5.1",
                prompt=f"test prompt {i}",
                response_text=f"test response {i}",
                search_queries=[SearchQuery(query=f"query {i}")],
                sources=[Source(url=f"https://example{i}.com", domain=f"example{i}.com")],
                citations=[],
                response_time_ms=1000,
                raw_response={}
            )

        # Get recent interactions
        interactions = test_db.get_recent_interactions(limit=10)

        assert len(interactions) == 3
        assert all("prompt" in i for i in interactions)
        assert all("model" in i for i in interactions)
        assert all("provider" in i for i in interactions)

    def test_save_interaction_new_provider(self, test_db):
        """Test saving interaction creates provider if it doesn't exist."""
        response_id = test_db.save_interaction(
            provider_name="new_provider",
            model="test-model",
            prompt="test",
            response_text="test",
            search_queries=[],
            sources=[],
            citations=[],
            response_time_ms=500,
            raw_response={}
        )

        assert response_id is not None

        # Verify provider was created
        session = test_db.get_session()
        try:
            provider = session.query(Provider).filter_by(name="new_provider").first()
            assert provider is not None
        finally:
            session.close()

    def test_save_interaction_multiple_sources(self, test_db):
        """Test saving interaction with multiple sources."""
        sources = [
            Source(url="https://example1.com", title="Example 1", domain="example1.com"),
            Source(url="https://example2.com", title="Example 2", domain="example2.com"),
            Source(url="https://example3.com", title="Example 3", domain="example3.com"),
        ]

        response_id = test_db.save_interaction(
            provider_name="google",
            model="gemini-3-pro",
            prompt="test",
            response_text="test",
            search_queries=[SearchQuery(query="test")],
            sources=sources,
            citations=[],
            response_time_ms=800,
            raw_response={}
        )

        # Verify all sources were saved
        session = test_db.get_session()
        try:
            response = session.query(Response).filter_by(id=response_id).first()
            total_sources = sum(len(sc.sources) for sc in response.search_calls)
            assert total_sources == 3
        finally:
            session.close()
