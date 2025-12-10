"""Tests for ProviderService."""

from unittest.mock import Mock, patch

import pytest

from app.services.provider_service import ProviderService
from app.services.providers.openai_provider import Citation, ProviderResponse, SearchQuery, Source


class TestProviderService:
  """Tests for ProviderService functionality."""

  @pytest.fixture
  def mock_interaction_service(self):
    """Create mock interaction service."""
    return Mock()

  @pytest.fixture
  def service(self, mock_interaction_service):
    """Create ProviderService with mocked dependencies."""
    return ProviderService(mock_interaction_service)

  def test_get_api_keys(self, service):
    """Test _get_api_keys returns dictionary of API keys."""
    api_keys = service._get_api_keys()

    assert isinstance(api_keys, dict)
    assert "openai" in api_keys
    assert "google" in api_keys
    assert "anthropic" in api_keys

  def test_get_available_providers_with_keys(self, service):
    """Test get_available_providers returns providers with configured keys."""
    with patch.object(service, '_get_api_keys', return_value={
      "openai": "test-key",
      "google": None,
      "anthropic": None,
    }):
      providers = service.get_available_providers()

      # Should only return OpenAI since only it has an API key
      assert len(providers) == 1
      assert providers[0].name == "openai"
      assert providers[0].display_name == "OpenAI"
      assert providers[0].is_active is True
      assert "gpt-5.1" in providers[0].supported_models

  def test_get_available_providers_all_keys(self, service):
    """Test get_available_providers with all keys configured."""
    with patch.object(service, '_get_api_keys', return_value={
      "openai": "test-key-1",
      "google": "test-key-2",
      "anthropic": "test-key-3",
    }):
      providers = service.get_available_providers()

      assert len(providers) == 3
      provider_names = [p.name for p in providers]
      assert "openai" in provider_names
      assert "google" in provider_names
      assert "anthropic" in provider_names

  def test_get_available_models(self, service):
    """Test get_available_models returns list of model IDs."""
    with patch.object(service, '_get_api_keys', return_value={
      "openai": "test-key",
      "google": None,
      "anthropic": None,
    }):
      models = service.get_available_models()

      assert isinstance(models, list)
      # Should have OpenAI models
      assert "gpt-5.1" in models
      assert "gpt-5-mini" in models
      # Should not have Google/Anthropic models
      assert "gemini-2.5-flash" not in models
      assert "claude-sonnet-4-5-20250929" not in models

  def test_get_provider_for_model_valid(self, service):
    """Test get_provider_for_model returns correct provider."""
    assert service.get_provider_for_model("gpt-5.1") == "openai"
    assert service.get_provider_for_model("gemini-2.5-flash") == "google"
    assert service.get_provider_for_model("claude-sonnet-4-5-20250929") == "anthropic"

  def test_get_provider_for_model_invalid(self, service):
    """Test get_provider_for_model raises error for unsupported model."""
    with pytest.raises(ValueError) as exc_info:
      service.get_provider_for_model("invalid-model")

    assert "invalid-model" in str(exc_info.value)
    assert "not supported" in str(exc_info.value)

  @patch('app.services.provider_service.ProviderFactory.get_provider')
  def test_send_prompt_without_saving(self, mock_get_provider, service, mock_interaction_service):
    """Test send_prompt with save_to_db=False returns response without saving."""
    # Create mock provider response
    mock_provider_response = ProviderResponse(
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

    # Mock provider
    mock_provider = Mock()
    mock_provider.send_prompt.return_value = mock_provider_response
    mock_get_provider.return_value = mock_provider

    # Call send_prompt with save_to_db=False
    response = service.send_prompt(
      prompt="Test prompt",
      model="gpt-5.1",
      save_to_db=False
    )

    # Verify response
    assert response.prompt == "Test prompt"
    assert response.response_text == "Test response"
    assert response.provider == "openai"
    assert response.model == "gpt-5.1"
    assert response.interaction_id is None  # Not saved

    # Verify interaction_service.save_interaction was NOT called
    mock_interaction_service.save_interaction.assert_not_called()

  @patch('app.services.provider_service.ProviderFactory.get_provider')
  def test_send_prompt_with_search_queries_and_citations(self, mock_get_provider, service, mock_interaction_service):
    """Test send_prompt handles search queries and citations correctly."""
    # Create mock provider response with search queries and citations
    mock_provider_response = ProviderResponse(
      provider="google",
      model="gemini-2.5-flash",
      response_text="Test response with sources",
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
      response_time_ms=1500,
      data_source="api",
      raw_response={"key": "value"}
    )

    # Mock provider
    mock_provider = Mock()
    mock_provider.send_prompt.return_value = mock_provider_response
    mock_get_provider.return_value = mock_provider

    # Mock interaction service to return None (testing non-save path)
    response = service.send_prompt(
      prompt="Test prompt with sources",
      model="gemini-2.5-flash",
      save_to_db=False
    )

    # Verify response
    assert response.prompt == "Test prompt with sources"
    assert len(response.search_queries) == 1
    assert response.search_queries[0].query == "test query"
    assert len(response.search_queries[0].sources) == 1
    assert response.search_queries[0].sources[0].url == "https://example.com"
    assert len(response.citations) == 1
    assert response.citations[0].url == "https://example.com"
