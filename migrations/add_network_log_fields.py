"""
Database migration: Add network log fields to existing tables.

This migration adds support for storing network log data alongside API data.
Run this script to update an existing database schema.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import Config
sys.path.append(str(Path(__file__).parent.parent))
from src.config import Config


def migrate():
    """Apply migration to add network log fields."""
    db_path = Config.DATABASE_URL.replace('sqlite:///', '')

    print(f"Migrating database at: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add data_source column to responses table
        print("Adding data_source column to responses table...")
        cursor.execute("""
            ALTER TABLE responses
            ADD COLUMN data_source VARCHAR(20) DEFAULT 'api'
        """)

        # Add network log fields to search_queries table
        print("Adding network log fields to search_queries table...")
        cursor.execute("""
            ALTER TABLE search_queries
            ADD COLUMN internal_ranking_scores JSON
        """)
        cursor.execute("""
            ALTER TABLE search_queries
            ADD COLUMN query_reformulations JSON
        """)

        # Add network log fields to sources table
        print("Adding network log fields to sources table...")
        cursor.execute("""
            ALTER TABLE sources
            ADD COLUMN snippet_text TEXT
        """)
        cursor.execute("""
            ALTER TABLE sources
            ADD COLUMN internal_score FLOAT
        """)
        cursor.execute("""
            ALTER TABLE sources
            ADD COLUMN metadata_json JSON
        """)

        # Add network log fields to sources_used table
        print("Adding network log fields to sources_used table...")
        cursor.execute("""
            ALTER TABLE sources_used
            ADD COLUMN snippet_used TEXT
        """)
        cursor.execute("""
            ALTER TABLE sources_used
            ADD COLUMN citation_confidence FLOAT
        """)

        # Create index for filtering by data source
        print("Creating index on data_source...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_source
            ON responses(data_source)
        """)

        conn.commit()
        print("✓ Migration completed successfully!")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠ Columns already exist - migration may have been run previously")
        else:
            print(f"✗ Migration failed: {e}")
            conn.rollback()
            raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
