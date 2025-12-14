"""Tests for frontend.components.models helpers."""

from types import SimpleNamespace

from frontend.components import models


class StreamlitStateStub:
  """Minimal stub to mimic the pieces of streamlit used in the module."""

  def __init__(self, api_client):
    """Initialize stub with an `api_client` in session_state."""
    self.session_state = SimpleNamespace(api_client=api_client)
    self._errors = []

  def error(self, message):
    """Collect emitted error messages for assertions."""
    self._errors.append(message)


class DummyApiClient:
  """Simple API client shim returning a fixed provider payload."""

  def __init__(self, providers):
    """Initialize with a list of provider dictionaries."""
    self._providers = providers

  def get_providers(self):
    """Return configured provider metadata."""
    return self._providers


def test_get_all_models_returns_formatted_labels(monkeypatch):
  """Active providers should map to friendly labels and tuples."""
  providers = [
    {
      "name": "openai",
      "is_active": True,
      "supported_models": ["gpt-5.1", "custom-special"],
    },
    {
      "name": "google",
      "is_active": True,
      "supported_models": ["gemini-2.5-flash"],
    },
    {
      "name": "anthropic",
      "is_active": False,
      "supported_models": ["claude-opus-4-1-20250805"],
    },
  ]
  client = DummyApiClient(providers)
  st_stub = StreamlitStateStub(api_client=client)
  monkeypatch.setattr(models, "st", st_stub)

  result = models.get_all_models()
  assert result == {
    "🟢 OpenAI - GPT-5.1": ("openai", "gpt-5.1"),
    "🟢 OpenAI - custom-special": ("openai", "custom-special"),
    "🔵 Google - Gemini 2.5 Flash": ("google", "gemini-2.5-flash"),
  }
  assert st_stub._errors == []


def test_get_all_models_handles_api_errors(monkeypatch):
  """Failures should surface as streamlit errors with graceful fallback."""

  class FailingApiClient:
    """API client stub that raises to trigger the error handler."""

    def get_providers(self):
      """Always raise to simulate failures."""
      raise RuntimeError("boom")

  st_stub = StreamlitStateStub(api_client=FailingApiClient())
  monkeypatch.setattr(models, "st", st_stub)

  assert models.get_all_models() == {}
  assert len(st_stub._errors) == 1
  assert "Error loading models" in st_stub._errors[0]
