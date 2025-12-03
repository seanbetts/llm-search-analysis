#!/usr/bin/env python3
"""
Migration script to add metrics columns to responses table.

Adds:
- sources_found (INTEGER)
- sources_used_count (INTEGER)
- avg_rank (REAL, nullable)

These columns were added in Phase 1.1 to store backend-computed metrics.
"""

import sqlite3
import sys
from pathlib import Path

# Get database path
DB_PATH = Path(__file__).parent.parent / "data" / "llm_search.db"

def main():
    """Run the migration."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Migrating database at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(responses)")
        columns = [row[1] for row in cursor.fetchall()]

        migrations_needed = []
        if 'sources_found' not in columns:
            migrations_needed.append(('sources_found', 'INTEGER DEFAULT 0'))
        if 'sources_used_count' not in columns:
            migrations_needed.append(('sources_used_count', 'INTEGER DEFAULT 0'))
        if 'avg_rank' not in columns:
            migrations_needed.append(('avg_rank', 'REAL'))

        if not migrations_needed:
            print("All columns already exist. No migration needed.")
            return

        # Add missing columns
        for col_name, col_def in migrations_needed:
            print(f"Adding column: {col_name} {col_def}")
            cursor.execute(f"ALTER TABLE responses ADD COLUMN {col_name} {col_def}")

        conn.commit()
        print(f"✓ Migration complete. Added {len(migrations_needed)} column(s).")

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
