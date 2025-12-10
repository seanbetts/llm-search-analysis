#!/bin/bash
# Run backend and frontend tests for LLM Search Analysis
# Also runs linting and docstring checks

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-}"
BACKEND_PYTEST_ADDOPTS="${BACKEND_PYTEST_ADDOPTS:-$USER_PYTEST_ADDOPTS}"
FRONTEND_PYTEST_ADDOPTS="${FRONTEND_PYTEST_ADDOPTS:-$USER_PYTEST_ADDOPTS}"
SKIP_EXTERNAL="${SKIP_EXTERNAL:-0}"
SKIP_LINT="${SKIP_LINT:-0}"
FRONTEND_PYTHON_BIN="${FRONTEND_PYTHON:-python}"
COVERAGE_PYTHON="$FRONTEND_PYTHON_BIN"
GENERATE_HTML_COVERAGE="${GENERATE_HTML_COVERAGE:-0}"

# Fallback to python3 if `python` is unavailable (e.g., macOS defaults)
if ! command -v "$FRONTEND_PYTHON_BIN" >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  FRONTEND_PYTHON_BIN="python3"
  COVERAGE_PYTHON="$FRONTEND_PYTHON_BIN"
fi

if [[ "$SKIP_EXTERNAL" == "1" ]]; then
  BACKEND_PYTEST_ADDOPTS="${BACKEND_PYTEST_ADDOPTS:+$BACKEND_PYTEST_ADDOPTS }--ignore=tests/test_e2e_persistence.py"
fi

log_section() {
  echo ""
  echo "==================================================================="
  echo "🔸 $1"
  echo "==================================================================="
}

run_linting_checks() {
  log_section "Running linting and docstring checks"

  if ! command -v ruff &> /dev/null; then
    echo "⚠️  Ruff not found. Skipping linting checks."
    echo "   Install with: pip install ruff"
    return 0
  fi

  (
    cd "$REPO_ROOT"
    echo "Running Ruff linting..."
    if ! ruff check .; then
      echo "❌ Linting errors found. Run 'make lint' for details."
      return 1
    fi

    echo ""
    echo "Running docstring checks..."
    if ! ruff check --select D .; then
      echo "❌ Docstring issues found. Run 'make docstring-check' for details."
      return 1
    fi

    echo "✅ All linting and docstring checks passed"
  )
}

run_backend_tests() {
  log_section "Running backend test suite"
  if [[ ! -x "$REPO_ROOT/backend/scripts/run_tests.sh" ]]; then
    echo "Backend test runner script not found or not executable: backend/scripts/run_tests.sh"
    exit 1
  fi
  local coverage_file="$REPO_ROOT/backend/.coverage"
  rm -f "$coverage_file"
  (
    cd "$REPO_ROOT/backend" && \
    PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" \
    PYTEST_ADDOPTS="$BACKEND_PYTEST_ADDOPTS" \
    COVERAGE_FILE="$coverage_file" \
    ./scripts/run_tests.sh
  )
}

run_frontend_tests() {
  log_section "Running frontend tests"
  local python_bin="$FRONTEND_PYTHON_BIN"
  if ! "$python_bin" -m pytest --version >/dev/null 2>&1; then
    echo "pytest is required to run frontend tests (via $python_bin). Please install project dependencies."
    exit 1
  fi
  local coverage_file="$REPO_ROOT/frontend/.coverage"
  rm -f "$coverage_file"
  (
    cd "$REPO_ROOT" && \
    PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
    PYTEST_ADDOPTS="$FRONTEND_PYTEST_ADDOPTS" \
    COVERAGE_FILE="$coverage_file" \
    "$python_bin" -m coverage run -m pytest frontend/tests/ -v
  )
}

combine_coverage_reports() {
  log_section "Combining backend + frontend coverage"
  local coverage_files=()
  [[ -f "$REPO_ROOT/backend/.coverage" ]] && coverage_files+=("$REPO_ROOT/backend/.coverage")
  [[ -f "$REPO_ROOT/frontend/.coverage" ]] && coverage_files+=("$REPO_ROOT/frontend/.coverage")

  if [[ ${#coverage_files[@]} -eq 0 ]]; then
    echo "No coverage data found. Skipping combined coverage report."
    return
  fi

  (
    cd "$REPO_ROOT"
    local combined_file="$REPO_ROOT/.coverage"
    rm -f "$combined_file"
    COVERAGE_FILE="$combined_file" "$COVERAGE_PYTHON" -m coverage combine "${coverage_files[@]}"
    local coverage_report
    coverage_report="$("$COVERAGE_PYTHON" -m coverage report --omit="tests/*")"
    printf '%s\n' "$coverage_report"
    local coverage_pct
    coverage_pct=$(printf '%s\n' "$coverage_report" | awk '/TOTAL/ {print $NF}' | tail -n 1)
    if [[ -n "$coverage_pct" ]]; then
      echo "Combined coverage: $coverage_pct"
    fi
    if [[ "$GENERATE_HTML_COVERAGE" == "1" ]]; then
      "$COVERAGE_PYTHON" -m coverage html -d coverage_html
      echo "Combined coverage HTML report available at coverage_html/index.html"
    fi
  )
}

main() {
  echo "🧪 Running full test suite (linting + backend + frontend)"
  local lint_status=0
  local backend_status=0
  local frontend_status=0

  echo "Frontend python: $FRONTEND_PYTHON_BIN"
  echo "Backend PYTEST_ADDOPTS: ${BACKEND_PYTEST_ADDOPTS:-<none>}"
  echo "Frontend PYTEST_ADDOPTS: ${FRONTEND_PYTEST_ADDOPTS:-<none>}"
  echo "Generate HTML coverage: ${GENERATE_HTML_COVERAGE}"
  echo "Skip linting: ${SKIP_LINT}"

  if [[ "$SKIP_EXTERNAL" == "1" ]]; then
    echo "🔕 SKIP_EXTERNAL=1: backend run will ignore tests/test_e2e_persistence.py"
  fi

  # Run linting checks first (unless skipped)
  if [[ "$SKIP_LINT" != "1" ]]; then
    set +e
    run_linting_checks
    lint_status=$?
    set -e
    if [[ $lint_status -ne 0 ]]; then
      echo "⚠️  Linting checks failed (exit code $lint_status). Continuing to tests..."
    fi
  else
    echo "🔕 SKIP_LINT=1: skipping linting and docstring checks"
  fi

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

  combine_coverage_reports

  if [[ $lint_status -eq 0 && $backend_status -eq 0 && $frontend_status -eq 0 ]]; then
    echo ""
    echo "✅ All linting checks and tests completed successfully."
  else
    echo ""
    echo "❌ Test suite completed with failures."
    [[ $lint_status -ne 0 ]] && echo "   - Linting: FAILED"
    [[ $backend_status -ne 0 ]] && echo "   - Backend tests: FAILED"
    [[ $frontend_status -ne 0 ]] && echo "   - Frontend tests: FAILED"
    exit 1
  fi
}

main "$@"
