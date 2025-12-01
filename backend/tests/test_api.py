"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from app.main import app
from app.models.database import Base
from app.dependencies import get_db


# Create test database
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(
  TEST_DATABASE_URL,
  connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db():
  """Create test database and tables."""
  Base.metadata.create_all(bind=test_engine)
  yield
  Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(test_db):
  """Create test client with test database."""
  def override_get_db():
    try:
      db = TestSessionLocal()
      yield db
    finally:
      db.close()

  app.dependency_overrides[get_db] = override_get_db
  yield TestClient(app)
  app.dependency_overrides.clear()


class TestHealthEndpoints:
  """Tests for health check endpoints."""

  def test_root_endpoint(self, client):
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "LLM Search Analysis API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"
    assert data["docs"] == "/docs"

  def test_health_check_endpoint(self, client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert data["database"] == "connected"


class TestProvidersEndpoints:
  """Tests for provider endpoints."""

  def test_get_providers(self, client):
    """Test GET /api/v1/providers returns list of providers."""
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # Should have at least one provider (OpenAI with API key)
    if len(data) > 0:
      provider = data[0]
      assert "name" in provider
      assert "display_name" in provider
      assert "is_active" in provider
      assert "supported_models" in provider
      assert isinstance(provider["supported_models"], list)

  def test_get_all_models(self, client):
    """Test GET /api/v1/providers/models returns list of models."""
    response = client.get("/api/v1/providers/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # Should have at least some models if providers are configured
    if len(data) > 0:
      assert all(isinstance(model, str) for model in data)


class TestInteractionsEndpoints:
  """Tests for interactions endpoints."""

  @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
  def test_send_prompt_success(self, mock_send_prompt, client):
    """Test POST /api/v1/interactions/send creates interaction."""
    # Mock the provider response
    from app.services.providers.openai_provider import ProviderResponse, SearchQuery, Source, Citation

    mock_send_prompt.return_value = ProviderResponse(
      provider="openai",
      model="gpt-5.1",
      response_text="Test response",
      search_queries=[
        SearchQuery(
          query="test query",
          sources=[
            Source(
              url="https://example.com",
              title="Example",
              domain="example.com",
              rank=1
            )
          ],
          timestamp="2024-01-01T00:00:00Z",
          order_index=0
        )
      ],
      sources=[
        Source(
          url="https://example.com",
          title="Example",
          domain="example.com",
          rank=1
        )
      ],
      citations=[
        Citation(
          url="https://example.com",
          title="Example",
          rank=1
        )
      ],
      response_time_ms=1000,
      data_source="api",
      raw_response={}
    )

    response = client.post(
      "/api/v1/interactions/send",
      json={
        "prompt": "Test prompt",
        "provider": "openai",
        "model": "gpt-5.1"
      }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response_text"] == "Test response"
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-5.1"
    assert "interaction_id" in data
    assert len(data["search_queries"]) == 1
    assert len(data["citations"]) == 1

  def test_send_prompt_validation_error(self, client):
    """Test POST /api/v1/interactions/send with invalid data."""
    response = client.post(
      "/api/v1/interactions/send",
      json={
        "prompt": "",  # Empty prompt should fail validation
        "provider": "openai",
        "model": "gpt-5.1"
      }
    )

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Request validation failed" in data["error"]["message"]

  def test_send_prompt_unsupported_model(self, client):
    """Test POST /api/v1/interactions/send with unsupported model."""
    response = client.post(
      "/api/v1/interactions/send",
      json={
        "prompt": "Test prompt",
        "provider": "openai",
        "model": "unsupported-model-xyz"
      }
    )

    # Unsupported model returns 400 Bad Request
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "unsupported-model-xyz" in data["error"]["message"]

  def test_get_recent_interactions_empty(self, client):
    """Test GET /api/v1/interactions/recent with no interactions."""
    response = client.get("/api/v1/interactions/recent")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0

  @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
  def test_get_recent_interactions_with_data(self, mock_send_prompt, client):
    """Test GET /api/v1/interactions/recent returns interactions."""
    # Mock the provider response
    from app.services.providers.openai_provider import ProviderResponse, SearchQuery, Source, Citation

    mock_send_prompt.return_value = ProviderResponse(
      provider="openai",
      model="gpt-5.1",
      response_text="Test response",
      search_queries=[],
      sources=[],
      citations=[],
      response_time_ms=1000,
      data_source="api",
      raw_response={}
    )

    # Create an interaction first
    client.post(
      "/api/v1/interactions/send",
      json={"prompt": "Test prompt", "provider": "openai", "model": "gpt-5.1"}
    )

    # Get recent interactions
    response = client.get("/api/v1/interactions/recent")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1

    interaction = data[0]
    assert "interaction_id" in interaction
    assert interaction["provider"] == "openai"
    assert interaction["model"] == "gpt-5.1"
    assert "created_at" in interaction

  def test_get_recent_interactions_with_limit(self, client):
    """Test GET /api/v1/interactions/recent respects limit parameter."""
    response = client.get("/api/v1/interactions/recent?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10

  def test_get_recent_interactions_with_data_source_filter(self, client):
    """Test GET /api/v1/interactions/recent filters by data source."""
    response = client.get("/api/v1/interactions/recent?data_source=api")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # All returned interactions should have data_source="api"
    for interaction in data:
      assert interaction["data_source"] == "api"

  def test_get_interaction_details_not_found(self, client):
    """Test GET /api/v1/interactions/{id} with non-existent ID."""
    response = client.get("/api/v1/interactions/99999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "99999" in data["error"]["message"]

  @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
  def test_get_interaction_details_success(self, mock_send_prompt, client):
    """Test GET /api/v1/interactions/{id} returns full details."""
    # Mock the provider response
    from app.services.providers.openai_provider import ProviderResponse, SearchQuery, Source, Citation

    mock_send_prompt.return_value = ProviderResponse(
      provider="openai",
      model="gpt-5.1",
      response_text="Test response",
      search_queries=[
        SearchQuery(
          query="test query",
          sources=[
            Source(
              url="https://example.com",
              title="Example",
              domain="example.com",
              rank=1
            )
          ],
          timestamp="2024-01-01T00:00:00Z",
          order_index=0
        )
      ],
      sources=[
        Source(
          url="https://example.com",
          title="Example",
          domain="example.com",
          rank=1
        )
      ],
      citations=[
        Citation(
          url="https://example.com",
          title="Example",
          rank=1
        )
      ],
      response_time_ms=1000,
      data_source="api",
      raw_response={}
    )

    # Create an interaction
    create_response = client.post(
      "/api/v1/interactions/send",
      json={"prompt": "Test prompt", "provider": "openai", "model": "gpt-5.1"}
    )
    interaction_id = create_response.json()["interaction_id"]

    # Get interaction details
    response = client.get(f"/api/v1/interactions/{interaction_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["interaction_id"] == interaction_id
    assert data["response_text"] == "Test response"
    assert len(data["search_queries"]) == 1
    assert len(data["citations"]) == 1

  def test_delete_interaction_not_found(self, client):
    """Test DELETE /api/v1/interactions/{id} with non-existent ID."""
    response = client.delete("/api/v1/interactions/99999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "99999" in data["error"]["message"]

  @patch('app.services.providers.openai_provider.OpenAIProvider.send_prompt')
  def test_delete_interaction_success(self, mock_send_prompt, client):
    """Test DELETE /api/v1/interactions/{id} deletes interaction."""
    # Mock the provider response
    from app.services.providers.openai_provider import ProviderResponse

    mock_send_prompt.return_value = ProviderResponse(
      provider="openai",
      model="gpt-5.1",
      response_text="Test response",
      search_queries=[],
      sources=[],
      citations=[],
      response_time_ms=1000,
      data_source="api",
      raw_response={}
    )

    # Create an interaction
    create_response = client.post(
      "/api/v1/interactions/send",
      json={"prompt": "Test prompt", "provider": "openai", "model": "gpt-5.1"}
    )
    interaction_id = create_response.json()["interaction_id"]

    # Delete the interaction
    response = client.delete(f"/api/v1/interactions/{interaction_id}")
    assert response.status_code == 204

    # Verify it's deleted
    get_response = client.get(f"/api/v1/interactions/{interaction_id}")
    assert get_response.status_code == 404


class TestErrorHandling:
  """Tests for error handling."""

  def test_404_on_unknown_endpoint(self, client):
    """Test 404 error on unknown endpoint."""
    response = client.get("/api/v1/unknown-endpoint")
    assert response.status_code == 404

  def test_validation_error_format(self, client):
    """Test validation errors return consistent format."""
    response = client.post(
      "/api/v1/interactions/send",
      json={"invalid": "data"}  # Missing required fields
    )

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Request validation failed" in data["error"]["message"]
    assert "errors" in data["error"]["details"]
