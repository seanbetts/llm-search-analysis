"""
Tests for Google Gemini provider implementation.
"""

import importlib.util
import pytest
from unittest.mock import Mock, patch

# Skip if google-genai is not installed in the current environment
if importlib.util.find_spec("google.genai") is None:
    pytest.skip("google.genai not installed; skipping Google provider tests", allow_module_level=True)

from src.providers.google_provider import GoogleProvider
from src.providers.base_provider import ProviderResponse


class TestGoogleProvider:
    """Test suite for Google provider."""

    @patch('src.providers.google_provider.Client')
    def test_initialization(self, mock_client_class):
        """Test provider can be initialized with API key."""
        provider = GoogleProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        mock_client_class.assert_called_once_with(api_key="test_key")

    def test_get_provider_name(self):
        """Test provider returns correct name."""
        with patch('src.providers.google_provider.Client'):
            provider = GoogleProvider(api_key="test_key")
            assert provider.get_provider_name() == "google"

    def test_get_supported_models(self):
        """Test provider returns list of supported models."""
        with patch('src.providers.google_provider.Client'):
            provider = GoogleProvider(api_key="test_key")
            models = provider.get_supported_models()

            assert isinstance(models, list)
            assert len(models) == 3
            assert "gemini-3-pro-preview" in models
            assert "gemini-2.5-flash" in models
            assert "gemini-2.5-flash-lite" in models

    def test_validate_model_success(self):
        """Test model validation succeeds for supported models."""
        with patch('src.providers.google_provider.Client'):
            provider = GoogleProvider(api_key="test_key")

            assert provider.validate_model("gemini-3-pro-preview") is True
            assert provider.validate_model("gemini-2.5-flash") is True

    def test_validate_model_failure(self):
        """Test model validation fails for unsupported models."""
        with patch('src.providers.google_provider.Client'):
            provider = GoogleProvider(api_key="test_key")

            assert provider.validate_model("gemini-1.0-pro") is False
            assert provider.validate_model("invalid-model") is False

    def test_send_prompt_invalid_model(self):
        """Test send_prompt raises error for invalid model."""
        with patch('src.providers.google_provider.Client'):
            provider = GoogleProvider(api_key="test_key")

            with pytest.raises(ValueError, match="Model .* not supported"):
                provider.send_prompt("test prompt", "invalid-model")

    @patch('src.providers.google_provider.Client')
    def test_send_prompt_mock_response(self, mock_client_class):
        """Test send_prompt with mocked API response."""
        # Create mock response
        mock_response = Mock()
        mock_response.text = "Test response from Gemini"
        mock_response.candidates = []

        # Setup mock client
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key="test_key")
        result = provider.send_prompt("test prompt", "gemini-3-pro-preview")

        # Assertions
        assert isinstance(result, ProviderResponse)
        assert result.response_text == "Test response from Gemini"
        assert result.model == "gemini-3-pro-preview"
        assert result.provider == "google"
        assert isinstance(result.search_queries, list)
        assert isinstance(result.sources, list)
        assert isinstance(result.citations, list)

    @patch('src.providers.google_provider.Client')
    @patch('src.providers.google_provider.requests.head')
    def test_send_prompt_with_grounding(self, mock_requests_head, mock_client_class):
        """Test send_prompt with grounding metadata."""
        # Mock the redirect resolution
        mock_head_response = Mock()
        mock_head_response.url = "https://example.com"
        mock_requests_head.return_value = mock_head_response

        # Create mock grounding metadata
        mock_chunk = Mock()
        mock_chunk.web = Mock(uri="https://example.com", title="Example")

        mock_metadata = Mock()
        mock_metadata.grounding_chunks = [mock_chunk]
        mock_metadata.web_search_queries = ["test query"]  # Add this as a list
        mock_metadata.search_entry_point = Mock()
        mock_metadata.grounding_supports = []

        mock_candidate = Mock()
        mock_candidate.grounding_metadata = mock_metadata

        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.candidates = [mock_candidate]

        # Setup mock client
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key="test_key")
        result = provider.send_prompt("test prompt", "gemini-3-pro-preview")

        # Assertions
        assert result.response_text == "Test response"
        assert len(result.sources) >= 1
        assert result.sources[0].url == "https://example.com"

    @patch('src.providers.google_provider.Client')
    def test_send_prompt_api_error(self, mock_client_class):
        """Test send_prompt handles API errors."""
        # Setup mock to raise exception
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key="test_key")

        with pytest.raises(Exception, match="Google API error"):
            provider.send_prompt("test prompt", "gemini-3-pro-preview")
