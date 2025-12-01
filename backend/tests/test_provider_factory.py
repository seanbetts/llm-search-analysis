"""Tests for ProviderFactory."""

import pytest
from app.services.providers.provider_factory import ProviderFactory
from app.services.providers.openai_provider import OpenAIProvider
from app.services.providers.google_provider import GoogleProvider
from app.services.providers.anthropic_provider import AnthropicProvider


class TestProviderFactory:
  """Tests for ProviderFactory model selection and provider instantiation."""

  def test_get_all_supported_models(self):
    """Test get_all_supported_models returns list of models."""
    models = ProviderFactory.get_all_supported_models()
    assert isinstance(models, list)
    assert len(models) > 0

    # Check some expected models are present
    assert "gpt-5.1" in models
    assert "gemini-2.5-flash" in models
    assert "claude-sonnet-4-5-20250929" in models

  def test_get_provider_for_model_openai(self):
    """Test get_provider_for_model returns correct provider for OpenAI models."""
    assert ProviderFactory.get_provider_for_model("gpt-5.1") == "openai"
    assert ProviderFactory.get_provider_for_model("gpt-5-mini") == "openai"
    assert ProviderFactory.get_provider_for_model("gpt-5-nano") == "openai"

  def test_get_provider_for_model_google(self):
    """Test get_provider_for_model returns correct provider for Google models."""
    assert ProviderFactory.get_provider_for_model("gemini-3-pro-preview") == "google"
    assert ProviderFactory.get_provider_for_model("gemini-2.5-flash") == "google"
    assert ProviderFactory.get_provider_for_model("gemini-2.5-flash-lite") == "google"

  def test_get_provider_for_model_anthropic(self):
    """Test get_provider_for_model returns correct provider for Anthropic models."""
    assert ProviderFactory.get_provider_for_model("claude-sonnet-4-5-20250929") == "anthropic"
    assert ProviderFactory.get_provider_for_model("claude-haiku-4-5-20251001") == "anthropic"
    assert ProviderFactory.get_provider_for_model("claude-opus-4-1-20250805") == "anthropic"

  def test_get_provider_for_model_unsupported(self):
    """Test get_provider_for_model returns None for unsupported models."""
    assert ProviderFactory.get_provider_for_model("invalid-model") is None
    assert ProviderFactory.get_provider_for_model("gpt-4") is None
    assert ProviderFactory.get_provider_for_model("unknown") is None

  def test_get_provider_openai_success(self):
    """Test get_provider creates OpenAI provider with valid inputs."""
    api_keys = {
      "openai": "test-openai-key",
      "google": "test-google-key",
      "anthropic": "test-anthropic-key"
    }

    provider = ProviderFactory.get_provider("gpt-5.1", api_keys)
    assert isinstance(provider, OpenAIProvider)

  def test_get_provider_google_success(self):
    """Test get_provider creates Google provider with valid inputs."""
    api_keys = {
      "openai": "test-openai-key",
      "google": "test-google-key",
      "anthropic": "test-anthropic-key"
    }

    provider = ProviderFactory.get_provider("gemini-2.5-flash", api_keys)
    assert isinstance(provider, GoogleProvider)

  def test_get_provider_anthropic_success(self):
    """Test get_provider creates Anthropic provider with valid inputs."""
    api_keys = {
      "openai": "test-openai-key",
      "google": "test-google-key",
      "anthropic": "test-anthropic-key"
    }

    provider = ProviderFactory.get_provider("claude-sonnet-4-5-20250929", api_keys)
    assert isinstance(provider, AnthropicProvider)

  def test_get_provider_unsupported_model(self):
    """Test get_provider raises ValueError for unsupported model."""
    api_keys = {"openai": "test-key"}

    with pytest.raises(ValueError) as exc_info:
      ProviderFactory.get_provider("invalid-model-xyz", api_keys)

    assert "invalid-model-xyz" in str(exc_info.value)
    assert "not supported" in str(exc_info.value)

  def test_get_provider_missing_api_key(self):
    """Test get_provider raises ValueError when API key is missing."""
    # OpenAI model but no OpenAI API key
    api_keys = {"google": "test-key"}

    with pytest.raises(ValueError) as exc_info:
      ProviderFactory.get_provider("gpt-5.1", api_keys)

    assert "openai" in str(exc_info.value).lower()
    assert "not configured" in str(exc_info.value).lower()

  def test_create_provider_openai(self):
    """Test create_provider creates OpenAI provider."""
    provider = ProviderFactory.create_provider("openai", "test-key")
    assert isinstance(provider, OpenAIProvider)

  def test_create_provider_google(self):
    """Test create_provider creates Google provider."""
    provider = ProviderFactory.create_provider("google", "test-key")
    assert isinstance(provider, GoogleProvider)

  def test_create_provider_anthropic(self):
    """Test create_provider creates Anthropic provider."""
    provider = ProviderFactory.create_provider("anthropic", "test-key")
    assert isinstance(provider, AnthropicProvider)

  def test_create_provider_unknown(self):
    """Test create_provider raises ValueError for unknown provider."""
    with pytest.raises(ValueError) as exc_info:
      ProviderFactory.create_provider("unknown-provider", "test-key")

    assert "unknown-provider" in str(exc_info.value).lower()
    assert "supported providers" in str(exc_info.value).lower()

  def test_create_provider_empty_name(self):
    """Test create_provider raises ValueError for empty provider name."""
    with pytest.raises(ValueError) as exc_info:
      ProviderFactory.create_provider("", "test-key")

    assert "supported providers" in str(exc_info.value).lower()
