"""
Tests for OpenAI provider implementation.
"""

import pytest
from unittest.mock import Mock, patch
from src.providers.openai_provider import OpenAIProvider
from src.providers.base_provider import ProviderResponse, SearchQuery, Source, Citation


class TestOpenAIProvider:
    """Test suite for OpenAI provider."""

    def test_initialization(self):
        """Test provider can be initialized with API key."""
        provider = OpenAIProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.client is not None

    def test_get_provider_name(self):
        """Test provider returns correct name."""
        provider = OpenAIProvider(api_key="test_key")
        assert provider.get_provider_name() == "openai"

    def test_get_supported_models(self):
        """Test provider returns list of supported models."""
        provider = OpenAIProvider(api_key="test_key")
        models = provider.get_supported_models()

        assert isinstance(models, list)
        assert len(models) == 3
        assert "gpt-5.1" in models
        assert "gpt-5-mini" in models
        assert "gpt-5-nano" in models

    def test_validate_model_success(self):
        """Test model validation succeeds for supported models."""
        provider = OpenAIProvider(api_key="test_key")

        assert provider.validate_model("gpt-5.1") is True
        assert provider.validate_model("gpt-5-mini") is True
        assert provider.validate_model("gpt-5-nano") is True

    def test_validate_model_failure(self):
        """Test model validation fails for unsupported models."""
        provider = OpenAIProvider(api_key="test_key")

        assert provider.validate_model("gpt-4") is False
        assert provider.validate_model("invalid-model") is False

    def test_send_prompt_invalid_model(self):
        """Test send_prompt raises error for invalid model."""
        provider = OpenAIProvider(api_key="test_key")

        with pytest.raises(ValueError, match="Model .* not supported"):
            provider.send_prompt("test prompt", "invalid-model")

    @patch('src.providers.openai_provider.OpenAI')
    def test_send_prompt_mock_response(self, mock_openai_class):
        """Test send_prompt with mocked API response."""
        # Create mock response
        mock_response = Mock()
        mock_response.items = [
            Mock(
                type="web_search_call",
                status="completed",
                action=Mock(
                    type="search",
                    query="test query",
                    sources=[
                        Mock(url="https://example.com", title="Example"),
                    ]
                )
            ),
            Mock(
                type="message",
                status="completed",
                content=[
                    Mock(
                        type="output_text",
                        text="Test response",
                        annotations=[
                            Mock(
                                type="url_citation",
                                url="https://example.com",
                                title="Example"
                            )
                        ]
                    )
                ]
            )
        ]
        mock_response.model_dump.return_value = {}

        # Setup mock client
        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        provider = OpenAIProvider(api_key="test_key")
        result = provider.send_prompt("test prompt", "gpt-5.1")

        # Assertions
        assert isinstance(result, ProviderResponse)
        assert result.response_text == "Test response"
        assert result.model == "gpt-5.1"
        assert result.provider == "openai"
        assert len(result.search_queries) == 1
        assert result.search_queries[0].query == "test query"
        assert len(result.sources) == 1
        assert result.sources[0].url == "https://example.com"
        assert len(result.citations) == 1
        assert result.citations[0].url == "https://example.com"

    @patch('src.providers.openai_provider.OpenAI')
    def test_send_prompt_api_error(self, mock_openai_class):
        """Test send_prompt handles API errors."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.responses.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key="test_key")

        with pytest.raises(Exception, match="OpenAI API error"):
            provider.send_prompt("test prompt", "gpt-5.1")
