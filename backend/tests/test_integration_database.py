"""
Integration tests with realistic database fixtures including edge cases.

These tests use production-like data scenarios including:
- NULL foreign key relationships
- Orphaned records
- Missing relationships
- Empty collections
- Mixed data from different sources

These tests would have caught:
- Eager loading crashes (Response.response_sources with NULL relationships)
- N+1 query problems
- NULL constraint violations
- Cascading delete issues
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.database import (
    Base,
    InteractionModel,
    Provider,
    QuerySource,
    Response,
    ResponseSource,
    SearchQuery,
)
from app.repositories.interaction_repository import InteractionRepository

# Create test database
TEST_DB_PATH = Path(__file__).resolve().parent / "data" / "test_integration.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database with tables."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Create database session."""
    session = TestSessionLocal()
    yield session
    session.close()


@pytest.fixture
def repository(db_session):
    """Create repository with test session."""
    return InteractionRepository(db_session)


class TestRealisticDataScenarios:
    """Test with realistic, messy database fixtures."""

    def test_eager_loading_with_null_relationships(self, db_session, repository):
        """
        Test eager loading when relationships have NULL values.

        This would have caught prior crashes when response-level sources
        weren't eager loaded correctly alongside query-level sources.
        """
        # Create provider and session
        provider = Provider(name="openai", display_name="OpenAI", is_active=True)
        db_session.add(provider)
        db_session.flush()

        interaction = InteractionModel(
            provider_id=provider.id,
            model_name="gpt-4o",
            prompt_text="Test prompt",
            data_source="api",
        )
        db_session.add(interaction)
        db_session.flush()

        response = Response(
            interaction_id=interaction.id,
            response_text="Test response",
            response_time_ms=1000,
            raw_response_json={},
            data_source="api",
        )
        db_session.add(response)
        db_session.flush()

        # Create network-log source linked directly to response
        network_source = ResponseSource(
            response_id=response.id,
            url="https://network.com",
            title="Network Source",
        )
        db_session.add(network_source)

        # Create query with associated sources
        search_query = SearchQuery(
            response_id=response.id,
            search_query="test query",
            order_index=0,
        )
        db_session.add(search_query)
        db_session.flush()

        query_source = QuerySource(
            search_query_id=search_query.id,
            url="https://api.com/result",
            title="API Source",
        )
        db_session.add(query_source)

        db_session.commit()

        # This should not crash even with NULL relationships
        # The bug was: eager loading Response.sources would crash
        result = repository.get_by_id(response.id)

        assert result is not None
        assert result.id == response.id
        # Should only load response-level sources in response_sources relationship
        assert len(result.response_sources) == 1
        assert result.response_sources[0].url == "https://network.com"
        # Query-level sources should be accessible via search query relationship
        assert len(result.search_queries[0].sources) == 1

    def test_get_recent_with_missing_relationships(self, db_session, repository):
        """
        Test get_recent with incomplete relationship chains.

        Simulates data migration or corruption where relationships are broken.
        """
        # Create provider
        provider = Provider(name="openai", display_name="OpenAI", is_active=True)
        db_session.add(provider)
        db_session.flush()

        interaction = InteractionModel(
            provider_id=provider.id,
            model_name="gpt-4o",
            prompt_text="Test prompt",
            data_source="api",
        )
        db_session.add(interaction)
        db_session.flush()

        good_response = Response(
            interaction_id=interaction.id,
            response_text="Good response",
            response_time_ms=1000,
            raw_response_json={},
            data_source="api",
        )
        db_session.add(good_response)

        db_session.commit()

        # Attempting to create an orphaned response should now fail fast
        with pytest.raises(IntegrityError):
            bad_response = Response(
                interaction_id=None,
                response_text="Orphaned response",
                response_time_ms=1000,
                raw_response_json={},
                data_source="api",
            )
            db_session.add(bad_response)
            db_session.commit()
        db_session.rollback()

        # Repository should still return the valid response without crashing.
        results, total = repository.get_recent(page_size=10)

        assert total == 1
        assert any(result.id == good_response.id for result in results)

    def test_search_query_with_no_sources(self, db_session, repository):
        """
        Test search queries that have no sources.

        Can happen if search returned no results or sources weren't captured.
        """
        # Setup basic relationships
        provider = Provider(name="openai", display_name="OpenAI", is_active=True)
        db_session.add(provider)
        db_session.flush()

        interaction = InteractionModel(
            provider_id=provider.id,
            model_name="gpt-4o",
            prompt_text="Test",
            data_source="api",
        )
        db_session.add(interaction)
        db_session.flush()

        response = Response(
            interaction_id=interaction.id,
            response_text="Response",
            response_time_ms=1000,
            raw_response_json={},
            data_source="api",
        )
        db_session.add(response)
        db_session.flush()

        # Create search query with NO sources
        empty_query = SearchQuery(
            response_id=response.id,
            search_query="query with no results",
            order_index=0,
        )
        db_session.add(empty_query)

        db_session.commit()

        # Should handle empty sources collection
        result = repository.get_by_id(response.id)

        assert result is not None
        assert len(result.search_queries) == 1
        assert len(result.search_queries[0].sources) == 0  # Empty, not NULL

    def test_response_with_no_citations(self, db_session, repository):
        """
        Test responses that have no citations/sources_used.

        Common when model doesn't cite sources or generates answer without search.
        """
        response_id = repository.save(
            prompt_text="Simple question",
            provider_name="openai",
            model_name="gpt-4o",
            response_text="Simple answer",
            response_time_ms=500,
            search_queries=[],  # No searches
            sources_used=[],  # No citations
            raw_response={},
            data_source="api",
        )

        result = repository.get_by_id(response_id)

        assert result is not None
        assert result.response_text == "Simple answer"
        assert len(result.search_queries) == 0
        assert len(result.sources_used) == 0
        # Should not crash when accessing empty collections

    def test_mixed_api_and_network_log_data(self, db_session, repository):
        """
        Test database with mix of API and network_log mode data.

        API mode: sources in search_queries
        Network_log mode: sources directly on response
        """
        # Save API mode interaction
        api_id = repository.save(
            prompt_text="API prompt",
            provider_name="openai",
            model_name="gpt-4o",
            response_text="API response",
            response_time_ms=1000,
            search_queries=[
                {
                    "query": "test query",
                    "sources": [
                        {
                            "url": "https://api-source.com",
                            "title": "API Source",
                            "rank": 1,
                        }
                    ],
                    "order_index": 0,
                }
            ],
            sources_used=[
                {
                    "url": "https://api-source.com",
                    "title": "API Source",
                    "rank": 1,
                }
            ],
            raw_response={},
            data_source="api",
        )

        # Save network_log mode interaction
        network_id = repository.save(
            prompt_text="Network prompt",
            provider_name="openai",
            model_name="gpt-4o",
            response_text="Network response",
            response_time_ms=1000,
            search_queries=[],  # No queries in network_log
            sources_used=[],
            raw_response={},
            data_source="network_log",
            sources=[  # Top-level sources
                {
                    "url": "https://network-source.com",
                    "title": "Network Source",
                    "rank": 1,
                }
            ],
        )

        # Retrieve both
        results, total = repository.get_recent(page_size=10)

        assert len(results) == 2

        # Verify API mode response
        api_response = repository.get_by_id(api_id)
        assert api_response.data_source == "api"
        assert len(api_response.search_queries) == 1
        assert len(api_response.search_queries[0].sources) == 1

        # Verify network_log mode response
        network_response = repository.get_by_id(network_id)
        assert network_response.data_source == "network_log"
        assert len(network_response.response_sources) == 1
        assert network_response.response_sources[0].response_id == network_response.id

    def test_concurrent_query_patterns(self, db_session, repository):
        """
        Test query patterns that might cause N+1 queries or loading issues.

        Validates that eager loading is configured correctly.
        """
        # Create multiple responses with full relationship chains
        for i in range(5):
            repository.save(
                prompt_text=f"Prompt {i}",
                provider_name="openai",
                model_name="gpt-4o",
                response_text=f"Response {i}",
                response_time_ms=1000,
                search_queries=[
                    {
                        "query": f"query {i}",
                        "sources": [
                            {"url": f"https://source{i}.com", "title": f"Source {i}", "rank": 1}
                        ],
                        "order_index": 0,
                    }
                ],
                sources_used=[
                    {"url": f"https://source{i}.com", "title": f"Source {i}", "rank": 1}
                ],
                raw_response={},
                data_source="api",
            )

        # Get all recent - should use eager loading, not N+1 queries
        results, total = repository.get_recent(page_size=10)

        assert len(results) == 5

        # Access all relationships - should be already loaded
        for result in results:
            assert result.interaction is not None
            assert result.interaction.provider is not None
            assert len(result.search_queries) > 0
            for query in result.search_queries:
                # Sources should be loaded
                assert query.sources is not None  # Should be list, even if empty

    def test_data_migration_scenario(self, db_session, repository):
        """
        Test data that might exist after migration or import.

        Includes:
        - Missing optional fields
        - NULL values where they shouldn't be
        - Legacy data structure
        """
        # Create provider
        provider = Provider(name="imported", display_name="Imported", is_active=True)
        db_session.add(provider)
        db_session.flush()

        interaction = InteractionModel(
            provider_id=provider.id,
            model_name="unknown-model",  # Model that doesn't exist anymore
            prompt_text="Migrated prompt",
            data_source="api",
        )
        db_session.add(interaction)
        db_session.flush()

        # Create response with missing optional fields
        response = Response(
            interaction_id=interaction.id,
            response_text="Migrated response",
            response_time_ms=None,  # Missing
            raw_response_json=None,  # Missing
            data_source="api",
            extra_links_count=None,  # Missing
        )
        db_session.add(response)
        db_session.flush()

        # Create source with minimal data
        query = SearchQuery(
            response_id=response.id,
            search_query="migrated query",
            order_index=0,
            internal_ranking_scores=None,
            query_reformulations=None,
        )
        db_session.add(query)
        db_session.flush()

        source = QuerySource(
            search_query_id=query.id,
            url="https://migrated.com",
            title=None,  # Missing
            domain=None,  # Missing
            rank=None,  # Missing
            pub_date=None,  # Missing
            snippet_text=None,
            internal_score=None,
            metadata_json=None,
        )
        db_session.add(source)

        db_session.commit()

        # Should handle all NULL/missing fields gracefully
        result = repository.get_by_id(response.id)

        assert result is not None
        assert result.response_time_ms is None
        assert result.raw_response_json is None
        assert len(result.search_queries) == 1
        assert result.search_queries[0].sources[0].title is None

    def test_delete_with_orphaned_relationships(self, db_session, repository):
        """
        Test deletion when some relationships are orphaned.

        Ensures cascading deletes work even with inconsistent data.
        """
        # Create complete interaction
        response_id = repository.save(
            prompt_text="To be deleted",
            provider_name="openai",
            model_name="gpt-4o",
            response_text="Response to delete",
            response_time_ms=1000,
            search_queries=[
                {
                    "query": "query",
                    "sources": [{"url": "https://source.com", "title": "Source", "rank": 1}],
                    "order_index": 0,
                }
            ],
            sources_used=[{"url": "https://citation.com", "title": "Citation", "rank": 1}],
            raw_response={},
            data_source="api",
        )

        # Manually create orphaned source (simulating data corruption)
        response = db_session.query(Response).filter_by(id=response_id).first()
        orphaned_source = ResponseSource(
            response_id=response.id,
            url="https://orphaned.com",
            title="Orphaned",
        )
        db_session.add(orphaned_source)
        db_session.commit()

        # Delete should work even with orphaned source
        deleted = repository.delete(response_id)

        assert deleted is True
        # Verify everything cleaned up
        assert db_session.query(Response).filter_by(id=response_id).first() is None
        assert db_session.query(ResponseSource).filter_by(url="https://orphaned.com").first() is None

    def test_delete_removes_session_and_provider(self, db_session, repository):
        """
        Deleting the only interaction should clean up session and provider.
        """
        response_id = repository.save(
            prompt_text="Cleanup prompt",
            provider_name="cleanup_provider",
            model_name="gpt-4o",
            response_text="Cleanup response",
            response_time_ms=1000,
            search_queries=[],
            sources_used=[],
            raw_response={},
            data_source="api",
        )

        assert repository.delete(response_id) is True
        assert db_session.query(InteractionModel).count() == 0
        assert db_session.query(Provider).count() == 0

    def test_delete_keeps_provider_with_other_sessions(self, db_session, repository):
        """
        Provider should stay if other sessions still exist.
        """
        first_id = repository.save(
            prompt_text="Prompt 1",
            provider_name="shared_provider",
            model_name="gpt-4o",
            response_text="Response 1",
            response_time_ms=1000,
            search_queries=[],
            sources_used=[],
            raw_response={},
            data_source="api",
        )

        second_id = repository.save(
            prompt_text="Prompt 2",
            provider_name="shared_provider",
            model_name="gpt-4o",
            response_text="Response 2",
            response_time_ms=1000,
            search_queries=[],
            sources_used=[],
            raw_response={},
            data_source="api",
        )

        assert repository.delete(first_id) is True
        assert db_session.query(Provider).filter_by(name="shared_provider").first() is not None

        assert repository.delete(second_id) is True
        assert db_session.query(Provider).filter_by(name="shared_provider").first() is None


class TestEdgeCaseQueries:
    """Test edge cases in query operations."""

    def test_get_recent_with_corrupted_timestamps(self, db_session, repository):
        """Test get_recent when timestamps are NULL or invalid."""
        provider = Provider(name="openai", display_name="OpenAI", is_active=True)
        db_session.add(provider)
        db_session.flush()

        interaction = InteractionModel(
            provider_id=provider.id,
            model_name="gpt-4o",
            prompt_text="Test",
            data_source="api",
        )
        db_session.add(interaction)
        db_session.flush()

        # Response with NULL created_at (shouldn't happen but might in real data)
        response = Response(
            interaction_id=interaction.id,
            response_text="Response",
            response_time_ms=1000,
            raw_response_json={},
            data_source="api",
        )
        # Bypass default timestamp
        response.created_at = None
        db_session.add(response)
        db_session.commit()

        # Should not crash, even with NULL timestamp
        results, total = repository.get_recent(page_size=10)

        # Should still return the response
        assert len(results) >= 1

    def test_filter_by_invalid_data_source(self, db_session, repository):
        """Test filtering by data_source that doesn't exist."""
        # Create normal interaction
        repository.save(
            prompt_text="Test",
            provider_name="openai",
            model_name="gpt-4o",
            response_text="Response",
            response_time_ms=1000,
            search_queries=[],
            sources_used=[],
            raw_response={},
            data_source="api",
        )

        # Filter by non-existent data source
        results, total = repository.get_recent(page_size=10, data_source="nonexistent")

        # Should return empty list, not crash
        assert total == 0
        assert results == []

    def test_extremely_large_limit(self, db_session, repository):
        """Test get_recent with extremely large limit."""
        # Create a few interactions
        for i in range(3):
            repository.save(
                prompt_text=f"Test {i}",
                provider_name="openai",
                model_name="gpt-4o",
                response_text=f"Response {i}",
                response_time_ms=1000,
                search_queries=[],
                sources_used=[],
                raw_response={},
                data_source="api",
            )

        # Request more than exist
        results, total = repository.get_recent(page_size=1000)

        # Should return all 3, not crash or error
        assert total == 3
        assert len(results) == 3
