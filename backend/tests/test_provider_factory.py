"""Tests for ProviderFactory helper."""

import pytest

from app.services.providers.provider_factory import ProviderFactory


class DummyProvider:
  pass


def test_get_provider_success(monkeypatch):
  """ProviderFactory should return provider instance when model and key exist."""
  class FakeProvider:
    def __init__(self, api_key):
      self.api_key = api_key

  monkeypatch.setattr("app.services.providers.openai_provider.OpenAIProvider", FakeProvider)

  provider = ProviderFactory.get_provider(
    model="gpt-5.1",
    api_keys={"openai": "test-key"}
  )

  assert isinstance(provider, FakeProvider)
  assert provider.api_key == "test-key"


def test_get_provider_missing_model():
  """Unsupported model should raise ValueError explaining supported list."""
  api_keys = {"openai": "key"}
  with pytest.raises(ValueError) as exc:
    ProviderFactory.get_provider(model="unknown-model", api_keys=api_keys)
  assert "not supported" in str(exc.value)


def test_get_provider_missing_api_key():
  """Missing API key for resolved provider should raise ValueError."""
  with pytest.raises(ValueError) as exc:
    ProviderFactory.get_provider(model="gpt-5.1", api_keys={})
  assert "API key" in str(exc.value)


@pytest.mark.parametrize(
  "provider_name, target",
  [
    ("openai", "app.services.providers.openai_provider.OpenAIProvider"),
    ("google", "app.services.providers.google_provider.GoogleProvider"),
    ("anthropic", "app.services.providers.anthropic_provider.AnthropicProvider"),
  ]
)
def test_create_provider(monkeypatch, provider_name, target):
  """create_provider should instantiate concrete provider classes."""
  class FakeProvider:
    def __init__(self, api_key):
      self.api_key = api_key

  monkeypatch.setattr(target, FakeProvider)
  instance = ProviderFactory.create_provider(provider_name, "secret")
  assert isinstance(instance, FakeProvider)
  assert instance.api_key == "secret"


def test_create_provider_unknown():
  """Unsupported provider name should raise ValueError."""
  with pytest.raises(ValueError):
    ProviderFactory.create_provider("unknown", "key")


def test_get_all_supported_models_not_empty():
  """Factory should expose list of known models."""
  models = ProviderFactory.get_all_supported_models()
  assert "gpt-5.1" in models
  assert isinstance(models, list)


def test_get_provider_for_model():
  """Mapping lookup should return provider name or None."""
  assert ProviderFactory.get_provider_for_model("gpt-5.1") == "openai"
  assert ProviderFactory.get_provider_for_model("unknown") is None
