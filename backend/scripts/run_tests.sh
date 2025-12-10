#!/bin/bash
# ============================================================================
# Test Runner for LLM Search Analysis Backend
# ============================================================================
# This script ensures SDK validation tests run FIRST before unit tests.
# SDK validation tests verify that the installed SDKs match our code's
# expectations, preventing issues where mocked tests pass but real code fails.
# ============================================================================

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BACKEND_ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🧪 Running LLM Search Analysis Test Suite"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: SDK Validation Tests (must pass before running unit tests)
echo -e "${BLUE}Step 1: SDK Validation Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "These tests verify that installed SDK versions are compatible with our code."
echo ""

if pytest tests/test_provider_sdk_validation.py -v -m sdk_validation; then
  echo ""
  echo -e "${GREEN}✅ SDK validation tests passed${NC}"
  echo ""
else
  echo ""
  echo -e "${RED}❌ SDK validation tests FAILED${NC}"
  echo ""
  echo "SDK validation tests ensure that:"
  echo "  • OpenAI SDK has client.responses attribute (requires version 2.x)"
  echo "  • Google SDK has client.models.generate_content method"
  echo "  • Anthropic SDK has client.messages.create method"
  echo ""
  echo "If these tests fail, your SDK versions may be incompatible."
  echo "Check requirements.txt and ensure you have the correct versions installed."
  echo ""
  exit 1
fi

# Step 2: Unit Tests (instrumented for coverage)
echo -e "${BLUE}Step 2: Unit Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

export COVERAGE_RCFILE="${COVERAGE_RCFILE:-$BACKEND_ROOT/../.coveragerc}"

if coverage run -m pytest tests/ -v -m "not sdk_validation" --ignore=tests/test_provider_sdk_validation.py; then
  echo ""
  echo -e "${GREEN}✅ Unit tests passed${NC}"
  echo ""
else
  echo ""
  echo -e "${RED}❌ Unit tests FAILED${NC}"
  echo ""
  exit 1
fi

# Step 3: Test Coverage Report
echo -e "${BLUE}Step 3: Test Coverage Report${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

coverage combine >/dev/null 2>&1 || true
coverage report
if [[ "${GENERATE_HTML_COVERAGE:-0}" == "1" ]]; then
  coverage html
  echo "HTML coverage report available at htmlcov/index.html"
fi
echo ""
echo -e "${GREEN}✅ Coverage summary generated${NC}"
echo ""

# Final Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ All tests passed!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
