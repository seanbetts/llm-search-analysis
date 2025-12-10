"""Tests for provider validation to prevent provider/model mismatches."""

import pytest
from pydantic import ValidationError

from app.api.v1.schemas.requests import SendPromptRequest


class TestProviderValidation:
  """Tests for provider validation logic."""

  def test_mismatched_provider_model_rejected(self):
    """Ensure mismatched provider+model raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        provider="anthropic",
        model="gpt-5.1",  # OpenAI model with Anthropic provider!
        prompt="test"
      )

    error_message = str(exc_info.value)
    assert "Provider mismatch" in error_message
    assert "gpt-5.1" in error_message
    assert "openai" in error_message

  def test_unknown_model_rejected(self):
    """Ensure unknown models raise validation error."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        provider="anthropic",
        model="claude-ultra-99",  # Not in MODEL_PROVIDER_MAP
        prompt="test"
      )

    error_message = str(exc_info.value)
    assert "not supported" in error_message.lower()

  def test_correct_anthropic_model_accepted(self):
    """Ensure correct Anthropic combinations work."""
    request = SendPromptRequest(
      provider="anthropic",
      model="claude-sonnet-4-5-20250929",
      prompt="test"
    )
    assert request.provider == "anthropic"
    assert request.model == "claude-sonnet-4-5-20250929"

  def test_correct_openai_model_accepted(self):
    """Ensure correct OpenAI combinations work."""
    request = SendPromptRequest(
      provider="openai",
      model="gpt-5.1",
      prompt="test"
    )
    assert request.provider == "openai"
    assert request.model == "gpt-5.1"

  def test_correct_google_model_accepted(self):
    """Ensure correct Google combinations work."""
    request = SendPromptRequest(
      provider="google",
      model="gemini-3-pro-preview",
      prompt="test"
    )
    assert request.provider == "google"
    assert request.model == "gemini-3-pro-preview"

  def test_openai_model_with_anthropic_provider_rejected(self):
    """Ensure OpenAI model with Anthropic provider is rejected."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        provider="anthropic",
        model="gpt-5-mini",
        prompt="test"
      )

    error_message = str(exc_info.value)
    assert "Provider mismatch" in error_message

  def test_google_model_with_openai_provider_rejected(self):
    """Ensure Google model with OpenAI provider is rejected."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        provider="openai",
        model="gemini-2.5-flash",
        prompt="test"
      )

    error_message = str(exc_info.value)
    assert "Provider mismatch" in error_message

  @pytest.mark.parametrize("provider,model", [
    ("openai", "gpt-5.1"),
    ("openai", "gpt-5-mini"),
    ("openai", "gpt-5-nano"),
    ("anthropic", "claude-sonnet-4-5-20250929"),
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("anthropic", "claude-opus-4-1-20250805"),
    ("google", "gemini-3-pro-preview"),
    ("google", "gemini-2.5-flash"),
    ("google", "gemini-2.5-flash-lite"),
  ])
  def test_all_valid_provider_model_combinations(self, provider, model):
    """Test all valid provider+model combinations from MODEL_PROVIDER_MAP."""
    request = SendPromptRequest(
      provider=provider,
      model=model,
      prompt="test"
    )
    assert request.provider == provider
    assert request.model == model

  @pytest.mark.parametrize("wrong_provider,correct_provider,model", [
    ("anthropic", "openai", "gpt-5.1"),
    ("openai", "anthropic", "claude-sonnet-4-5-20250929"),
    ("google", "openai", "gpt-5-mini"),
    ("anthropic", "google", "gemini-3-pro-preview"),
    ("openai", "google", "gemini-2.5-flash"),
    ("google", "anthropic", "claude-haiku-4-5-20251001"),
  ])
  def test_all_invalid_provider_model_combinations(self, wrong_provider, correct_provider, model):
    """Test that all mismatched combinations are properly rejected."""
    with pytest.raises(ValidationError) as exc_info:
      SendPromptRequest(
        provider=wrong_provider,
        model=model,
        prompt="test"
      )

    error_message = str(exc_info.value)
    assert "Provider mismatch" in error_message
    assert correct_provider in error_message
    assert model in error_message
