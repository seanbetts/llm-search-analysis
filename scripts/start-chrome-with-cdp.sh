#!/bin/bash
# ============================================================================
# Start Chrome with Remote Debugging (CDP) for Docker Playwright Connection
# ============================================================================
# ⚠️  NOTE: This script is NOT needed for the hybrid architecture.
# ⚠️  It's kept for reference in case you want to try CDP connections.
#
# For the hybrid architecture, simply run:
#   ./scripts/start-hybrid.sh
#
# This script launches Chrome on macOS with remote debugging enabled,
# allowing Playwright running in Docker to connect via CDP.
#
# Usage: ./scripts/start-chrome-with-cdp.sh
# ============================================================================

set -e

# Configuration
CDP_PORT_CHROME=9222      # Chrome listens on localhost:9222
CDP_PORT_PUBLIC=9223      # socat forwards 0.0.0.0:9223 -> localhost:9222
USER_DATA_DIR="$HOME/Library/Application Support/Google/Chrome/PlaywrightProfile"
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🌐 Starting Chrome with Remote Debugging"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Chrome is installed
if [ ! -f "$CHROME_APP" ]; then
    echo -e "${YELLOW}❌ Chrome not found at: $CHROME_APP${NC}"
    echo "Please install Google Chrome from https://www.google.com/chrome/"
    exit 1
fi

# Check if ports are already in use
if lsof -Pi :$CDP_PORT_CHROME -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $CDP_PORT_CHROME is already in use${NC}"
    echo ""
    echo "Chrome may already be running with remote debugging."
    echo "If you want to restart it:"
    echo "  1. Close all Chrome windows"
    echo "  2. Run: pkill -9 'Google Chrome'"
    echo "  3. Run this script again"
    echo ""
    read -p "Continue anyway? (yes/no): " continue_anyway
    if [ "$continue_anyway" != "yes" ]; then
        exit 0
    fi
fi

if lsof -Pi :$CDP_PORT_PUBLIC -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $CDP_PORT_PUBLIC is already in use${NC}"
    echo "Killing existing socat process..."
    lsof -ti :$CDP_PORT_PUBLIC | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Create user data directory if it doesn't exist
mkdir -p "$USER_DATA_DIR"

echo "📁 User Data Directory: $USER_DATA_DIR"
echo "🔌 Chrome CDP Port: localhost:$CDP_PORT_CHROME"
echo "🔌 Public CDP Port: 0.0.0.0:$CDP_PORT_PUBLIC"
echo ""

# Launch Chrome with remote debugging
echo "🚀 Launching Chrome..."
"$CHROME_APP" \
  --remote-debugging-port=$CDP_PORT_CHROME \
  --user-data-dir="$USER_DATA_DIR" \
  --disable-blink-features=AutomationControlled \
  --disable-web-security \
  --no-first-run \
  --no-default-browser-check \
  > /dev/null 2>&1 &

CHROME_PID=$!

# Wait a moment for Chrome to start
sleep 2

# Verify Chrome started
if ! ps -p $CHROME_PID > /dev/null 2>&1; then
    echo -e "${YELLOW}❌ Failed to start Chrome${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Chrome started successfully!${NC}"
echo ""

# Start socat to forward public port to Chrome's localhost port
echo "🔀 Starting port forwarder (socat)..."
socat TCP-LISTEN:$CDP_PORT_PUBLIC,bind=0.0.0.0,reuseaddr,fork TCP:localhost:$CDP_PORT_CHROME > /dev/null 2>&1 &
SOCAT_PID=$!

# Wait a moment for socat to start
sleep 1

# Verify socat started
if ps -p $SOCAT_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Port forwarder started successfully!${NC}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Chrome is now ready for Playwright connections${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📋 Connection Details:"
    echo "   Chrome CDP (localhost only): http://localhost:$CDP_PORT_CHROME"
    echo "   Public CDP (for Docker): http://localhost:$CDP_PORT_PUBLIC"
    echo "   Process IDs: Chrome=$CHROME_PID, socat=$SOCAT_PID"
    echo ""
    echo "🐳 Docker will connect automatically via:"
    echo "   http://host.docker.internal:$CDP_PORT_PUBLIC"
    echo ""
    echo "💡 Tips:"
    echo "   • Keep this Chrome instance running while using the app"
    echo "   • Use a separate regular Chrome for other browsing"
    echo "   • To stop: Close Chrome or run: kill $CHROME_PID $SOCAT_PID"
    echo ""
else
    echo -e "${YELLOW}❌ Failed to start port forwarder${NC}"
    kill $CHROME_PID 2>/dev/null
    exit 1
fi
