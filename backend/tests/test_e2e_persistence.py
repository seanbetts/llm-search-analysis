"""
End-to-end tests for API persistence.

These tests verify that API calls actually save to the database.
This catches issues that component tests miss because they test
the database layer and API layer separately.

These tests hit real provider SDKs and require valid API keys plus
network access. To avoid flaky local/CI runs, they are skipped unless
RUN_E2E=1 is set in the environment.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dependencies import get_db
from app.main import app
from app.models.database import Base


RUN_E2E = os.getenv("RUN_E2E") == "1"
pytestmark = pytest.mark.integration


def _recent_prompts(response):
    """Extract prompt strings from /interactions/recent responses."""
    assert response.status_code == 200, f"Unexpected status {response.status_code}"
    payload = response.json()
    interactions = payload.get("items", payload) if isinstance(payload, dict) else payload
    return [item["prompt"] for item in interactions]


@pytest.fixture
def test_db_url():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name

    yield f'sqlite:///{db_path}'

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def client(test_db_url):
    """Create test client with temporary database."""
    # Override database dependency
    engine = create_engine(test_db_url)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Override get_db dependency
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


@pytest.mark.skipif(
    not RUN_E2E,
    reason="Set RUN_E2E=1 with provider API keys to exercise real persistence tests.",
)
class TestAPIPersistence:
    """Test that API calls actually persist to database."""

    def test_openai_api_call_saves_to_database(self, client, test_db_url):
        """Test that calling send_prompt API for OpenAI actually saves to DB."""
        # This test will fail if OPENAI_API_KEY is not set
        # Skip if not available
        import os
        if not os.getenv('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not set")

        # Call API
        response = client.post('/api/v1/interactions/send', json={
            'prompt': 'Test OpenAI prompt for E2E',
            'provider': 'openai',
            'model': 'gpt-5.1'
        })

        # Verify API call succeeded
        assert response.status_code == 200
        data = response.json()
        assert data['provider'] == 'OpenAI'  # API returns display name
        assert data['model'] == 'gpt-5.1'
        interaction_id = data.get('interaction_id')
        assert interaction_id is not None

        # Verify saved to database by retrieving it
        get_response = client.get(f'/api/v1/interactions/{interaction_id}')
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved['prompt'] == 'Test OpenAI prompt for E2E'
        assert retrieved['provider'] == 'OpenAI'  # API returns display name
        assert retrieved['model'] == 'gpt-5.1'

    def test_anthropic_api_call_saves_to_database(self, client, test_db_url):
        """Test that calling send_prompt API for Anthropic actually saves to DB."""
        # This is the test that should have caught the bug!
        import os
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        # Call API
        response = client.post('/api/v1/interactions/send', json={
            'prompt': 'Test Anthropic prompt for E2E',
            'provider': 'anthropic',
            'model': 'claude-sonnet-4-5-20250929'
        })

        # Verify API call succeeded
        assert response.status_code == 200
        data = response.json()
        assert data['provider'] == 'Anthropic'  # API returns display name
        assert data['model'] == 'claude-sonnet-4-5-20250929'
        interaction_id = data.get('interaction_id')
        assert interaction_id is not None, "Anthropic interaction should have ID (proving it was saved)"

        # Verify saved to database by retrieving it
        get_response = client.get(f'/api/v1/interactions/{interaction_id}')
        assert get_response.status_code == 200, "Should be able to retrieve saved Anthropic interaction"
        retrieved = get_response.json()
        assert retrieved['prompt'] == 'Test Anthropic prompt for E2E'
        assert retrieved['provider'] == 'Anthropic'  # API returns display name
        assert retrieved['model'] == 'claude-sonnet-4-5-20250929'

    def test_google_api_call_saves_to_database(self, client, test_db_url):
        """Test that calling send_prompt API for Google actually saves to DB."""
        import os
        if not os.getenv('GOOGLE_API_KEY'):
            pytest.skip("GOOGLE_API_KEY not set")

        # Call API
        response = client.post('/api/v1/interactions/send', json={
            'prompt': 'Test Google prompt for E2E',
            'provider': 'google',
            'model': 'gemini-3-pro-preview'
        })

        # Verify API call succeeded
        assert response.status_code == 200
        data = response.json()
        assert data['provider'] == 'Google'  # API returns display name
        assert data['model'] == 'gemini-3-pro-preview'
        interaction_id = data.get('interaction_id')
        assert interaction_id is not None

        # Verify saved to database by retrieving it
        get_response = client.get(f'/api/v1/interactions/{interaction_id}')
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved['prompt'] == 'Test Google prompt for E2E'
        assert retrieved['provider'] == 'Google'  # API returns display name

    def test_recent_interactions_includes_all_providers(self, client, test_db_url):
        """Test that recent interactions returns data from all providers."""
        import os

        providers_to_test = []
        if os.getenv('OPENAI_API_KEY'):
            providers_to_test.append(('openai', 'gpt-5.1'))
        if os.getenv('ANTHROPIC_API_KEY'):
            providers_to_test.append(('anthropic', 'claude-sonnet-4-5-20250929'))
        if os.getenv('GOOGLE_API_KEY'):
            providers_to_test.append(('google', 'gemini-3-pro-preview'))

        if not providers_to_test:
            pytest.skip("No API keys configured")

        # Send prompts to each provider
        for provider, model in providers_to_test:
            response = client.post('/api/v1/interactions/send', json={
                'prompt': f'Test prompt for {provider}',
                'provider': provider,
                'model': model
            })
            assert response.status_code == 200

        # Get recent interactions
        response = client.get('/api/v1/interactions/recent?page_size=50')
        assert response.status_code == 200
        payload = response.json()
        interactions = payload.get("items", payload)

        # Verify all providers are present
        providers_found = {i['provider'] for i in interactions}
        expected_providers = {p[0].capitalize() if p[0] != 'openai' else 'OpenAI' for p in providers_to_test}

        for expected in expected_providers:
            assert expected in providers_found, f"{expected} interactions should be saved and retrieved"


class TestAPIErrors:
    """Test that API errors are handled correctly and don't break persistence."""

    def test_invalid_model_does_not_save(self, client):
        """Test that invalid model requests don't create database entries."""
        response = client.post('/api/v1/interactions/send', json={
            'prompt': 'Test prompt',
            'provider': 'openai',
            'model': 'invalid-model-12345'
        })

        # Should fail
        assert response.status_code != 200

        # Should not be in recent interactions
        recent = client.get('/api/v1/interactions/recent')
        prompts = _recent_prompts(recent)
        assert 'Test prompt' not in prompts

    def test_provider_api_error_does_not_save(self, client):
        """Test that provider API errors don't create partial database entries."""
        from unittest.mock import patch, Mock
        from app.core.exceptions import APIException

        # Mock the OpenAI provider to raise an API error
        with patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt') as mock_send_prompt:
            # Force an API error
            mock_send_prompt.side_effect = APIException(
                message="API request failed",
                error_code="PROVIDER_API_ERROR",
                status_code=500,
                details={"error": "Simulated provider API error"}
            )

            # Attempt to send prompt
            response = client.post('/api/v1/interactions/send', json={
                'prompt': 'Test prompt that will fail',
                'provider': 'openai',
                'model': 'gpt-5.1'
            })

            # Should return error status
            assert response.status_code >= 400
            data = response.json()
            assert 'error' in data

            # Verify no partial database entry was created
            recent = client.get('/api/v1/interactions/recent')
            prompts = _recent_prompts(recent)
            assert 'Test prompt that will fail' not in prompts
