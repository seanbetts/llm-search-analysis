# Contributing to LLM Search Analysis

Thank you for your interest in contributing to LLM Search Analysis! This guide will help you understand our development standards and workflows.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Docstring Style (Google)](#docstring-style-google)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Code Review Guidelines](#code-review-guidelines)

## Getting Started

1. **Fork and clone** the repository
2. **Set up your environment** following the [README quickstart](README.md#quickstart)
3. **Create a feature branch** from `main`
4. **Make your changes** following our standards below
5. **Run tests** to ensure everything passes
6. **Submit a pull request** with a clear description

## Development Setup

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For linting and testing tools
alembic upgrade head
pytest --cov=app
```

### Frontend Development
```bash
pip install -r requirements.txt
playwright install chrome  # Only needed for network capture mode
pytest frontend/tests -v
```

### Running Locally
Use the hybrid setup for development:
```bash
./scripts/start-hybrid.sh
```

This starts the backend in Docker and the frontend natively for faster iteration.

## Docstring Style (Google)

We follow **Google-style docstrings** across all Python code. This ensures consistency, improves IDE support, and enables automated documentation generation.

### Why Google Style?

- **Readable**: Natural, prose-like format that's easy to scan
- **Widely adopted**: Used by Google, TensorFlow, and many major projects
- **Tool support**: Excellent IDE autocomplete and documentation generation
- **Consistency**: Already used in 80%+ of our existing codebase

### Requirements

All code must include:

1. **Module docstrings** - Every `.py` file must have a module-level docstring
2. **Class docstrings** - Every public class must document its purpose and attributes
3. **Function/method docstrings** - All public functions/methods must document parameters, returns, and exceptions

### Exemptions

The following do NOT require docstrings:
- Test fixtures and simple test helper functions (scenario docstrings are encouraged)
- Dunder methods (`__repr__`, `__str__`, `__eq__`, etc.) unless they have complex logic
- One-line property getters without side effects
- Auto-generated Alembic migration files (`backend/alembic/versions/*.py`)

### Module Docstrings

Every module must start with a docstring describing its purpose.

#### Good Examples (from our codebase)

**Comprehensive module docstring** (`backend/app/core/exceptions.py`):
```python
"""Custom exceptions for the LLM Search Analysis API.

This module defines a hierarchy of custom exceptions with error codes and
user-friendly messages for consistent error handling across the application.
"""
```

**Concise module docstring** (`frontend/api_client.py`):
```python
"""
API Client for LLM Search Analysis Backend.

This module provides a client library for interacting with the FastAPI backend.
"""
```

#### Bad Examples

**Missing module docstring** (main.py currently has this issue):
```python
# ❌ NO docstring at all
from fastapi import FastAPI
```

**Too vague**:
```python
"""Utilities."""  # ❌ What kind of utilities? What's their purpose?
```

### Class Docstrings

Classes should document their purpose and list important attributes.

#### Good Examples (from our codebase)

**Full class with attributes** (`backend/app/core/exceptions.py`):
```python
class APIException(Exception):
  """Base exception for all API errors.

  All custom exceptions should inherit from this class to ensure
  consistent error handling and response formatting.

  Attributes:
    message: User-friendly error message
    error_code: Machine-readable error code
    status_code: HTTP status code
    details: Additional error details (optional)
  """
```

**Class with usage example** (`frontend/api_client.py`):
```python
class APIClient:
  """
  Client for interacting with the LLM Search Analysis FastAPI backend.

  Features:
  - Connection pooling for efficient HTTP requests
  - Automatic retry with exponential backoff for transient failures
  - Configurable timeouts per operation type
  - User-friendly error messages

  Example:
    >>> client = APIClient(base_url="http://localhost:8000")
    >>> providers = client.get_providers()
    >>> response = client.send_prompt(
    ...     prompt="What is AI?",
    ...     provider="openai",
    ...     model="gpt-5.1"
    ... )
  """
```

**Simple class** (`backend/app/models.py`):
```python
class Provider(Base):
  """AI provider information.

  Stores metadata about LLM providers (OpenAI, Google, Anthropic, etc.)
  including their supported models and configuration.
  """
  __tablename__ = "providers"
```

#### Bad Examples

**Missing entirely**:
```python
class MyClass:  # ❌ No docstring
  pass
```

**Too brief to be useful**:
```python
class DataProcessor:
  """Processes data."""  # ❌ What kind of data? How?
```

### Function/Method Docstrings

Functions and methods must document their parameters, return values, and exceptions.

#### Good Examples (from our codebase)

**Complete function documentation** (`frontend/api_client.py`):
```python
def send_prompt(
  self,
  prompt: str,
  provider: str,
  model: str,
  data_mode: str = "api",
  headless: bool = True
) -> Dict[str, Any]:
  """
  Send a prompt to an LLM provider and get the response.

  Args:
    prompt: The prompt text to send (1-10000 characters)
    provider: Provider name (openai, google, anthropic, chatgpt)
    model: Model identifier (e.g., "gpt-5.1", "gemini-2.5-flash")
    data_mode: Data collection mode ("api" or "network_log")
    headless: Whether to run browser in headless mode (network_log only)

  Returns:
    Dictionary containing response data with keys:
    - response_id: Unique identifier for this response
    - response_text: The LLM's response text
    - search_queries: List of search queries detected
    - sources: List of source URLs

  Raises:
    APIValidationError: If prompt/provider/model is invalid
    APIServerError: If backend or LLM API fails
    APITimeoutError: If request exceeds timeout

  Example:
    >>> response = client.send_prompt(
    ...     prompt="What is machine learning?",
    ...     provider="openai",
    ...     model="gpt-5.1"
    ... )
    >>> print(response["response_text"])
  """
```

**Utility function with examples** (`backend/app/core/utils.py`):
```python
def extract_domain(url: str) -> Optional[str]:
  """
  Extract domain from URL.

  Args:
    url: The URL to extract domain from

  Returns:
    Domain name (without www prefix) or None if invalid URL

  Examples:
    >>> extract_domain("https://www.example.com/path")
    'example.com'
    >>> extract_domain("invalid")
    None
  """
```

**Simple function (minimal sections)** (`backend/app/core/exceptions.py`):
```python
def to_dict(self) -> Dict[str, Any]:
  """Convert exception to dictionary for JSON response."""
  response = {
    "error": {
      "message": self.message,
      "code": self.error_code,
    }
  }
  return response
```

**Constructor with detailed args** (`frontend/api_client.py`):
```python
def __init__(
  self,
  base_url: str = "http://localhost:8000",
  timeout_default: float = 30.0,
  timeout_send_prompt: float = 120.0,
  max_retries: int = 3,
  pool_connections: int = 10,
  pool_maxsize: int = 20,
):
  """
  Initialize API client.

  Args:
    base_url: Base URL of the FastAPI backend (default: http://localhost:8000)
    timeout_default: Default timeout for API requests in seconds (default: 30.0)
    timeout_send_prompt: Timeout for send_prompt requests in seconds (default: 120.0)
    max_retries: Maximum number of retry attempts for transient failures (default: 3)
    pool_connections: Number of connection pools to cache (default: 10)
    pool_maxsize: Maximum number of connections to save in the pool (default: 20)
  """
```

#### Bad Examples

**Missing parameters documentation**:
```python
def calculate_metrics(responses, include_scores):
  """Calculate response metrics."""  # ❌ What are the parameters? What's returned?
  pass
```

**Vague descriptions**:
```python
def process(data: dict) -> dict:
  """Process data.

  Args:
    data: The data

  Returns:
    The result
  """  # ❌ Too vague - what kind of data? What does "process" mean?
```

**Missing exception documentation**:
```python
def get_user(user_id: int) -> User:
  """Get user by ID.

  Args:
    user_id: The user's ID

  Returns:
    User object
  """
  # ❌ Function raises UserNotFoundError but doesn't document it
  if not user:
    raise UserNotFoundError(user_id)
```

### Docstring Sections

Use these sections in your docstrings (order matters):

1. **Summary** (required) - One-line description of what it does
2. **Extended description** (optional) - Additional context, algorithm details, usage notes
3. **Args** (if parameters exist) - Document each parameter
4. **Returns** (if not None) - Describe the return value
5. **Raises** (if exceptions raised) - List possible exceptions
6. **Yields** (for generators) - Describe yielded values
7. **Example** or **Examples** (optional but encouraged) - Usage examples

### Formatting Guidelines

**One-line docstrings**:
```python
"""Do something and return a result."""
```

**Multi-line docstrings** (note the blank line after summary):
```python
"""
Summary line describing the function.

Extended description with more details. Can be multiple paragraphs
if needed.

Args:
  param1: Description of param1
  param2: Description of param2

Returns:
  Description of return value
"""
```

**Parameter descriptions**:
- Use `param_name:` followed by description (no hyphen)
- Include type information if not in type hints
- Mention defaults if relevant: `timeout: Request timeout in seconds (default: 30)`
- For complex types: `config: Configuration dict with keys 'host', 'port', 'timeout'`

**Return value descriptions**:
- Describe the semantic meaning, not just the type
- For dicts/lists, document structure: `Dictionary with keys 'id', 'name', 'status'`
- For complex objects, mention key attributes: `User object with populated profile data`

**Exception documentation**:
```python
Raises:
  ValueError: If prompt is empty or exceeds max length
  APITimeoutError: If request takes longer than specified timeout
  DatabaseError: If database query fails
```

### Docstring Quality Checklist

Before submitting a PR, verify your docstrings:

- [ ] Every `.py` file has a module docstring
- [ ] Every public class has a docstring with purpose and key attributes
- [ ] Every public function/method documents parameters, return value, and exceptions
- [ ] Examples provided for complex or unintuitive APIs
- [ ] No placeholders like "TODO" or "Fix this later"
- [ ] Docstrings match current implementation (no stale docs)
- [ ] Grammar and spelling are correct
- [ ] Lines wrapped at reasonable length (recommendation: 88 characters)

### Validation Tools

We use **Ruff** to enforce docstring standards. Use the convenient Make commands:

```bash
# Check docstring coverage and style
make docstring-check

# Auto-fix docstring formatting issues
make docstring-fix

# Run all linting (includes docstrings, code style, imports)
make lint
```

Or use Ruff directly:
```bash
# Check docstrings
ruff check --select D .

# Auto-fix some docstring issues
ruff check --select D --fix .
```

Pytest enforcement tests verify coverage:
```bash
# Backend docstring coverage
pytest backend/tests/test_docstrings.py -v

# Frontend docstring coverage
pytest frontend/tests/test_docstrings.py -v
```

## Testing Requirements

### Backend Tests

All backend changes must include tests. We maintain **95%+ test coverage**.

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

**Test requirements**:
- Unit tests for business logic
- Integration tests for API endpoints
- Contract tests for external provider interactions
- Repository tests for database operations

See `docs/backend/TESTING.md` for details.

### Frontend Tests

Frontend utilities and helpers should have tests:

```bash
pytest frontend/tests -v
```

See `docs/frontend/TESTING.md` for details.

### Pre-commit Checks

Before committing, run:
```bash
# Quick check - linting and docstrings
make lint
make docstring-check

# Run all tests
make test

# Or run individually:
make test-backend    # Backend tests with coverage
make test-frontend   # Frontend tests
```

See `make help` for all available commands.

## Pull Request Process

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Make your changes** following this guide
3. **Add tests** for new functionality
4. **Update documentation** if you change APIs or behavior
5. **Run tests and linting** locally
6. **Commit with clear messages**: Use imperative mood ("Add feature" not "Added feature")
7. **Push and create PR** against `main` branch
8. **Reference related issues** in the PR description
9. **Respond to review feedback** promptly

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

**Example**:
```
feat: add retry logic to API client

Implement exponential backoff with configurable max retries for transient
network failures. Default is 3 retries with 1-10 second backoff.

Closes #123
```

## Code Review Guidelines

### For Authors

- Keep PRs focused and reasonably sized (< 500 lines when possible)
- Provide context in PR description
- Respond to feedback constructively
- Update the PR rather than commenting "Will fix" without pushing changes

### For Reviewers

- Be kind and constructive
- Ask questions rather than demanding changes
- Approve when the code meets standards, even if you'd do it differently
- Focus on:
  - Correctness and logic errors
  - Test coverage
  - Documentation (especially docstrings)
  - Security issues
  - Performance problems

## Getting Help

- **Documentation**: Check `docs/` directory first
- **Issues**: Search existing issues before creating new ones
- **Questions**: Open a discussion or issue with the "question" label

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
