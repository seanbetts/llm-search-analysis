#!/bin/bash
# ============================================================================
# SQLite Database Backup Script
# ============================================================================
# Creates a timestamped backup of the SQLite database
#
# Usage: ./backend/scripts/backup-database.sh [backup_dir]
#
# Options:
#   backup_dir - Optional backup directory (default: <repo>/backups)
#
# Examples:
#   ./backend/scripts/backup-database.sh
#   ./backend/scripts/backup-database.sh /path/to/backups
# ============================================================================

set -e  # Exit on any error

# Resolve project paths regardless of invocation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
DB_FILE="${LLM_SEARCH_DB_FILE:-$REPO_ROOT/backend/data/llm_search.db}"
if [ -n "$1" ]; then
    BACKUP_DIR="$1"
else
    BACKUP_DIR="$REPO_ROOT/backend/backups"
fi
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Expand backup dir for display/logging
BACKUP_DIR="$(mkdir -p "$BACKUP_DIR" && cd "$BACKUP_DIR" && pwd)"
BACKUP_FILE="$BACKUP_DIR/llm_search_${TIMESTAMP}.db"

echo "🗄️  SQLite Database Backup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if database file exists
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}❌ Database file not found: $DB_FILE${NC}"
    echo "Set LLM_SEARCH_DB_FILE or run alembic migrations to create it."
    exit 1
fi

# Get database info before backup
DB_SIZE=$(ls -lh "$DB_FILE" | awk '{print $5}')
INTERACTION_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM interactions;" 2>/dev/null || echo "0")
RESPONSE_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM responses;" 2>/dev/null || echo "0")
echo "📊 Database Info:"
echo "   File: $DB_FILE"
echo "   Size: $DB_SIZE"
echo "   Interactions: $INTERACTION_COUNT"
echo "   Responses: $RESPONSE_COUNT"
echo ""

# Create backup using SQLite's backup command (hot backup)
echo "💾 Creating backup..."
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# Verify backup was created
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ Backup failed${NC}"
    exit 1
fi

# Verify backup integrity
echo "🔍 Verifying backup integrity..."
if ! sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo -e "${RED}❌ Backup integrity check failed${NC}"
    rm -f "$BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo -e "${GREEN}✅ Backup created successfully${NC}"
echo ""
echo "📁 Backup Details:"
echo "   File: $BACKUP_FILE"
echo "   Size: $BACKUP_SIZE"
echo "   Created: $(date)"
echo ""

# Show all backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.db 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo "📦 All Backups ($BACKUP_COUNT):"
    ls -lht "$BACKUP_DIR"/*.db | awk '{print "   " $9 " (" $5 ") - " $6 " " $7 " " $8}'
    echo ""

    # Calculate total backup size
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | awk '{print $1}')
    echo "   Total backup size: $TOTAL_SIZE"
    echo ""
fi

# Cleanup old backups (keep last 10)
OLD_BACKUPS=$(ls -1t "$BACKUP_DIR"/*.db 2>/dev/null | tail -n +11)
if [ -n "$OLD_BACKUPS" ]; then
    echo -e "${YELLOW}🧹 Cleaning up old backups (keeping 10 most recent)...${NC}"
    echo "$OLD_BACKUPS" | while read -r old_backup; do
        echo "   Removing: $(basename "$old_backup")"
        rm -f "$old_backup"
    done
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Backup complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 To restore this backup:"
echo "   ./backend/scripts/restore-database.sh $BACKUP_FILE"
echo ""
