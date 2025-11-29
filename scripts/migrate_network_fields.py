"""
Lightweight SQLite migration to add network capture fields.

Adds:
- search_queries.order_index (INTEGER)
- sources.pub_date (TEXT)
- sources_used.metadata_json (JSON)
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/llm_search.db")


def column_exists(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def add_column(conn, table, column_def):
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
    print(f"Added {table}.{column_def}")


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}, nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        if not column_exists(conn, "search_queries", "order_index"):
            add_column(conn, "search_queries", "order_index INTEGER DEFAULT 0")

        if not column_exists(conn, "sources", "pub_date"):
            add_column(conn, "sources", "pub_date TEXT")

        if not column_exists(conn, "sources_used", "metadata_json"):
            add_column(conn, "sources_used", "metadata_json JSON")

        conn.commit()
        print("Migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
