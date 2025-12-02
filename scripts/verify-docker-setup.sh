#!/bin/bash
# ============================================================================
# Docker Compose Verification Script
# ============================================================================
# Verifies that the Docker Compose local production setup is working correctly
#
# Usage: ./scripts/verify-docker-setup.sh
# ============================================================================

set -e  # Exit on any error

echo "🔍 Verifying Docker Compose Setup..."
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker is running
echo "1️⃣  Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is running${NC}"
echo ""

# Check Docker Compose is installed
echo "2️⃣  Checking Docker Compose..."
if ! docker-compose --version > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi
COMPOSE_VERSION=$(docker-compose --version)
echo -e "${GREEN}✅ $COMPOSE_VERSION${NC}"
echo ""

# Check containers are running
echo "3️⃣  Checking containers..."
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}⚠️  Containers are not running${NC}"
    echo "Starting containers..."
    docker-compose up -d
    echo "Waiting for containers to be healthy (30s)..."
    sleep 30
fi

CONTAINERS=$(docker-compose ps --format "table {{.Name}}\t{{.Status}}" | tail -n +2)
echo "$CONTAINERS"
echo ""

# Check both containers are healthy
if ! echo "$CONTAINERS" | grep -q "healthy"; then
    echo -e "${RED}❌ Containers are not healthy${NC}"
    echo "Check logs with: docker-compose logs"
    exit 1
fi
echo -e "${GREEN}✅ All containers are healthy${NC}"
echo ""

# Check backend health endpoint
echo "4️⃣  Checking backend API..."
BACKEND_HEALTH=$(curl -s http://localhost:8000/health)
if ! echo "$BACKEND_HEALTH" | grep -q "healthy"; then
    echo -e "${RED}❌ Backend health check failed${NC}"
    echo "Response: $BACKEND_HEALTH"
    exit 1
fi
echo -e "${GREEN}✅ Backend is healthy${NC}"
echo "Response: $BACKEND_HEALTH"
echo ""

# Check database connection
echo "5️⃣  Checking database..."
if ! echo "$BACKEND_HEALTH" | grep -q "connected"; then
    echo -e "${RED}❌ Database is not connected${NC}"
    exit 1
fi

# Check database file exists
if [ ! -f "backend/data/llm_search.db" ]; then
    echo -e "${YELLOW}⚠️  Database file not found (will be created on first use)${NC}"
else
    DB_SIZE=$(ls -lh backend/data/llm_search.db | awk '{print $5}')
    INTERACTION_COUNT=$(sqlite3 backend/data/llm_search.db "SELECT COUNT(*) FROM responses;" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ Database connected${NC}"
    echo "   Size: $DB_SIZE"
    echo "   Interactions: $INTERACTION_COUNT"
fi
echo ""

# Check frontend health
echo "6️⃣  Checking frontend..."
FRONTEND_HEALTH=$(curl -s http://localhost:8501/_stcore/health)
if [ "$FRONTEND_HEALTH" != "ok" ]; then
    echo -e "${RED}❌ Frontend health check failed${NC}"
    echo "Response: $FRONTEND_HEALTH"
    exit 1
fi
echo -e "${GREEN}✅ Frontend is healthy${NC}"
echo ""

# Check providers endpoint (tests backend API)
echo "7️⃣  Checking API endpoints..."
PROVIDERS=$(curl -s http://localhost:8000/api/v1/providers)
if ! echo "$PROVIDERS" | grep -q "openai"; then
    echo -e "${RED}❌ Providers endpoint failed${NC}"
    echo "Response: $PROVIDERS"
    exit 1
fi
PROVIDER_COUNT=$(echo "$PROVIDERS" | grep -o '"name"' | wc -l | tr -d ' ')
echo -e "${GREEN}✅ API endpoints working${NC}"
echo "   Available providers: $PROVIDER_COUNT"
echo ""

# Check volumes are mounted
echo "8️⃣  Checking volume mounts..."
BACKEND_VOLUME=$(docker inspect llm-search-api --format '{{range .Mounts}}{{.Source}}:{{.Destination}}{{"\n"}}{{end}}' | grep data || echo "")
FRONTEND_VOLUME=$(docker inspect llm-search-frontend --format '{{range .Mounts}}{{.Source}}:{{.Destination}}{{"\n"}}{{end}}' | grep data || echo "")

if [ -z "$BACKEND_VOLUME" ] || [ -z "$FRONTEND_VOLUME" ]; then
    echo -e "${RED}❌ Volume mounts not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Volumes are mounted${NC}"
echo "   Backend: $BACKEND_VOLUME"
echo "   Frontend: $FRONTEND_VOLUME"
echo ""

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ All checks passed!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access URLs:"
echo "   Frontend: http://localhost:8501"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📊 Quick Commands:"
echo "   View logs: docker-compose logs -f"
echo "   Restart: docker-compose restart"
echo "   Stop: docker-compose down"
echo "   Rebuild: docker-compose up -d --build"
echo ""
