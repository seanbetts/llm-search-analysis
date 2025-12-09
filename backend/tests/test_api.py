"""Integration tests for FastAPI endpoints."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.schemas.responses import BatchStatus, SendPromptResponse
from app.dependencies import get_batch_service, get_db
from app.main import app
from app.models.database import Base


# Create test database
TEST_DB_PATH = Path(__file__).resolve().parent / "data" / "test.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
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
    assert data["provider"] == "OpenAI"  # API returns display name
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

    # Unsupported model returns 422 Unprocessable Entity (Pydantic validation error)
    assert response.status_code == 422
    data = response.json()
    # Error is wrapped in custom error handler format


class _StubBatchService:
  """Simple stub used to test batch endpoints."""

  def __init__(self):
    result = SendPromptResponse(
      prompt="Prompt A",
      response_text="Batch result",
      search_queries=[],
      citations=[],
      all_sources=[],
      provider="openai",
      model="gpt-5.1",
      model_display_name="GPT-5.1",
      response_time_ms=1500,
      data_source="api",
      sources_found=0,
      sources_used=0,
      avg_rank=None,
      extra_links_count=0,
      interaction_id=123,
      created_at=datetime.utcnow(),
      raw_response={},
    )
    self.start_status = BatchStatus(
      batch_id="stub-batch",
      total_tasks=2,
      completed_tasks=0,
      failed_tasks=0,
      status="processing",
      results=[],
      errors=[],
      started_at=datetime.utcnow(),
    )
    self.final_status = BatchStatus(
      batch_id="stub-batch",
      total_tasks=2,
      completed_tasks=2,
      failed_tasks=0,
      status="completed",
      results=[result],
      errors=[],
      started_at=datetime.utcnow(),
      completed_at=datetime.utcnow(),
    )
    self.last_request = None
    self.last_status_batch_id = None

  async def start_batch(self, request):
    self.last_request = request
    return self.start_status

  def get_status(self, batch_id: str):
    self.last_status_batch_id = batch_id
    return self.final_status


class TestBatchEndpoints:
  """Tests for backend-managed batch lifecycle."""

  def test_batch_start_and_status(self, client):
    """POST /interactions/batch and GET status should use batch service."""
    stub = _StubBatchService()
    app.dependency_overrides[get_batch_service] = lambda: stub
    try:
      payload = {
        "prompts": ["Prompt A", "Prompt B"],
        "models": ["gpt-5.1"],
      }
      response = client.post("/api/v1/interactions/batch", json=payload)
      assert response.status_code == 202
      body = response.json()
      assert body["batch_id"] == "stub-batch"
      assert stub.last_request.prompts == payload["prompts"]
      assert stub.last_request.models == payload["models"]

      status_response = client.get("/api/v1/interactions/batch/stub-batch")
      assert status_response.status_code == 200
      status_body = status_response.json()
      assert status_body["status"] == "completed"
      assert status_body["completed_tasks"] == 2
      assert len(status_body["results"]) == 1
      assert stub.last_status_batch_id == "stub-batch"
    finally:
      app.dependency_overrides.pop(get_batch_service, None)

  def test_get_recent_interactions_empty(self, client):
    """Test GET /api/v1/interactions/recent with no interactions."""
    response = client.get("/api/v1/interactions/recent")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data["items"] == []
    assert data["pagination"]["total_items"] == 0

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
    assert isinstance(data, dict)
    assert len(data["items"]) == 1

    interaction = data["items"][0]
    assert "interaction_id" in interaction
    assert interaction["provider"] == "OpenAI"  # API returns display name
    assert interaction["model"] == "gpt-5.1"
    assert "created_at" in interaction

  def test_get_recent_interactions_with_limit(self, client):
    """Test GET /api/v1/interactions/recent respects page_size parameter."""
    response = client.get("/api/v1/interactions/recent?page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data["items"]) <= 10
    assert data["pagination"]["page_size"] == 10

  def test_get_recent_interactions_with_data_source_filter(self, client):
    """Test GET /api/v1/interactions/recent filters by data source."""
    response = client.get("/api/v1/interactions/recent?data_source=api")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    # All returned interactions should have data_source="api"
    for interaction in data["items"]:
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

  def test_save_network_log_interaction(self, client):
    """Test POST /api/v1/interactions/save-network-log persists network log data."""
    payload = {
      "provider": "openai",
      "model": "chatgpt-free",
      "prompt": "Capture ChatGPT conversation",
      "response_text": "Network log response body",
      "search_queries": [
        {
          "query": "latest ai news",
          "order_index": 0,
          "sources": [
            {
              "url": "https://example.com/article",
              "title": "Example Article",
              "domain": "example.com",
              "rank": 1,
              "snippet_text": "Example snippet",
              "pub_date": "2024-01-01"
            }
          ]
        }
      ],
      "sources": [
        {
          "url": "https://example.com/article",
          "title": "Example Article",
          "domain": "example.com",
          "rank": 1,
          "snippet_text": "Example snippet",
          "pub_date": "2024-01-01"
        }
      ],
      "citations": [
        {
          "url": "https://example.com/article",
          "title": "Example Article",
          "rank": 1,
          "snippet_used": "Example snippet"
        }
      ],
      "response_time_ms": 1200,
      "extra_links_count": 1,
      "raw_response": {"mode": "network_log"}
    }

    response = client.post("/api/v1/interactions/save-network-log", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["interaction_id"] is not None
    assert data["data_source"] == "network_log"
    assert data["prompt"] == payload["prompt"]
    assert len(data["all_sources"]) == 1

    recent = client.get("/api/v1/interactions/recent?data_source=network_log")
    assert recent.status_code == 200
    recent_data = recent.json()
    assert any(item["prompt"] == payload["prompt"] for item in recent_data["items"])

  def test_save_network_log_invalid_payload(self, client):
    """Invalid network log payloads should return 422 with detail."""
    payload = {
      "provider": "openai",
      "model": "chatgpt-free",
      "prompt": "Invalid data",
      "response_text": "Body",
      "search_queries": [
        {
          # Missing required query field
          "sources": []
        }
      ],
      "sources": [],
      "citations": [],
      "response_time_ms": 500,
      "raw_response": {}
    }

    response = client.post("/api/v1/interactions/save-network-log", json=payload)
    assert response.status_code == 422
    error = response.json()
    assert "search_queries" in str(error)

  def test_export_interaction_markdown_success(self, client):
    """Test GET /api/v1/interactions/{id}/export/markdown returns markdown."""
    payload = {
      "provider": "openai",
      "model": "chatgpt-free",
      "prompt": "Export me",
      "response_text": "Export response body",
      "search_queries": [],
      "sources": [
        {
          "url": "https://example.com/export",
          "title": "Export Source",
          "domain": "example.com",
          "rank": 1,
          "snippet_text": "Snippet"
        }
      ],
      "citations": [],
      "response_time_ms": 900,
      "extra_links_count": 0,
      "raw_response": {"mode": "network_log"}
    }
    create_resp = client.post("/api/v1/interactions/save-network-log", json=payload)
    interaction_id = create_resp.json()["interaction_id"]

    export_resp = client.get(f"/api/v1/interactions/{interaction_id}/export/markdown")
    assert export_resp.status_code == 200
    markdown = export_resp.text
    assert "# Interaction" in markdown
    assert "## Prompt" in markdown
    assert payload["prompt"] in markdown

  def test_export_interaction_markdown_not_found(self, client):
    """Test GET /api/v1/interactions/{id}/export/markdown returns 404 for missing ID."""
    response = client.get("/api/v1/interactions/999999/export/markdown")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


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
