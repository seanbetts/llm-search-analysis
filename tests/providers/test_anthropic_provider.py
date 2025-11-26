"""
Tests for Anthropic Claude provider implementation.
"""

import pytest
from unittest.mock import Mock, patch
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.base_provider import ProviderResponse


class TestAnthropicProvider:
    """Test suite for Anthropic provider."""

    def test_initialization(self):
        """Test provider can be initialized with API key."""
        provider = AnthropicProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.client is not None

    def test_get_provider_name(self):
        """Test provider returns correct name."""
        provider = AnthropicProvider(api_key="test_key")
        assert provider.get_provider_name() == "anthropic"

    def test_get_supported_models(self):
        """Test provider returns list of supported models."""
        provider = AnthropicProvider(api_key="test_key")
        models = provider.get_supported_models()

        assert isinstance(models, list)
        assert len(models) == 3
        assert "claude-sonnet-4-5-20250929" in models
        assert "claude-haiku-4-5-20251001" in models
        assert "claude-opus-4-1-20250805" in models

    def test_validate_model_success(self):
        """Test model validation succeeds for supported models."""
        provider = AnthropicProvider(api_key="test_key")

        assert provider.validate_model("claude-sonnet-4-5-20250929") is True
        assert provider.validate_model("claude-haiku-4-5-20251001") is True
        assert provider.validate_model("claude-opus-4-1-20250805") is True

    def test_validate_model_failure(self):
        """Test model validation fails for unsupported models."""
        provider = AnthropicProvider(api_key="test_key")

        assert provider.validate_model("claude-2") is False
        assert provider.validate_model("invalid-model") is False

    def test_send_prompt_invalid_model(self):
        """Test send_prompt raises error for invalid model."""
        provider = AnthropicProvider(api_key="test_key")

        with pytest.raises(ValueError, match="Model .* not supported"):
            provider.send_prompt("test prompt", "invalid-model")

    @patch('src.providers.anthropic_provider.Anthropic')
    def test_send_prompt_mock_response(self, mock_anthropic_class):
        """Test send_prompt with mocked API response."""
        # Create mock content block
        mock_content_block = Mock()
        mock_content_block.type = "text"
        mock_content_block.text = "Test response from Claude"
        mock_content_block.citations = []  # No citations

        # Create mock response
        mock_response = Mock()
        mock_response.content = [mock_content_block]
        mock_response.model_dump.return_value = {}

        # Setup mock client
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key="test_key")
        result = provider.send_prompt("test prompt", "claude-sonnet-4-5-20250929")

        # Assertions
        assert isinstance(result, ProviderResponse)
        assert result.response_text == "Test response from Claude"
        assert result.model == "claude-sonnet-4-5-20250929"
        assert result.provider == "anthropic"
        # MVP: No search integration yet
        assert len(result.search_queries) == 0
        assert len(result.sources) == 0
        assert len(result.citations) == 0

    @patch('src.providers.anthropic_provider.Anthropic')
    def test_send_prompt_multiple_content_blocks(self, mock_anthropic_class):
        """Test send_prompt with multiple text blocks."""
        # Create mock content blocks
        mock_block1 = Mock()
        mock_block1.type = "text"
        mock_block1.text = "Part 1. "
        mock_block1.citations = []  # No citations

        mock_block2 = Mock()
        mock_block2.type = "text"
        mock_block2.text = "Part 2."
        mock_block2.citations = []  # No citations

        # Create mock response
        mock_response = Mock()
        mock_response.content = [mock_block1, mock_block2]
        mock_response.model_dump.return_value = {}

        # Setup mock client
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key="test_key")
        result = provider.send_prompt("test prompt", "claude-sonnet-4-5-20250929")

        # Assertions
        assert result.response_text == "Part 1. Part 2."

    @patch('src.providers.anthropic_provider.Anthropic')
    def test_send_prompt_api_error(self, mock_anthropic_class):
        """Test send_prompt handles API errors."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key="test_key")

        with pytest.raises(Exception, match="Anthropic API error"):
            provider.send_prompt("test prompt", "claude-sonnet-4-5-20250929")
