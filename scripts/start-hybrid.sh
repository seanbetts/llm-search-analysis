#!/bin/bash
# ============================================================================
# Start LLM Search Analysis - Hybrid Architecture
# ============================================================================
# This script starts the application in hybrid mode:
#   - Backend (FastAPI) in Docker
#   - Frontend (Streamlit) natively on macOS
#
# Usage: ./scripts/start-hybrid.sh
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🚀 Starting LLM Search Analysis (Hybrid Mode)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo -e "${YELLOW}Please edit .env and add your API keys, then run this script again.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}❌ Docker is not running${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "📦 Step 1: Starting backend (Docker)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose up -d

# Wait for backend to be healthy
echo ""
echo "⏳ Waiting for backend to be healthy..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is healthy!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠️  Backend health check timeout${NC}"
        echo "Check logs with: docker compose logs api"
        exit 1
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "🎨 Step 2: Starting frontend (native)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo -e "${YELLOW}⚠️  Streamlit not found. Installing dependencies...${NC}"
    pip install -r requirements.txt
    echo ""
fi

# Check if Chrome is installed
if ! command -v playwright &> /dev/null || ! playwright show-browsers | grep -q "chrome"; then
    echo -e "${YELLOW}⚠️  Chrome not found. Installing Playwright browsers...${NC}"
    playwright install chrome
    echo ""
fi

echo -e "${BLUE}Starting Streamlit frontend...${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Application is ready!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Access Points:"
echo "   Frontend (Streamlit): http://localhost:8501"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "💡 To stop:"
echo "   • Frontend: Press Ctrl+C"
echo "   • Backend: docker compose down"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Export environment variables and start Streamlit
export API_BASE_URL=http://localhost:8000
unset CHROME_CDP_URL
streamlit run app.py --server.port 8501
