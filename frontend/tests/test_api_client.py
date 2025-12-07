"""Unit tests for API Client."""

import pytest
import httpx
import respx
from frontend.api_client import (
  APIClient,
  APIClientError,
  APITimeoutError,
  APIConnectionError,
  APIValidationError,
  APINotFoundError,
  APIServerError,
)


@pytest.fixture
def client():
  """Create API client for testing."""
  return APIClient(base_url="http://testserver")


@pytest.fixture
def mock_api():
  """Create mock API with respx."""
  with respx.mock(base_url="http://testserver") as respx_mock:
    yield respx_mock


class TestAPIClientInitialization:
  """Tests for API client initialization."""

  def test_init_with_defaults(self):
    """Test initialization with default values."""
    client = APIClient()
    assert client.base_url == "http://localhost:8000"
    assert client.timeout_default == 30.0
    assert client.timeout_send_prompt == 120.0
    assert client.max_retries == 3
    client.close()

  def test_init_with_custom_values(self):
    """Test initialization with custom values."""
    client = APIClient(
      base_url="http://custom:9000",
      timeout_default=60.0,
      timeout_send_prompt=180.0,
      max_retries=5
    )
    assert client.base_url == "http://custom:9000"
    assert client.timeout_default == 60.0
    assert client.timeout_send_prompt == 180.0
    assert client.max_retries == 5
    client.close()

  def test_base_url_trailing_slash_removed(self):
    """Test that trailing slash is removed from base_url."""
    client = APIClient(base_url="http://testserver/")
    assert client.base_url == "http://testserver"
    client.close()


class TestHealthCheck:
  """Tests for health check endpoint."""

  def test_health_check_success(self, client, mock_api):
    """Test successful health check."""
    mock_api.get("/health").mock(return_value=httpx.Response(
      200,
      json={"status": "healthy", "version": "1.0.0", "database": "connected"}
    ))

    result = client.health_check()
    assert result["status"] == "healthy"
    assert result["version"] == "1.0.0"
    assert result["database"] == "connected"

  def test_health_check_unhealthy(self, client, mock_api):
    """Test unhealthy status response."""
    mock_api.get("/health").mock(return_value=httpx.Response(
      503,
      json={"status": "unhealthy", "database": "error"}
    ))

    with pytest.raises(APIServerError) as exc_info:
      client.health_check()
    assert "Server error" in str(exc_info.value)


class TestGetProviders:
  """Tests for get providers endpoint."""

  def test_get_providers_success(self, client, mock_api):
    """Test getting list of providers."""
    mock_response = [
      {
        "name": "openai",
        "display_name": "OpenAI",
        "is_active": True,
        "supported_models": ["gpt-5.1", "gpt-5-mini"]
      }
    ]

    mock_api.get("/api/v1/providers").mock(return_value=httpx.Response(
      200,
      json=mock_response
    ))

    result = client.get_providers()
    assert len(result) == 1
    assert result[0]["name"] == "openai"
    assert result[0]["is_active"] is True
    assert len(result[0]["supported_models"]) == 2

  def test_get_providers_empty(self, client, mock_api):
    """Test getting providers when none are configured."""
    mock_api.get("/api/v1/providers").mock(return_value=httpx.Response(
      200,
      json=[]
    ))

    result = client.get_providers()
    assert result == []


class TestGetModels:
  """Tests for get models endpoint."""

  def test_get_models_success(self, client, mock_api):
    """Test getting list of all models."""
    mock_response = ["gpt-5.1", "gpt-5-mini", "gemini-2.5-flash"]

    mock_api.get("/api/v1/providers/models").mock(return_value=httpx.Response(
      200,
      json=mock_response
    ))

    result = client.get_models()
    assert len(result) == 3
    assert "gpt-5.1" in result
    assert "gemini-2.5-flash" in result


class TestSendPrompt:
  """Tests for send prompt endpoint."""

  def test_send_prompt_success(self, client, mock_api):
    """Test sending a prompt successfully."""
    mock_response = {
      "interaction_id": 123,
      "response_text": "Test response",
      "provider": "openai",
      "model": "gpt-5.1",
      "search_queries": [],
      "citations": [],
      "response_time_ms": 1000
    }

    mock_api.post("/api/v1/interactions/send").mock(return_value=httpx.Response(
      200,
      json=mock_response
    ))

    result = client.send_prompt(
      prompt="Test prompt",
      provider="openai",
      model="gpt-5.1"
    )

    assert result["interaction_id"] == 123
    assert result["response_text"] == "Test response"
    assert result["provider"] == "openai"

  def test_send_prompt_validation_error(self, client, mock_api):
    """Test validation error on send prompt."""
    mock_api.post("/api/v1/interactions/send").mock(return_value=httpx.Response(
      422,
      json={
        "status": "error",
        "message": "Validation error",
        "detail": [{"loc": ["body", "prompt"], "msg": "String should have at least 1 character"}]
      }
    ))

    with pytest.raises(APIValidationError) as exc_info:
      client.send_prompt(prompt="", provider="openai", model="gpt-5.1")
    assert "Validation error" in str(exc_info.value)

  def test_send_prompt_bad_model(self, client, mock_api):
    """Test sending prompt with unsupported model."""
    mock_api.post("/api/v1/interactions/send").mock(return_value=httpx.Response(
      400,
      json={"detail": "Model 'unsupported' is not supported"}
    ))

    with pytest.raises(APIClientError) as exc_info:
      client.send_prompt(
        prompt="Test",
        provider="openai",
        model="unsupported"
      )
    assert "not supported" in str(exc_info.value)


class TestGetRecentInteractions:
  """Tests for get recent interactions endpoint."""

  def test_get_recent_interactions_success(self, client, mock_api):
    """Test getting recent interactions."""
    mock_response = {
      "items": [
        {
          "interaction_id": 1,
          "prompt": "Test prompt 1",
          "provider": "openai",
          "model": "gpt-5.1",
          "created_at": "2024-01-01T00:00:00Z"
        },
        {
          "interaction_id": 2,
          "prompt": "Test prompt 2",
          "provider": "google",
          "model": "gemini-2.5-flash",
          "created_at": "2024-01-02T00:00:00Z"
        }
      ],
      "pagination": {
        "page": 1,
        "page_size": 10,
        "total_items": 2,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False
      }
    }

    mock_api.get("/api/v1/interactions/recent").mock(return_value=httpx.Response(
      200,
      json=mock_response
    ))

    result = client.get_recent_interactions(page=1, page_size=10)
    assert "items" in result
    assert len(result["items"]) == 2
    assert result["items"][0]["interaction_id"] == 1
    assert result["items"][1]["provider"] == "google"
    assert result["pagination"]["page_size"] == 10

  def test_get_recent_interactions_with_filter(self, client, mock_api):
    """Test getting recent interactions with data source filter."""
    mock_response = {
      "items": [
        {
          "interaction_id": 1,
          "prompt": "Test",
          "data_source": "api"
        }
      ],
      "pagination": {
        "page": 1,
        "page_size": 5,
        "total_items": 1,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False
      }
    }

    mock_api.get("/api/v1/interactions/recent").mock(return_value=httpx.Response(
      200,
      json=mock_response
    ))

    result = client.get_recent_interactions(page=1, page_size=5, data_source="api")
    assert len(result["items"]) == 1
    assert result["items"][0]["data_source"] == "api"
    assert result["pagination"]["page_size"] == 5


class TestGetInteraction:
  """Tests for get interaction details endpoint."""

  def test_get_interaction_success(self, client, mock_api):
    """Test getting interaction details."""
    mock_response = {
      "interaction_id": 123,
      "prompt": "Test prompt",
      "response_text": "Full response",
      "provider": "openai",
      "model": "gpt-5.1",
      "search_queries": [{"query": "test", "sources": []}],
      "citations": []
    }

    mock_api.get("/api/v1/interactions/123").mock(return_value=httpx.Response(
      200,
      json=mock_response
    ))

    result = client.get_interaction(123)
    assert result["interaction_id"] == 123
    assert result["response_text"] == "Full response"
    assert len(result["search_queries"]) == 1

  def test_get_interaction_not_found(self, client, mock_api):
    """Test getting non-existent interaction."""
    mock_api.get("/api/v1/interactions/99999").mock(return_value=httpx.Response(
      404,
      json={"detail": "Interaction 99999 not found"}
    ))

    with pytest.raises(APINotFoundError) as exc_info:
      client.get_interaction(99999)
    assert "not found" in str(exc_info.value)


class TestDeleteInteraction:
  """Tests for delete interaction endpoint."""

  def test_delete_interaction_success(self, client, mock_api):
    """Test deleting interaction."""
    mock_api.delete("/api/v1/interactions/123").mock(return_value=httpx.Response(
      204
    ))

    result = client.delete_interaction(123)
    assert result is True

  def test_delete_interaction_not_found(self, client, mock_api):
    """Test deleting non-existent interaction."""
    mock_api.delete("/api/v1/interactions/99999").mock(return_value=httpx.Response(
      404,
      json={"detail": "Interaction 99999 not found"}
    ))

    with pytest.raises(APINotFoundError) as exc_info:
      client.delete_interaction(99999)
    assert "not found" in str(exc_info.value)


class TestErrorHandling:
  """Tests for error handling."""

  def test_timeout_error(self, client, mock_api):
    """Test timeout error handling."""
    mock_api.get("/health").mock(side_effect=httpx.TimeoutException("Connection timed out"))

    with pytest.raises(APITimeoutError) as exc_info:
      client.health_check()
    assert "timed out" in str(exc_info.value).lower()

  def test_connection_error(self, client, mock_api):
    """Test connection error handling."""
    mock_api.get("/health").mock(side_effect=httpx.ConnectError("Connection refused"))

    with pytest.raises(APIConnectionError) as exc_info:
      client.health_check()
    assert "connect" in str(exc_info.value).lower()

  def test_server_error_500(self, client, mock_api):
    """Test 500 server error handling."""
    mock_api.get("/api/v1/providers").mock(return_value=httpx.Response(
      500,
      json={"detail": "Internal server error"}
    ))

    with pytest.raises(APIServerError) as exc_info:
      client.get_providers()
    assert "Server error" in str(exc_info.value)

  def test_generic_http_error(self, client, mock_api):
    """Test generic HTTP error handling."""
    mock_api.get("/health").mock(return_value=httpx.Response(
      403,
      json={"detail": "Forbidden"}
    ))

    with pytest.raises(APIClientError) as exc_info:
      client.health_check()
    assert "403" in str(exc_info.value)


class TestClientCleanup:
  """Tests for client cleanup."""

  def test_explicit_close(self):
    """Test explicit client close."""
    client = APIClient()
    client.close()
    # Should not raise any errors

  def test_context_manager_style(self):
    """Test using client in context manager style."""
    client = APIClient()
    try:
      # Use client
      pass
    finally:
      client.close()
    # Should not raise any errors


class TestSaveNetworkLog:
  """Tests for save_network_log endpoint."""

  def test_save_network_log_success(self, client, mock_api):
    """Posting network log data should return saved interaction info."""
    mock_api.post("/api/v1/interactions/save-network-log").mock(return_value=httpx.Response(
      201,
      json={"interaction_id": 42, "data_source": "network_log"}
    ))

    payload = {
      "provider": "openai",
      "model": "chatgpt-free",
      "prompt": "Captured prompt",
      "response_text": "Captured response",
      "search_queries": [],
      "sources": [],
      "citations": [],
      "response_time_ms": 1200,
      "raw_response": {"mode": "network_log"},
      "extra_links_count": 1,
    }
    result = client.save_network_log(**payload)
    assert result["interaction_id"] == 42
    assert result["data_source"] == "network_log"

  def test_save_network_log_validation_error(self, client, mock_api):
    """Validation errors should raise APIValidationError."""
    mock_api.post("/api/v1/interactions/save-network-log").mock(return_value=httpx.Response(
      422,
      json={"detail": "Missing prompt"}
    ))

    with pytest.raises(APIValidationError):
      client.save_network_log(
        provider="openai",
        model="chatgpt-free",
        prompt="",
        response_text="",
        search_queries=[],
        sources=[],
        citations=[],
        response_time_ms=500,
      )


class TestExportInteractionMarkdown:
  """Tests for export_interaction_markdown helper."""

  def test_export_success(self, client, mock_api):
    """Successful export should return markdown text."""
    mock_api.get("/api/v1/interactions/123/export/markdown").mock(return_value=httpx.Response(
      200,
      text="# Interaction 123"
    ))

    markdown = client.export_interaction_markdown(123)
    assert markdown.startswith("# Interaction 123")

  def test_export_not_found(self, client, mock_api):
    """Missing interaction should raise APINotFoundError."""
    mock_api.get("/api/v1/interactions/999/export/markdown").mock(return_value=httpx.Response(
      404,
      text="Not Found"
    ))

    with pytest.raises(APINotFoundError):
      client.export_interaction_markdown(999)
