#!/bin/bash
# Run backend and frontend tests for LLM Search Analysis

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log_section() {
  echo ""
  echo "==================================================================="
  echo "🔸 $1"
  echo "==================================================================="
}

run_backend_tests() {
  log_section "Running backend test suite"
  if [[ ! -x "$REPO_ROOT/backend/scripts/run_tests.sh" ]]; then
    echo "Backend test runner script not found or not executable: backend/scripts/run_tests.sh"
    exit 1
  fi
  (
    cd "$REPO_ROOT/backend" && \
    PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" ./scripts/run_tests.sh
  )
}

run_frontend_tests() {
  log_section "Running frontend tests"
  if ! command -v pytest >/dev/null 2>&1; then
    echo "pytest is required to run frontend tests. Please install project dependencies."
    exit 1
  fi
  (cd "$REPO_ROOT" && pytest frontend/tests/ -v)
}

main() {
  echo "🧪 Running full test suite (backend + frontend)"
  run_backend_tests
  run_frontend_tests
  echo ""
  echo "✅ All frontend and backend tests completed successfully."
}

main "$@"
