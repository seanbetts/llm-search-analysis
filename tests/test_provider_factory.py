"""
Tests for provider factory.
"""

import importlib.util
import pytest

# Skip Google-dependent imports if google-genai is not installed
google_missing = importlib.util.find_spec("google.genai") is None
if google_missing:
    pytest.skip("google.genai not installed; skipping provider factory tests", allow_module_level=True)

from src.providers.provider_factory import ProviderFactory
from src.providers.openai_provider import OpenAIProvider
from src.providers.google_provider import GoogleProvider
from src.providers.anthropic_provider import AnthropicProvider


class TestProviderFactory:
    """Test suite for ProviderFactory."""

    def test_get_all_supported_models(self):
        """Test factory returns all supported models."""
        models = ProviderFactory.get_all_supported_models()

        assert isinstance(models, list)
        assert len(models) == 9  # 3 per provider

        # OpenAI models
        assert "gpt-5.1" in models
        assert "gpt-5-mini" in models
        assert "gpt-5-nano" in models

        # Google models
        assert "gemini-3-pro-preview" in models
        assert "gemini-2.5-flash" in models
        assert "gemini-2.5-flash-lite" in models

        # Anthropic models
        assert "claude-sonnet-4-5-20250929" in models
        assert "claude-haiku-4-5-20251001" in models
        assert "claude-opus-4-1-20250805" in models

    def test_get_provider_for_model_openai(self):
        """Test get_provider_for_model returns correct provider for OpenAI models."""
        assert ProviderFactory.get_provider_for_model("gpt-5.1") == "openai"
        assert ProviderFactory.get_provider_for_model("gpt-5-mini") == "openai"
        assert ProviderFactory.get_provider_for_model("gpt-5-nano") == "openai"

    def test_get_provider_for_model_google(self):
        """Test get_provider_for_model returns correct provider for Google models."""
        assert ProviderFactory.get_provider_for_model("gemini-3-pro-preview") == "google"
        assert ProviderFactory.get_provider_for_model("gemini-2.5-flash") == "google"

    def test_get_provider_for_model_anthropic(self):
        """Test get_provider_for_model returns correct provider for Anthropic models."""
        assert ProviderFactory.get_provider_for_model("claude-sonnet-4-5-20250929") == "anthropic"
        assert ProviderFactory.get_provider_for_model("claude-haiku-4-5-20251001") == "anthropic"

    def test_get_provider_for_model_invalid(self):
        """Test get_provider_for_model returns None for invalid model."""
        assert ProviderFactory.get_provider_for_model("invalid-model") is None

    def test_get_provider_openai(self):
        """Test factory creates OpenAI provider."""
        api_keys = {
            "openai": "test_openai_key",
            "google": "test_google_key",
            "anthropic": "test_anthropic_key"
        }

        provider = ProviderFactory.get_provider("gpt-5.1", api_keys)

        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "test_openai_key"

    def test_get_provider_google(self):
        """Test factory creates Google provider."""
        api_keys = {
            "openai": "test_openai_key",
            "google": "test_google_key",
            "anthropic": "test_anthropic_key"
        }

        provider = ProviderFactory.get_provider("gemini-3-pro-preview", api_keys)

        assert isinstance(provider, GoogleProvider)
        assert provider.api_key == "test_google_key"

    def test_get_provider_anthropic(self):
        """Test factory creates Anthropic provider."""
        api_keys = {
            "openai": "test_openai_key",
            "google": "test_google_key",
            "anthropic": "test_anthropic_key"
        }

        provider = ProviderFactory.get_provider("claude-sonnet-4-5-20250929", api_keys)

        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "test_anthropic_key"

    def test_get_provider_unsupported_model(self):
        """Test factory raises error for unsupported model."""
        api_keys = {
            "openai": "test_openai_key",
            "google": "test_google_key",
            "anthropic": "test_anthropic_key"
        }

        with pytest.raises(ValueError, match="Model .* is not supported"):
            ProviderFactory.get_provider("invalid-model", api_keys)

    def test_get_provider_missing_api_key(self):
        """Test factory raises error when API key is missing."""
        api_keys = {
            "google": "test_google_key",
            "anthropic": "test_anthropic_key"
            # Missing OpenAI key
        }

        with pytest.raises(ValueError, match="API key for provider .* is not configured"):
            ProviderFactory.get_provider("gpt-5.1", api_keys)
