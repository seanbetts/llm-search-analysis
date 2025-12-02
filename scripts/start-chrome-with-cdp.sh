#!/bin/bash
# ============================================================================
# Start Chrome with Remote Debugging (CDP) for Docker Playwright Connection
# ============================================================================
# This script launches Chrome on macOS with remote debugging enabled,
# allowing Playwright running in Docker to connect via CDP.
#
# Usage: ./scripts/start-chrome-with-cdp.sh
# ============================================================================

set -e

# Configuration
CDP_PORT=9222
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

# Check if CDP port is already in use
if lsof -Pi :$CDP_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $CDP_PORT is already in use${NC}"
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

# Create user data directory if it doesn't exist
mkdir -p "$USER_DATA_DIR"

echo "📁 User Data Directory: $USER_DATA_DIR"
echo "🔌 CDP Port: $CDP_PORT"
echo ""

# Launch Chrome with remote debugging
echo "🚀 Launching Chrome..."
"$CHROME_APP" \
  --remote-debugging-port=$CDP_PORT \
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
if ps -p $CHROME_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome started successfully!${NC}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Chrome is now ready for Playwright connections${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📋 Connection Details:"
    echo "   CDP URL: http://localhost:$CDP_PORT"
    echo "   Process ID: $CHROME_PID"
    echo ""
    echo "🐳 Docker will connect automatically via:"
    echo "   http://host.docker.internal:$CDP_PORT"
    echo ""
    echo "💡 Tips:"
    echo "   • Keep this Chrome instance running while using the app"
    echo "   • Use a separate regular Chrome for other browsing"
    echo "   • To stop: Close Chrome or run: kill $CHROME_PID"
    echo ""
else
    echo -e "${YELLOW}❌ Failed to start Chrome${NC}"
    exit 1
fi
