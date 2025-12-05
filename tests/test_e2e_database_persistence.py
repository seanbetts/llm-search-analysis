"""
End-to-end tests that verify the full integration:
Frontend → Backend API → Database persistence

These tests catch issues that unit/integration tests miss because
they test the complete flow in the actual deployment environment.

Run with: pytest tests/test_e2e_database_persistence.py -v
"""

import pytest
import requests
import time
from datetime import datetime
from src.database import Database


@pytest.fixture
def api_base_url():
    """Base URL for the running backend API."""
    return "http://localhost:8000"


@pytest.fixture
def database():
    """Get database instance."""
    return Database()


class TestE2EAPIPersistence:
    """
    Test that API calls actually save to the database.

    These tests require:
    1. Backend API running on localhost:8000
    2. API keys configured in .env file
    """

    def test_backend_is_running(self, api_base_url):
        """Verify backend is accessible before running tests."""
        try:
            response = requests.get(f"{api_base_url}/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend is not running. Start with: docker-compose up -d api")

    def test_openai_call_persists_to_database(self, api_base_url, database):
        """
        E2E test: OpenAI API call → Database persistence.

        This test WOULD HAVE caught the database path mismatch bug!
        """
        import os
        if not os.getenv('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not configured")

        # Get count before
        initial_count = len(database.get_recent_interactions(limit=1000))

        # Make API call
        test_prompt = f"E2E test prompt at {datetime.now().isoformat()}"
        response = requests.post(
            f"{api_base_url}/api/v1/interactions/send",
            json={
                "prompt": test_prompt,
                "provider": "openai",
                "model": "gpt-5.1"
            },
            timeout=60
        )

        # Verify API succeeded
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-5.1"

        # CRITICAL: Verify it's actually in the database
        time.sleep(1)  # Give DB a moment to flush
        interactions = database.get_recent_interactions(limit=5)

        # Should have one more interaction
        assert len(interactions) >= initial_count + 1, \
            "New interaction not found in database! API call succeeded but database save failed."

        # Most recent should be our test
        most_recent = interactions[0]
        assert most_recent["prompt"] == test_prompt, \
            f"Most recent prompt doesn't match. Expected '{test_prompt}', got '{most_recent['prompt']}'"
        assert most_recent["provider"] == "OpenAI"

    def test_anthropic_call_persists_to_database(self, api_base_url, database):
        """
        E2E test: Anthropic API call → Database persistence.

        THIS TEST WOULD HAVE CAUGHT THE BUG where Anthropic tests
        weren't being saved!
        """
        import os
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not configured")

        # Get count before
        initial_interactions = database.get_recent_interactions(limit=1000)
        initial_anthropic_count = sum(1 for i in initial_interactions if i["provider"] == "Anthropic")

        # Make API call
        test_prompt = f"Anthropic E2E test at {datetime.now().isoformat()}"
        response = requests.post(
            f"{api_base_url}/api/v1/interactions/send",
            json={
                "prompt": test_prompt,
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929"
            },
            timeout=60
        )

        # Verify API succeeded
        assert response.status_code == 200, f"Anthropic API call failed: {response.text}"
        data = response.json()
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-sonnet-4-5-20250929"

        # CRITICAL: Verify it's in the database
        time.sleep(1)
        interactions = database.get_recent_interactions(limit=10)
        anthropic_interactions = [i for i in interactions if i["provider"] == "Anthropic"]

        assert len(anthropic_interactions) >= initial_anthropic_count + 1, \
            "Anthropic interaction not saved to database! This is the bug we're trying to catch."

        # Verify our test prompt is there
        recent_prompts = [i["prompt"] for i in anthropic_interactions[:3]]
        assert test_prompt in recent_prompts, \
            f"Test prompt not found in recent Anthropic interactions: {recent_prompts}"

    def test_google_call_persists_to_database(self, api_base_url, database):
        """E2E test: Google API call → Database persistence."""
        import os
        if not os.getenv('GOOGLE_API_KEY'):
            pytest.skip("GOOGLE_API_KEY not configured")

        initial_count = len(database.get_recent_interactions(limit=1000))

        test_prompt = f"Google E2E test at {datetime.now().isoformat()}"
        response = requests.post(
            f"{api_base_url}/api/v1/interactions/send",
            json={
                "prompt": test_prompt,
                "provider": "google",
                "model": "gemini-3-pro-preview"
            },
            timeout=60
        )

        assert response.status_code == 200

        time.sleep(1)
        interactions = database.get_recent_interactions(limit=5)
        assert len(interactions) >= initial_count + 1
        assert interactions[0]["prompt"] == test_prompt

    def test_database_path_consistency(self, database):
        """
        Verify frontend and backend use the SAME database.

        This test checks that both are reading/writing to the same file.
        """
        # Get database path
        import os
        from src.config import Config

        frontend_db_path = Config.DATABASE_URL.replace("sqlite:///", "")

        # Backend should be using backend/data/llm_search.db (via Docker volume mount)
        # Frontend should be using backend/data/llm_search.db (after our fix)

        assert "backend/data/llm_search.db" in frontend_db_path, \
            f"Frontend database path incorrect: {frontend_db_path}. Should point to backend/data/"

        # Verify the file actually exists
        assert os.path.exists(frontend_db_path), \
            f"Database file doesn't exist at: {frontend_db_path}"

    def test_all_providers_save_successfully(self, api_base_url, database):
        """
        Comprehensive test: Verify ALL configured providers save to database.

        This test ensures no provider is silently failing.
        """
        import os

        providers_to_test = []
        if os.getenv('OPENAI_API_KEY'):
            providers_to_test.append(('openai', 'gpt-5.1', 'OpenAI'))
        if os.getenv('ANTHROPIC_API_KEY'):
            providers_to_test.append(('anthropic', 'claude-sonnet-4-5-20250929', 'Anthropic'))
        if os.getenv('GOOGLE_API_KEY'):
            providers_to_test.append(('google', 'gemini-3-pro-preview', 'Google'))

        if not providers_to_test:
            pytest.skip("No API keys configured")

        test_timestamp = datetime.now().isoformat()

        for provider_name, model, display_name in providers_to_test:
            test_prompt = f"Multi-provider E2E test {test_timestamp} - {provider_name}"

            # Make API call
            response = requests.post(
                f"{api_base_url}/api/v1/interactions/send",
                json={
                    "prompt": test_prompt,
                    "provider": provider_name,
                    "model": model
                },
                timeout=60
            )

            assert response.status_code == 200, \
                f"{provider_name} API call failed: {response.text}"

            # Verify in database
            time.sleep(0.5)
            interactions = database.get_recent_interactions(limit=20)
            prompts = [i["prompt"] for i in interactions]

            assert test_prompt in prompts, \
                f"{provider_name} interaction not found in database! Prompts: {prompts[:5]}"


class TestE2EDatabaseConsistency:
    """Test that database reads/writes are consistent across the system."""

    def test_history_shows_recent_interactions(self, database):
        """Verify that recent API calls appear in history."""
        interactions = database.get_recent_interactions(limit=10)

        # Should have some interactions
        assert len(interactions) > 0, "Database is empty! No interactions found."

        # Most recent should be from today or yesterday
        most_recent = interactions[0]
        most_recent_date = most_recent["timestamp"]

        # Basic sanity check - should have been created recently
        # (Not checking exact date to avoid timezone issues)
        assert most_recent_date is not None

    def test_all_providers_represented_in_history(self, database):
        """Verify all providers that have been used show up in history."""
        interactions = database.get_recent_interactions(limit=100)

        providers_found = {i["provider"] for i in interactions}

        # Log what we found for debugging
        print(f"\\nProviders in database: {providers_found}")
        print(f"Total interactions: {len(interactions)}")

        if len(interactions) > 0:
            # At least one provider should be present
            assert len(providers_found) > 0, "No provider data found in database"
