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

# Detect docker compose command (V2 vs V1)
if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${YELLOW}❌ Docker Compose not found${NC}"
    echo "Please install Docker Compose and try again."
    exit 1
fi

echo "📦 Step 1: Starting backend (Docker)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$DOCKER_COMPOSE up -d --remove-orphans

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
        echo "Check logs with: $DOCKER_COMPOSE logs api"
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

# Check if Playwright browsers are installed (optional - only needed for network capture mode)
# We'll skip this check and let users install on-demand if they use network capture
# This avoids errors and speeds up startup

# Check if port 8501 is already in use
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8501 is already in use${NC}"
    echo ""
    echo "A Streamlit instance is already running on port 8501."
    echo ""
    echo "What would you like to do?"
    echo "  1) Kill the existing process and start fresh"
    echo "  2) Keep the existing instance (recommended)"
    echo ""
    read -p "Enter your choice (1 or 2): " choice
    echo ""

    case $choice in
        1)
            echo "Stopping existing Streamlit process..."
            kill $(lsof -ti:8501) 2>/dev/null || true
            sleep 2
            echo -e "${GREEN}✅ Existing process stopped${NC}"
            echo ""
            ;;
        2|*)
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo -e "${GREEN}✅ Using existing Streamlit instance${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "📋 Access Points:"
            echo "   Frontend (Streamlit): http://localhost:8501"
            echo "   Backend API: http://localhost:8000"
            echo "   API Docs: http://localhost:8000/docs"
            echo ""
            echo "💡 To stop the frontend: kill \$(lsof -ti:8501)"
            echo ""
            exit 0
            ;;
    esac
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
echo "   • Backend: $DOCKER_COMPOSE down"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Export environment variables and start Streamlit
export API_BASE_URL=http://localhost:8000
unset CHROME_CDP_URL
streamlit run app.py --server.port 8501
