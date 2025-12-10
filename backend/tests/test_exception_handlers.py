"""Tests for global exception handlers in main.py."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
  APIException,
  DatabaseError,
  InvalidRequestError,
  ResourceNotFoundError,
  ValidationError,
)


class TestExceptionHandlers:
  """Tests for global exception handlers."""

  @pytest.fixture
  def test_app(self):
    """Create a minimal test app with exception handlers."""
    from app.main import (
      api_exception_handler,
      database_exception_handler,
      global_exception_handler,
    )

    app = FastAPI()

    # Add exception handlers
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Add test endpoints that raise different exceptions
    @app.get("/api-exception")
    async def raise_api_exception():
      raise ValidationError(
        message="Test validation error",
        details={"field": "test"}
      )

    @app.get("/resource-not-found")
    async def raise_resource_not_found():
      raise ResourceNotFoundError(
        resource_type="TestResource",
        resource_id="123"
      )

    @app.get("/invalid-request")
    async def raise_invalid_request():
      raise InvalidRequestError("Invalid request test")

    @app.get("/database-error")
    async def raise_database_error():
      raise SQLAlchemyError("Database connection failed")

    @app.get("/general-exception")
    async def raise_general_exception():
      raise ValueError("Unexpected error")

    @app.get("/database-custom-error")
    async def raise_database_custom():
      raise DatabaseError(
        message="Custom database error",
        details={"table": "users"}
      )

    return app

  def test_api_exception_handler_validation_error(self, test_app):
    """Test APIException handler for ValidationError."""
    client = TestClient(test_app)

    response = client.get("/api-exception")

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Test validation error" in data["error"]["message"]
    assert data["error"]["details"]["field"] == "test"

  def test_api_exception_handler_resource_not_found(self, test_app):
    """Test APIException handler for ResourceNotFoundError."""
    client = TestClient(test_app)

    response = client.get("/resource-not-found")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "TestResource" in data["error"]["message"]
    assert "123" in data["error"]["message"]

  def test_api_exception_handler_invalid_request(self, test_app):
    """Test APIException handler for InvalidRequestError."""
    client = TestClient(test_app)

    response = client.get("/invalid-request")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "Invalid request test" in data["error"]["message"]

  def test_database_exception_handler(self, test_app):
    """Test database exception handler for SQLAlchemyError."""
    client = TestClient(test_app)

    response = client.get("/database-error")

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "DATABASE_ERROR"
    assert "database error" in data["error"]["message"].lower()

  def test_database_custom_error_handler(self, test_app):
    """Test database exception handler for custom DatabaseError."""
    client = TestClient(test_app)

    response = client.get("/database-custom-error")

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "DATABASE_ERROR"
    assert "Custom database error" in data["error"]["message"]

  def test_global_exception_handler(self, test_app):
    """Test global exception handler for unexpected exceptions."""
    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.get("/general-exception")

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "unexpected error" in data["error"]["message"].lower()


class TestHealthCheckWithDatabaseError:
  """Tests for health check endpoint with database errors."""

  def test_health_check_database_failure(self):
    """Test health check returns 503 when database is unavailable."""
    from unittest.mock import MagicMock, patch

    from app.main import app

    client = TestClient(app)

    # Mock the database engine to raise an exception
    with patch('app.main.engine') as mock_engine:
      mock_conn = MagicMock()
      mock_conn.execute.side_effect = Exception("Connection refused")
      mock_engine.connect.return_value.__enter__.return_value = mock_conn

      response = client.get("/health")

      assert response.status_code == 503
      data = response.json()
      assert data["status"] == "unhealthy"
      assert data["database"] == "error"
      assert "error" in data
