#!/bin/bash
# ============================================================================
# Hybrid Architecture Verification Script
# ============================================================================
# Verifies that the hybrid architecture setup is working correctly:
#   - Backend (FastAPI) running in Docker
#   - Frontend (Streamlit) running natively on macOS (optional)
#
# Usage: ./scripts/verify-docker-setup.sh
# ============================================================================

set -e  # Exit on any error

echo "🔍 Verifying Hybrid Architecture Setup..."
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

# Detect and check Docker Compose (V2 vs V1)
echo "2️⃣  Checking Docker Compose..."
if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
    COMPOSE_VERSION=$(docker compose version)
elif command -v docker-compose > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version)
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ $COMPOSE_VERSION${NC}"
echo ""

# Check backend container is running
echo "3️⃣  Checking backend container..."
if ! $DOCKER_COMPOSE ps | grep "llm-search-api" | grep -q "Up"; then
    echo -e "${YELLOW}⚠️  Backend container is not running${NC}"
    echo "Starting backend..."
    $DOCKER_COMPOSE up -d
    echo "Waiting for backend to be healthy (30s)..."
    sleep 30
fi

BACKEND_STATUS=$($DOCKER_COMPOSE ps --format "table {{.Name}}\t{{.Status}}" | grep "llm-search-api" || echo "")
echo "$BACKEND_STATUS"
echo ""

# Check backend container is healthy
if ! echo "$BACKEND_STATUS" | grep -q "healthy"; then
    echo -e "${RED}❌ Backend container is not healthy${NC}"
    echo "Check logs with: $DOCKER_COMPOSE logs api"
    exit 1
fi
echo -e "${GREEN}✅ Backend container is healthy${NC}"
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

# Check frontend health (optional - runs natively)
echo "6️⃣  Checking frontend (optional)..."
FRONTEND_HEALTH=$(curl -s http://localhost:8501/_stcore/health 2>/dev/null || echo "")
if [ "$FRONTEND_HEALTH" = "ok" ]; then
    echo -e "${GREEN}✅ Frontend is running (native)${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend is not running${NC}"
    echo "   To start: ./scripts/start-hybrid.sh"
    echo "   Or manually: export API_BASE_URL=http://localhost:8000 && streamlit run app.py --server.port 8501"
fi
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

# Check backend volume is mounted
echo "8️⃣  Checking backend volume mount..."
BACKEND_VOLUME=$(docker inspect llm-search-api --format '{{range .Mounts}}{{.Source}}:{{.Destination}}{{"\n"}}{{end}}' | grep data || echo "")

if [ -z "$BACKEND_VOLUME" ]; then
    echo -e "${RED}❌ Backend volume mount not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Backend volume is mounted${NC}"
echo "   $BACKEND_VOLUME"
echo ""

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Backend checks passed!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access URLs:"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
if [ "$FRONTEND_HEALTH" = "ok" ]; then
    echo "   Frontend: http://localhost:8501 ✅"
else
    echo "   Frontend: Not running (start with ./scripts/start-hybrid.sh)"
fi
echo ""
echo "📊 Backend Commands:"
echo "   View logs: $DOCKER_COMPOSE logs -f api"
echo "   Restart: $DOCKER_COMPOSE restart api"
echo "   Stop: $DOCKER_COMPOSE down"
echo "   Rebuild: $DOCKER_COMPOSE up -d --build"
echo ""
echo "🎨 Frontend Commands:"
echo "   Start: ./scripts/start-hybrid.sh"
echo "   Or manual: export API_BASE_URL=http://localhost:8000 && streamlit run app.py --server.port 8501"
echo ""
