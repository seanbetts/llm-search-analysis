#!/bin/bash
# ============================================================================
# SQLite Database Restore Script
# ============================================================================
# Restores the SQLite database from a backup file
#
# Usage: ./scripts/restore-database.sh <backup_file>
#
# WARNING: This will replace the current database!
#
# Examples:
#   ./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db
#   ./scripts/restore-database.sh ./backups/llm_search_20250102_143000.db --force
# ============================================================================

set -e  # Exit on any error

# Configuration
DB_FILE="backend/data/llm_search.db"
BACKUP_FILE="$1"
FORCE="${2}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "♻️  SQLite Database Restore"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if backup file argument provided
if [ -z "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ No backup file specified${NC}"
    echo ""
    echo "Usage: ./scripts/restore-database.sh <backup_file>"
    echo ""
    echo "Available backups:"
    if ls -1 ./backups/*.db 2>/dev/null | head -10; then
        echo ""
        echo "Example:"
        LATEST_BACKUP=$(ls -1t ./backups/*.db 2>/dev/null | head -1)
        echo "  ./scripts/restore-database.sh $LATEST_BACKUP"
    else
        echo "  No backups found in ./backups/"
    fi
    echo ""
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

# Check backup integrity
echo "🔍 Verifying backup integrity..."
if ! sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo -e "${RED}❌ Backup file is corrupted${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Backup file is valid${NC}"
echo ""

# Get backup info
BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
BACKUP_DATE=$(ls -l "$BACKUP_FILE" | awk '{print $6 " " $7 " " $8}')
BACKUP_INTERACTIONS=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM responses;" 2>/dev/null || echo "0")

echo "📊 Backup Info:"
echo "   File: $BACKUP_FILE"
echo "   Size: $BACKUP_SIZE"
echo "   Date: $BACKUP_DATE"
echo "   Interactions: $BACKUP_INTERACTIONS"
echo ""

# Check if current database exists
if [ -f "$DB_FILE" ]; then
    CURRENT_SIZE=$(ls -lh "$DB_FILE" | awk '{print $5}')
    CURRENT_INTERACTIONS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM responses;" 2>/dev/null || echo "0")

    echo "⚠️  Current Database (will be replaced):"
    echo "   File: $DB_FILE"
    echo "   Size: $CURRENT_SIZE"
    echo "   Interactions: $CURRENT_INTERACTIONS"
    echo ""

    # Create automatic backup of current database before restore
    if [ "$FORCE" != "--force" ]; then
        echo -e "${YELLOW}⚠️  WARNING: This will replace the current database!${NC}"
        echo ""
        echo "A backup of the current database will be created first."
        echo ""
        read -p "Continue with restore? (yes/no): " confirm

        if [ "$confirm" != "yes" ]; then
            echo "Restore cancelled"
            exit 0
        fi
    fi

    # Create backup of current database before restore
    echo ""
    echo "💾 Creating backup of current database..."
    PRE_RESTORE_BACKUP="./backups/pre_restore_$(date +"%Y%m%d_%H%M%S").db"
    mkdir -p ./backups
    sqlite3 "$DB_FILE" ".backup '$PRE_RESTORE_BACKUP'"
    echo -e "${GREEN}✅ Current database backed up to: $PRE_RESTORE_BACKUP${NC}"
    echo ""
fi

# Stop Docker containers if they're running
echo "🛑 Checking if Docker containers are running..."
if docker-compose ps 2>/dev/null | grep -q "Up"; then
    echo -e "${YELLOW}⚠️  Docker containers are running. They should be stopped during restore.${NC}"

    if [ "$FORCE" != "--force" ]; then
        read -p "Stop Docker containers? (yes/no): " stop_containers

        if [ "$stop_containers" = "yes" ]; then
            echo "Stopping containers..."
            docker-compose down
            CONTAINERS_STOPPED=true
        else
            echo -e "${YELLOW}⚠️  Restoring while containers are running may cause issues${NC}"
        fi
    else
        echo "Stopping containers..."
        docker-compose down
        CONTAINERS_STOPPED=true
    fi
fi
echo ""

# Restore database
echo "♻️  Restoring database..."
cp "$BACKUP_FILE" "$DB_FILE"

# Verify restored database
echo "🔍 Verifying restored database..."
if ! sqlite3 "$DB_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo -e "${RED}❌ Restore failed - database is corrupted${NC}"
    if [ -f "$PRE_RESTORE_BACKUP" ]; then
        echo "Restoring previous database..."
        cp "$PRE_RESTORE_BACKUP" "$DB_FILE"
    fi
    exit 1
fi

RESTORED_INTERACTIONS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM responses;" 2>/dev/null || echo "0")
echo -e "${GREEN}✅ Database restored successfully${NC}"
echo ""
echo "📊 Restored Database:"
echo "   File: $DB_FILE"
echo "   Size: $(ls -lh "$DB_FILE" | awk '{print $5}')"
echo "   Interactions: $RESTORED_INTERACTIONS"
echo ""

# Restart Docker containers if we stopped them
if [ "$CONTAINERS_STOPPED" = true ]; then
    echo "🚀 Restarting Docker containers..."
    docker-compose up -d
    echo "Waiting for containers to be healthy (15s)..."
    sleep 15
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Restore complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "$PRE_RESTORE_BACKUP" ]; then
    echo "💡 The previous database was backed up to:"
    echo "   $PRE_RESTORE_BACKUP"
    echo ""
fi

echo "🌐 Access the application:"
echo "   Frontend: http://localhost:8501"
echo "   Backend: http://localhost:8000"
echo ""
