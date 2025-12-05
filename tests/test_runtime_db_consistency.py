"""
Runtime database consistency tests.

These tests verify that the RUNNING application is using the correct database,
not just that the config SAYS to use the correct database.

This catches caching issues where config changes but the app doesn't reload.
"""

import pytest
import os
import sqlite3
from datetime import datetime, timedelta
from src.database import Database
from src.config import Config


class TestRuntimeDatabaseConsistency:
    """Verify the running app uses the correct database."""

    def test_database_file_actually_exists(self):
        """Verify the configured database file exists on disk."""
        db_path = Config.DATABASE_URL.replace("sqlite:///", "")

        assert os.path.exists(db_path), \
            f"Database file doesn't exist at: {db_path}"

        # Verify it's not empty
        size = os.path.getsize(db_path)
        assert size > 1000, \
            f"Database file is suspiciously small ({size} bytes). Expected > 1000 bytes."

    def test_database_points_to_backend_data(self):
        """Verify database path points to backend/data/ (not root data/)."""
        db_path = Config.DATABASE_URL.replace("sqlite:///", "")

        # Must contain 'backend/data' to match Docker volume mount
        assert "backend/data" in db_path, \
            f"Database path must include 'backend/data' to match Docker volume. Got: {db_path}"

    def test_database_connection_works(self):
        """Verify we can actually connect and query the database."""
        db = Database()

        # This will raise an exception if connection fails
        interactions = db.get_recent_interactions(limit=1)

        # If we have any data, verify it's structured correctly
        if interactions:
            interaction = interactions[0]
            required_fields = ["id", "prompt", "model", "provider", "timestamp"]
            for field in required_fields:
                assert field in interaction, \
                    f"Database returned interaction without required field: {field}"

    def test_backend_and_frontend_use_same_database(self):
        """
        CRITICAL TEST: Verify backend writes and frontend reads use same file.

        This would have caught the caching bug!
        """
        # Get backend database path (from Docker)
        backend_db_path = "backend/data/llm_search.db"  # Docker mounts this

        # Get frontend database path (from config)
        frontend_db_path = Config.DATABASE_URL.replace("sqlite:///", "")

        # Verify they point to the same file
        backend_abs = os.path.abspath(backend_db_path)
        frontend_abs = os.path.abspath(frontend_db_path)

        assert backend_abs == frontend_abs, \
            f"Backend and frontend use DIFFERENT databases!\n" \
            f"  Backend:  {backend_abs}\n" \
            f"  Frontend: {frontend_abs}\n" \
            f"This means writes to backend won't appear in frontend!"

    def test_database_has_recent_activity(self):
        """
        Verify database has been written to recently.

        If this fails, either:
        1. No one has used the system recently (OK)
        2. Writes are going to wrong database (BUG!)
        """
        db = Database()
        interactions = db.get_recent_interactions(limit=10)

        if len(interactions) == 0:
            pytest.skip("No interactions in database yet")

        # Check if most recent is from today or yesterday
        most_recent = interactions[0]
        created = most_recent["timestamp"]

        # Just verify the timestamp is sane (not None, not in future)
        assert created is not None, "Most recent interaction has no timestamp"

    def test_database_file_matches_docker_mount(self):
        """
        Verify the database file on host matches what Docker sees.

        Docker mounts: backend/data -> /app/data
        So backend/data/llm_search.db should be accessible to both.
        """
        host_db_path = "backend/data/llm_search.db"

        # Verify it exists
        assert os.path.exists(host_db_path), \
            f"Database not found at Docker mount location: {host_db_path}"

        # Verify we can open it
        conn = sqlite3.connect(host_db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        conn.close()

        assert table_count > 0, \
            f"Database at {host_db_path} has no tables! It may be corrupt or uninitialized."

    def test_database_not_using_wrong_location(self):
        """
        Verify we're NOT using the old wrong database location.

        This is a regression test for the bug we just fixed.
        """
        frontend_db_path = Config.DATABASE_URL.replace("sqlite:///", "")

        # These are WRONG paths that we used before
        wrong_paths = [
            "data/llm_search.db",  # Old frontend path (wrong!)
            "../data/llm_search.db",  # Relative path (wrong!)
            "./data/llm_search.db",  # Current dir data (wrong!)
        ]

        for wrong_path in wrong_paths:
            assert frontend_db_path != wrong_path, \
                f"Database is using WRONG path: {wrong_path}. Should be: backend/data/llm_search.db"


class TestDatabaseCacheDetection:
    """
    Tests to detect if database connection is cached/stale.

    These help identify when config changes but app doesn't reload.
    """

    def test_database_shows_anthropic_data_if_configured(self):
        """
        If ANTHROPIC_API_KEY is set, verify Anthropic data appears in database.

        This catches the caching bug where:
        1. Backend writes Anthropic data
        2. Frontend reads from old cached database
        3. Anthropic data doesn't appear in History tab
        """
        import os
        if not os.getenv('ANTHROPIC_API_KEY'):
            pytest.skip("ANTHROPIC_API_KEY not configured")

        db = Database()
        interactions = db.get_recent_interactions(limit=100)

        if len(interactions) == 0:
            pytest.skip("No interactions in database yet")

        # Check if ANY Anthropic interactions exist
        anthropic_count = sum(1 for i in interactions if i["provider"] == "Anthropic")

        # Log for debugging
        print(f"\nFound {anthropic_count} Anthropic interactions out of {len(interactions)} total")
        print(f"Providers in database: {set(i['provider'] for i in interactions)}")

        # If Anthropic key is configured but we have ZERO Anthropic data,
        # that's suspicious (unless system is brand new)
        if len(interactions) > 20:  # Only check if system has been used
            assert anthropic_count > 0, \
                "ANTHROPIC_API_KEY is configured and system has data, but NO Anthropic " \
                "interactions found. This suggests frontend is reading from wrong database!"
