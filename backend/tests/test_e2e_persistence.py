"""
End-to-end tests for API persistence.

These tests verify that API calls actually save to the database.
This catches issues that component tests miss because they test
the database layer and API layer separately.
"""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from app.main import app
from app.database import Database, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


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
    from app.database import Base
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
        response = client.post('/v1/interactions/send', json={
            'prompt': 'Test OpenAI prompt for E2E',
            'provider': 'openai',
            'model': 'gpt-5.1'
        })

        # Verify API call succeeded
        assert response.status_code == 200
        data = response.json()
        assert data['provider'] == 'openai'
        assert data['model'] == 'gpt-5.1'
        interaction_id = data.get('interaction_id')
        assert interaction_id is not None

        # Verify saved to database by retrieving it
        get_response = client.get(f'/v1/interactions/{interaction_id}')
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved['prompt'] == 'Test OpenAI prompt for E2E'
        assert retrieved['provider'] == 'openai'
        assert retrieved['model'] == 'gpt-5.1'

    def test_anthropic_api_call_saves_to_database(self, client, test_db_url):
        """Test that calling send_prompt API for Anthropic actually saves to DB."""
        # This is the test that should have caught the bug!
        import os
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not set")

        # Call API
        response = client.post('/v1/interactions/send', json={
            'prompt': 'Test Anthropic prompt for E2E',
            'provider': 'anthropic',
            'model': 'claude-sonnet-4-5-20250929'
        })

        # Verify API call succeeded
        assert response.status_code == 200
        data = response.json()
        assert data['provider'] == 'anthropic'
        assert data['model'] == 'claude-sonnet-4-5-20250929'
        interaction_id = data.get('interaction_id')
        assert interaction_id is not None, "Anthropic interaction should have ID (proving it was saved)"

        # Verify saved to database by retrieving it
        get_response = client.get(f'/v1/interactions/{interaction_id}')
        assert get_response.status_code == 200, "Should be able to retrieve saved Anthropic interaction"
        retrieved = get_response.json()
        assert retrieved['prompt'] == 'Test Anthropic prompt for E2E'
        assert retrieved['provider'] == 'anthropic'
        assert retrieved['model'] == 'claude-sonnet-4-5-20250929'

    def test_google_api_call_saves_to_database(self, client, test_db_url):
        """Test that calling send_prompt API for Google actually saves to DB."""
        import os
        if not os.getenv('GOOGLE_API_KEY'):
            pytest.skip("GOOGLE_API_KEY not set")

        # Call API
        response = client.post('/v1/interactions/send', json={
            'prompt': 'Test Google prompt for E2E',
            'provider': 'google',
            'model': 'gemini-3-pro-preview'
        })

        # Verify API call succeeded
        assert response.status_code == 200
        data = response.json()
        assert data['provider'] == 'google'
        assert data['model'] == 'gemini-3-pro-preview'
        interaction_id = data.get('interaction_id')
        assert interaction_id is not None

        # Verify saved to database by retrieving it
        get_response = client.get(f'/v1/interactions/{interaction_id}')
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved['prompt'] == 'Test Google prompt for E2E'
        assert retrieved['provider'] == 'google'

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
            response = client.post('/v1/interactions/send', json={
                'prompt': f'Test prompt for {provider}',
                'provider': provider,
                'model': model
            })
            assert response.status_code == 200

        # Get recent interactions
        response = client.get('/v1/interactions/recent?limit=50')
        assert response.status_code == 200
        interactions = response.json()

        # Verify all providers are present
        providers_found = {i['provider'] for i in interactions}
        expected_providers = {p[0].capitalize() if p[0] != 'openai' else 'OpenAI' for p in providers_to_test}

        for expected in expected_providers:
            assert expected in providers_found, f"{expected} interactions should be saved and retrieved"


class TestAPIErrors:
    """Test that API errors are handled correctly and don't break persistence."""

    def test_invalid_model_does_not_save(self, client):
        """Test that invalid model requests don't create database entries."""
        response = client.post('/v1/interactions/send', json={
            'prompt': 'Test prompt',
            'provider': 'openai',
            'model': 'invalid-model-12345'
        })

        # Should fail
        assert response.status_code != 200

        # Should not be in recent interactions
        recent = client.get('/v1/interactions/recent')
        interactions = recent.json()
        prompts = [i['prompt'] for i in interactions]
        assert 'Test prompt' not in prompts

    def test_provider_api_error_does_not_save(self, client):
        """Test that provider API errors don't create partial database entries."""
        # This would require mocking the provider to force an error
        # For now, we test with missing API key which should fail
        import os

        # Find a provider without API key
        test_provider = None
        if not os.getenv('OPENAI_API_KEY'):
            test_provider = ('openai', 'gpt-5.1')
        elif not os.getenv('ANTHROPIC_API_KEY'):
            test_provider = ('anthropic', 'claude-sonnet-4-5-20250929')
        elif not os.getenv('GOOGLE_API_KEY'):
            test_provider = ('google', 'gemini-3-pro-preview')

        if not test_provider:
            pytest.skip("All API keys are configured, can't test missing key error")

        provider, model = test_provider
        response = client.post('/v1/interactions/send', json={
            'prompt': 'Test prompt with missing key',
            'provider': provider,
            'model': model
        })

        # Should fail
        assert response.status_code != 200

        # Should not be in recent interactions
        recent = client.get('/v1/interactions/recent')
        interactions = recent.json()
        prompts = [i['prompt'] for i in interactions]
        assert 'Test prompt with missing key' not in prompts
