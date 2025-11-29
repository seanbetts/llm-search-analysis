"""
Migration script to update sources table schema.

Changes:
1. Make search_query_id nullable (for network log sources)
2. Add response_id column (for network log sources without query association)

This allows us to store network log sources honestly - we know they came from
searches, but we cannot reliably determine which specific query each source
came from.
"""

import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path("data") / "llm_search.db"

def migrate():
    """Perform the schema migration."""
    print("=" * 80)
    print("MIGRATING SOURCES TABLE SCHEMA")
    print("=" * 80)
    print()

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("No migration needed - schema will be correct on first create_tables()")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(sources)")
        columns = {row[1]: row for row in cursor.fetchall()}

        print("Current columns:")
        for col_name in columns:
            print(f"  - {col_name}")
        print()

        # Check if response_id already exists
        if 'response_id' in columns:
            print("✓ Migration already applied (response_id column exists)")
            return

        print("Applying migration...")
        print()

        # SQLite doesn't support ALTER COLUMN to change nullability
        # We need to recreate the table

        # Step 1: Create new table with updated schema
        print("1. Creating new sources table...")
        cursor.execute("""
            CREATE TABLE sources_new (
                id INTEGER PRIMARY KEY,
                search_query_id INTEGER,
                response_id INTEGER,
                url TEXT NOT NULL,
                title TEXT,
                domain VARCHAR(255),
                rank INTEGER,
                pub_date VARCHAR(50),
                snippet_text TEXT,
                internal_score REAL,
                metadata_json TEXT,
                FOREIGN KEY (search_query_id) REFERENCES search_queries(id),
                FOREIGN KEY (response_id) REFERENCES responses(id)
            )
        """)

        # Step 2: Copy data from old table
        print("2. Copying data from old table...")
        cursor.execute("""
            INSERT INTO sources_new
            (id, search_query_id, url, title, domain, rank, pub_date,
             snippet_text, internal_score, metadata_json)
            SELECT
                id, search_query_id, url, title, domain, rank, pub_date,
                snippet_text, internal_score, metadata_json
            FROM sources
        """)

        rows_copied = cursor.rowcount
        print(f"   Copied {rows_copied} rows")

        # Step 3: Drop old table
        print("3. Dropping old table...")
        cursor.execute("DROP TABLE sources")

        # Step 4: Rename new table
        print("4. Renaming new table...")
        cursor.execute("ALTER TABLE sources_new RENAME TO sources")

        # Commit changes
        conn.commit()

        print()
        print("=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)
        print()
        print("Changes applied:")
        print("  ✓ search_query_id is now nullable")
        print("  ✓ response_id column added")
        print()
        print("This allows network log sources to be stored without query association,")
        print("since ChatGPT network logs don't provide reliable query-to-source mapping.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
