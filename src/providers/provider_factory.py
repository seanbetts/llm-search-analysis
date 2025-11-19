"""
Provider factory for selecting the appropriate LLM provider based on model.
"""

from typing import Optional
from .base_provider import BaseProvider


class ProviderFactory:
    """
    Factory class to instantiate the correct provider based on model name.
    """

    # Model to provider mapping
    MODEL_PROVIDER_MAP = {
        # OpenAI models
        "gpt-5.1": "openai",
        "gpt-5-mini": "openai",
        "gpt-5-nano": "openai",

        # Google models
        "gemini-3-pro": "google",
        "gemini-2.5-flash": "google",
        "gemini-2.5-flash-lite": "google",

        # Anthropic models
        "claude-sonnet-4.5": "anthropic",
        "claude-haiku-4.5": "anthropic",
        "claude-opus-4.1": "anthropic",
    }

    @staticmethod
    def get_provider(model: str, api_keys: dict) -> BaseProvider:
        """
        Get the appropriate provider instance for the given model.

        Args:
            model: Model identifier (e.g., "gpt-5.1", "gemini-3.0")
            api_keys: Dictionary with API keys for all providers
                     {"openai": "key1", "google": "key2", "anthropic": "key3"}

        Returns:
            Instance of the appropriate provider

        Raises:
            ValueError: If model is not supported or API key is missing
        """
        # Determine which provider this model belongs to
        provider_name = ProviderFactory.MODEL_PROVIDER_MAP.get(model)

        if not provider_name:
            raise ValueError(
                f"Model '{model}' is not supported. "
                f"Supported models: {list(ProviderFactory.MODEL_PROVIDER_MAP.keys())}"
            )

        # Get the API key for this provider
        api_key = api_keys.get(provider_name)
        if not api_key:
            raise ValueError(f"API key for provider '{provider_name}' is not configured")

        # Import and instantiate the appropriate provider
        if provider_name == "openai":
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(api_key)
        elif provider_name == "google":
            from .google_provider import GoogleProvider
            return GoogleProvider(api_key)
        elif provider_name == "anthropic":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(api_key)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    @staticmethod
    def get_all_supported_models() -> list[str]:
        """
        Get list of all supported models across all providers.

        Returns:
            List of model identifiers
        """
        return list(ProviderFactory.MODEL_PROVIDER_MAP.keys())

    @staticmethod
    def get_provider_for_model(model: str) -> Optional[str]:
        """
        Get the provider name for a given model.

        Args:
            model: Model identifier

        Returns:
            Provider name or None if model is not supported
        """
        return ProviderFactory.MODEL_PROVIDER_MAP.get(model)
