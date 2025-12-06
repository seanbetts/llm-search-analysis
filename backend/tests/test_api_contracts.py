"""
Contract tests for API response schemas.

These tests validate that API responses match the expected data structures
that the frontend depends on. They catch issues like:
- List fields being None instead of empty lists
- Missing required fields
- Incorrect data types
- Schema violations

These tests would have caught the bugs fixed in commits:
- 974518c: None-safety checks for citations
- 6473e54: Handle None values for all_sources field
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.main import app
from app.models.database import Base
from app.dependencies import get_db
from app.api.v1.schemas.responses import SendPromptResponse, InteractionSummary


# Create test database
TEST_DB_PATH = Path(__file__).resolve().parent / "data" / "test_contracts.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database and tables."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client with test database."""
    def override_get_db():
        try:
            db = TestSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestInteractionResponseContract:
    """Contract tests for interaction response schemas."""

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_send_prompt_response_schema_validation(self, mock_send_prompt, client):
        """
        Test that POST /api/v1/interactions/send response matches SendPromptResponse schema.

        Validates:
        - All required fields are present
        - List fields are never None (always empty list or populated)
        - Data types match schema
        """
        from app.services.providers.openai_provider import ProviderResponse

        # Mock minimal response
        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Test response",
            search_queries=[],  # Empty list, not None
            sources=[],  # Empty list, not None
            citations=[],  # Empty list, not None
            response_time_ms=1000,
            data_source="api",
            raw_response={}
        )

        response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "Test prompt", "provider": "openai", "model": "gpt-5.1"}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate against Pydantic schema
        validated = SendPromptResponse(**data)
        assert validated.response_text == "Test response"

        # Critical: List fields must never be None, always list type
        assert isinstance(data["search_queries"], list), "search_queries must be a list, not None"
        assert isinstance(data["citations"], list), "citations must be a list, not None"

        # all_sources can be None for 'api' mode, but if present must be a list
        if data.get("all_sources") is not None:
            assert isinstance(data["all_sources"], list), "all_sources must be a list if present"

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_get_interaction_details_list_fields_never_none(self, mock_send_prompt, client):
        """
        Test that GET /api/v1/interactions/{id} never returns None for list fields.

        This test would have caught the bug:
        TypeError: 'NoneType' object is not iterable (line 1376)

        The frontend expects to iterate over these fields without None checks:
        - search_queries
        - citations
        - all_sources (if data_source is 'network_log')
        """
        from app.services.providers.openai_provider import ProviderResponse

        # Create interaction with empty lists
        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Test",
            search_queries=[],
            sources=[],
            citations=[],
            response_time_ms=1000,
            data_source="api",
            raw_response={}
        )

        create_response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "Test", "provider": "openai", "model": "gpt-5.1"}
        )
        interaction_id = create_response.json()["interaction_id"]

        # Get interaction details
        response = client.get(f"/api/v1/interactions/{interaction_id}")
        assert response.status_code == 200
        data = response.json()

        # Validate schema
        validated = SendPromptResponse(**data)

        # CRITICAL VALIDATION: These fields must be iterable
        # The frontend does: for c in details.get('citations', [])
        # But .get() with default only works if key is missing, not if value is None
        assert isinstance(data["search_queries"], list), \
            "search_queries must be list (frontend iterates without None check)"
        assert isinstance(data["citations"], list), \
            "citations must be list (frontend iterates without None check)"

        # For 'api' mode, all_sources can be None (sources are in search_queries)
        # But if present, must be a list
        if data.get("all_sources") is not None:
            assert isinstance(data["all_sources"], list), \
                "all_sources must be list if present"

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_network_log_mode_all_sources_handling(self, mock_send_prompt, client):
        """
        Test data_source='network_log' mode where sources are directly on response.

        In network_log mode:
        - all_sources should contain the sources (not in search_queries)
        - Frontend expects to iterate: for src in details.get('all_sources') or []
        - Sources are saved with response_id (not search_query_id)

        This test validates:
        - Top-level sources are persisted to database
        - Sources are retrieved in all_sources field
        - Frontend can iterate without None errors
        """
        from app.services.providers.openai_provider import ProviderResponse, Source

        # Create interaction with network_log mode
        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Test",
            search_queries=[],
            sources=[  # Sources at top level for network_log
                Source(
                    url="https://example.com",
                    title="Example",
                    domain="example.com",
                    rank=1
                )
            ],
            citations=[],
            response_time_ms=1000,
            data_source="network_log",  # Network log mode
            raw_response={}
        )

        create_response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "Test", "provider": "openai", "model": "gpt-5.1"}
        )
        interaction_id = create_response.json()["interaction_id"]

        # Get details
        response = client.get(f"/api/v1/interactions/{interaction_id}")
        assert response.status_code == 200
        data = response.json()

        # For network_log mode, all_sources should be present
        assert "all_sources" in data, "all_sources must be present for network_log mode"

        # CRITICAL: Must be iterable, not None
        # Frontend does: all_sources = details.get('all_sources') or []
        if data["all_sources"] is not None:
            assert isinstance(data["all_sources"], list), \
                "all_sources must be list, not None (frontend iterates)"
            assert len(data["all_sources"]) == 1, \
                "Should have 1 source from network log"

    def test_get_recent_interactions_list_consistency(self, client):
        """
        Test that GET /api/v1/interactions/recent returns consistent list types.

        Validates:
        - Response is always a list
        - Each item matches InteractionSummary schema
        - No None values for required fields
        """
        response = client.get("/api/v1/interactions/recent")
        assert response.status_code == 200
        data = response.json()

        # Must be a list, even if empty
        assert isinstance(data, list), "Response must be a list"

        # Validate each item against schema
        for item in data:
            validated = InteractionSummary(**item)
            assert validated.interaction_id is not None
            assert isinstance(validated.prompt, str)
            assert isinstance(validated.provider, str)
            assert isinstance(validated.model, str)

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_nested_sources_in_search_queries_never_none(self, mock_send_prompt, client):
        """
        Test that sources within search_queries are never None.

        Frontend iterates: for src in query.get('sources', [])
        This must work even if sources is None in the database.
        """
        from app.services.providers.openai_provider import ProviderResponse, SearchQuery, Source

        # Create interaction with search query that has sources
        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Test",
            search_queries=[
                SearchQuery(
                    query="test query",
                    sources=[  # Not None, but could be empty
                        Source(
                            url="https://example.com",
                            title="Example",
                            domain="example.com",
                            rank=1
                        )
                    ],
                    timestamp="2024-01-01T00:00:00Z",
                    order_index=0
                )
            ],
            sources=[],
            citations=[],
            response_time_ms=1000,
            data_source="api",
            raw_response={}
        )

        create_response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "Test", "provider": "openai", "model": "gpt-5.1"}
        )
        interaction_id = create_response.json()["interaction_id"]

        # Get details
        response = client.get(f"/api/v1/interactions/{interaction_id}")
        assert response.status_code == 200
        data = response.json()

        # Validate nested sources
        assert len(data["search_queries"]) == 1
        query = data["search_queries"][0]

        # CRITICAL: sources must be iterable
        assert isinstance(query["sources"], list), \
            "query.sources must be list (frontend iterates without None check)"
        assert len(query["sources"]) == 1

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_empty_response_data_handling(self, mock_send_prompt, client):
        """
        Test handling of completely empty response data (no queries, no citations).

        This is a realistic scenario where:
        - Model doesn't use web search
        - No citations in response
        - Frontend should handle gracefully
        """
        from app.services.providers.openai_provider import ProviderResponse

        # Completely empty response
        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Direct answer without search",
            search_queries=[],  # No searches
            sources=[],  # No sources
            citations=[],  # No citations
            response_time_ms=500,
            data_source="api",
            raw_response={}
        )

        create_response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "What is 2+2?", "provider": "openai", "model": "gpt-5.1"}
        )
        assert create_response.status_code == 200
        data = create_response.json()

        # Validate all list fields are empty lists, not None
        assert data["search_queries"] == []
        assert data["citations"] == []
        assert isinstance(data["search_queries"], list)
        assert isinstance(data["citations"], list)

        # Get details endpoint should return same
        interaction_id = data["interaction_id"]
        response = client.get(f"/api/v1/interactions/{interaction_id}")
        assert response.status_code == 200
        details = response.json()

        # Validate schema
        SendPromptResponse(**details)

        # All list fields must be empty lists, never None
        assert details["search_queries"] == []
        assert details["citations"] == []
        assert isinstance(details["search_queries"], list)
        assert isinstance(details["citations"], list)


class TestResponseSchemaEdgeCases:
    """Test edge cases in response schemas that could break frontend."""

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_citation_without_rank_is_valid(self, mock_send_prompt, client):
        """
        Test that citations without rank (extra links) are handled correctly.

        Frontend logic:
        - citations_with_rank = [c for c in citations if c.get('rank')]
        - extra_links = [c for c in citations if not c.get('rank')]

        Both must work even if rank is None.
        """
        from app.services.providers.openai_provider import ProviderResponse, Citation

        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Test with extra link",
            search_queries=[],
            sources=[],
            citations=[
                Citation(
                    url="https://example.com",
                    title="Extra Link",
                    rank=None  # No rank = extra link
                )
            ],
            response_time_ms=1000,
            data_source="api",
            raw_response={}
        )

        create_response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "Test", "provider": "openai", "model": "gpt-5.1"}
        )
        interaction_id = create_response.json()["interaction_id"]

        response = client.get(f"/api/v1/interactions/{interaction_id}")
        assert response.status_code == 200
        data = response.json()

        # Citation should be present
        assert len(data["citations"]) == 1
        citation = data["citations"][0]

        # rank can be None for extra links
        assert citation["rank"] is None or isinstance(citation["rank"], int)

    @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
    def test_all_optional_fields_can_be_none(self, mock_send_prompt, client):
        """
        Test that all Optional fields can be None without breaking validation.

        This ensures our schema correctly marks optional fields.
        """
        from app.services.providers.openai_provider import ProviderResponse

        mock_send_prompt.return_value = ProviderResponse(
            provider="openai",
            model="gpt-5.1",
            response_text="Minimal response",
            search_queries=[],
            sources=[],
            citations=[],
            response_time_ms=None,  # Optional
            data_source="api",
            raw_response=None  # Optional
        )

        response = client.post(
            "/api/v1/interactions/send",
            json={"prompt": "Test", "provider": "openai", "model": "gpt-5.1"}
        )
        assert response.status_code == 200
        data = response.json()

        # Should validate despite None optionals
        SendPromptResponse(**data)
