"""Tests for middleware components."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from app.core.middleware import (
  LoggingMiddleware,
  CorrelationIDMiddleware,
  get_correlation_id,
)


class TestLoggingMiddleware:
  """Tests for LoggingMiddleware request/response logging."""

  @pytest.fixture
  def app_with_logging(self):
    """Create test app with logging middleware."""
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/test")
    async def test_endpoint():
      return {"message": "success"}

    @app.get("/test-error")
    async def test_error_endpoint():
      raise ValueError("Test error")

    @app.get("/test-correlation")
    async def test_correlation_endpoint(request: Request):
      return {"correlation_id": get_correlation_id(request)}

    return app

  def test_request_with_correlation_id_header(self, app_with_logging):
    """Test that custom correlation ID is preserved."""
    client = TestClient(app_with_logging)
    custom_id = "test-correlation-12345"

    response = client.get(
      "/test",
      headers={"X-Correlation-ID": custom_id}
    )

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_id

  def test_request_without_correlation_id_generates_one(self, app_with_logging):
    """Test that correlation ID is generated if not provided."""
    client = TestClient(app_with_logging)

    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0

  def test_correlation_id_available_in_endpoint(self, app_with_logging):
    """Test that correlation ID is available via get_correlation_id."""
    client = TestClient(app_with_logging)
    custom_id = "endpoint-test-123"

    response = client.get(
      "/test-correlation",
      headers={"X-Correlation-ID": custom_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["correlation_id"] == custom_id

  def test_middleware_handles_exceptions(self, app_with_logging, caplog):
    """Test that middleware logs exceptions and re-raises them."""
    import logging
    client = TestClient(app_with_logging, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR):
      response = client.get("/test-error")

    # Should get 500 error
    assert response.status_code == 500

    # Verify exception was logged with ERROR level
    assert any(
      "Request failed" in record.message and record.levelname == "ERROR"
      for record in caplog.records
    )

  def test_success_responses_logged_at_info_level(self, app_with_logging, caplog):
    """Test that 2xx responses are logged at info level."""
    import logging
    client = TestClient(app_with_logging)

    with caplog.at_level(logging.INFO):
      response = client.get("/test")

    assert response.status_code == 200

    # Verify successful request was logged
    assert any("Request completed" in record.message and record.levelname == "INFO" for record in caplog.records)


class TestCorrelationIDMiddleware:
  """Tests for lightweight CorrelationIDMiddleware."""

  @pytest.fixture
  def app_with_correlation(self):
    """Create test app with correlation ID middleware."""
    app = FastAPI()
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    async def test_endpoint():
      return {"message": "success"}

    @app.get("/test-correlation")
    async def test_correlation_endpoint(request: Request):
      return {"correlation_id": get_correlation_id(request)}

    return app

  def test_correlation_id_added_to_response(self, app_with_correlation):
    """Test that correlation ID is added to response headers."""
    client = TestClient(app_with_correlation)

    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers

  def test_correlation_id_preserved_from_request(self, app_with_correlation):
    """Test that provided correlation ID is preserved."""
    client = TestClient(app_with_correlation)
    custom_id = "custom-correlation-abc"

    response = client.get(
      "/test",
      headers={"X-Correlation-ID": custom_id}
    )

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_id

  def test_correlation_id_available_in_request_state(self, app_with_correlation):
    """Test that correlation ID is accessible via request state."""
    client = TestClient(app_with_correlation)
    custom_id = "state-test-xyz"

    response = client.get(
      "/test-correlation",
      headers={"X-Correlation-ID": custom_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["correlation_id"] == custom_id


class TestGetCorrelationId:
  """Tests for get_correlation_id helper function."""

  def test_get_correlation_id_from_request_state(self):
    """Test extracting correlation ID from request state."""
    # Create a mock request with correlation_id in state
    from unittest.mock import Mock
    request = Mock()
    request.state.correlation_id = "test-id-123"

    correlation_id = get_correlation_id(request)

    assert correlation_id == "test-id-123"

  def test_get_correlation_id_returns_default_when_missing(self):
    """Test that default is returned when correlation ID is not in state."""
    from unittest.mock import Mock
    request = Mock()
    # Remove correlation_id attribute if it exists
    request.state = Mock(spec=[])

    correlation_id = get_correlation_id(request)

    assert correlation_id == "no-correlation-id"
