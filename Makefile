.PHONY: help lint docstring-check docstring-fix format test test-backend test-frontend clean

help:
	@echo "LLM Search Analysis - Development Commands"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              Run all linting checks (includes docstrings)"
	@echo "  make docstring-check   Check docstring coverage and style"
	@echo "  make docstring-fix     Auto-fix docstring formatting issues"
	@echo "  make format            Format code with black and ruff"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run all tests"
	@echo "  make test-backend      Run backend tests with coverage"
	@echo "  make test-frontend     Run frontend tests"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean             Remove cache files and temp directories"

# Linting commands
lint:
	@echo "Running Ruff linting..."
	ruff check .
	@echo ""
	@echo "Running mypy type checking..."
	cd backend && mypy app

docstring-check:
	@echo "Checking docstring coverage and style..."
	@echo ""
	@echo "Backend modules:"
	ruff check backend/
	@echo ""
	@echo "Frontend modules:"
	ruff check frontend/
	@echo ""
	@echo "Scripts:"
	ruff check scripts/

docstring-fix:
	@echo "Auto-fixing docstring formatting..."
	ruff check --select D --fix .

format:
	@echo "Formatting with ruff..."
	ruff check --fix .
	ruff format .
	@echo ""
	@echo "Formatting with black (backend only)..."
	cd backend && black app/

# Testing commands
test:
	@echo "Running all tests..."
	pytest

test-backend:
	@echo "Running backend tests with coverage..."
	cd backend && pytest --cov=app --cov-report=term-missing

test-frontend:
	@echo "Running frontend tests..."
	pytest frontend/tests -v

# Utility commands
clean:
	@echo "Cleaning up cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete!"
