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
  PYTHON_BIN="${FRONTEND_PYTHON:-python}"
  (
    cd "$REPO_ROOT" && \
    PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -m pytest frontend/tests/ -v ${PYTEST_ADDOPTS:-}
  )
}

main() {
  echo "🧪 Running full test suite (backend + frontend)"
  backend_status=0
  frontend_status=0

  set +e
  run_backend_tests
  backend_status=$?
  set -e
  if [[ $backend_status -ne 0 ]]; then
    echo "⚠️  Backend tests failed (exit code $backend_status). Continuing to frontend..."
  fi

  set +e
  run_frontend_tests
  frontend_status=$?
  set -e

  if [[ $backend_status -eq 0 && $frontend_status -eq 0 ]]; then
    echo ""
    echo "✅ All frontend and backend tests completed successfully."
  else
    echo ""
    echo "❌ Test suite completed with failures."
    exit 1
  fi
}

main "$@"
