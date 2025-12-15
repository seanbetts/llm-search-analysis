"""Provider factory for selecting the appropriate LLM provider based on model.

This module serves as the single source of truth for all model configuration.
All model metadata (provider, display name) is centralized here to prevent
duplication and ensure consistency across the application.
"""

from typing import Dict, List, Optional

from .base_provider import BaseProvider


class ModelInfo:
  """Model metadata container."""

  def __init__(self, model_id: str, provider: str, display_name: str):
    """Initialize model info.

    Args:
      model_id: Model identifier (e.g., "gpt-5.1")
      provider: Provider name (e.g., "openai")
      display_name: Human-friendly display name (e.g., "GPT-5.1")
    """
    self.model_id = model_id
    self.provider = provider
    self.display_name = display_name


class ProviderFactory:
  """Factory class to instantiate the correct provider based on model name.

  This class maintains the centralized model registry (MODEL_REGISTRY) which
  is the single source of truth for all model configuration in the application.
  """

  # Centralized model registry - SINGLE SOURCE OF TRUTH
  # All model metadata is defined here to prevent duplication
  MODEL_REGISTRY: Dict[str, ModelInfo] = {
    # OpenAI models
    "gpt-5.1": ModelInfo("gpt-5.1", "openai", "GPT-5.1"),
    "gpt-5.2": ModelInfo("gpt-5.2", "openai", "GPT-5.2"),
    "gpt-5-mini": ModelInfo("gpt-5-mini", "openai", "GPT-5 Mini"),
    "gpt-5-nano": ModelInfo("gpt-5-nano", "openai", "GPT-5 Nano"),

    # Google models
    "gemini-3-pro-preview": ModelInfo("gemini-3-pro-preview", "google", "Gemini 3 Pro (Preview)"),
    "gemini-2.5-flash": ModelInfo("gemini-2.5-flash", "google", "Gemini 2.5 Flash"),
    "gemini-2.5-flash-lite": ModelInfo("gemini-2.5-flash-lite", "google", "Gemini 2.5 Flash Lite"),

    # Anthropic models
    "claude-sonnet-4-5-20250929": ModelInfo("claude-sonnet-4-5-20250929", "anthropic", "Claude Sonnet 4.5"),
    "claude-haiku-4-5-20251001": ModelInfo("claude-haiku-4-5-20251001", "anthropic", "Claude Haiku 4.5"),
    "claude-opus-4-1-20250805": ModelInfo("claude-opus-4-1-20250805", "anthropic", "Claude Opus 4.1"),
  }

  # Backward compatibility - derived from MODEL_REGISTRY
  MODEL_PROVIDER_MAP = {
    model_id: info.provider
    for model_id, info in MODEL_REGISTRY.items()
  }

  @staticmethod
  def get_provider(model: str, api_keys: dict) -> BaseProvider:
    """Get the appropriate provider instance for the given model.

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
  def get_all_supported_models() -> List[str]:
    """Get list of all supported models across all providers.

    Returns:
      List of model identifiers
    """
    return list(ProviderFactory.MODEL_REGISTRY.keys())

  @staticmethod
  def get_provider_for_model(model: str) -> Optional[str]:
    """Get the provider name for a given model.

    Args:
      model: Model identifier

    Returns:
      Provider name or None if model is not supported
    """
    model_info = ProviderFactory.MODEL_REGISTRY.get(model)
    return model_info.provider if model_info else None

  @staticmethod
  def get_model_info(model: str) -> Optional[ModelInfo]:
    """Get full model metadata for a given model.

    Args:
      model: Model identifier

    Returns:
      ModelInfo object or None if model is not supported
    """
    return ProviderFactory.MODEL_REGISTRY.get(model)

  @staticmethod
  def get_display_name(model: str) -> Optional[str]:
    """Get display name for a given model.

    Args:
      model: Model identifier

    Returns:
      Display name or None if model is not supported
    """
    model_info = ProviderFactory.MODEL_REGISTRY.get(model)
    return model_info.display_name if model_info else None

  @staticmethod
  def get_models_for_provider(provider: str) -> List[ModelInfo]:
    """Get all models for a specific provider.

    Args:
      provider: Provider name (e.g., "openai")

    Returns:
      List of ModelInfo objects for that provider
    """
    return [
      info for info in ProviderFactory.MODEL_REGISTRY.values()
      if info.provider == provider
    ]

  @staticmethod
  def create_provider(provider_name: str, api_key: str) -> BaseProvider:
    """Create a provider instance by provider name.

    Args:
      provider_name: Name of provider ("openai", "google", or "anthropic")
      api_key: API key for the provider

    Returns:
      Instance of the appropriate provider

    Raises:
      ValueError: If provider name is not supported
    """
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
      raise ValueError(
        f"Unknown provider: {provider_name}. "
        f"Supported providers: openai, google, anthropic"
      )
