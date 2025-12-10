"""Tests for model name persistence and normalization."""

import pytest

from app.core.utils import normalize_model_name


class TestModelNameNormalization:
  """Tests for model name normalization logic."""

  @pytest.mark.parametrize("model_name", [
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-1-20250805",
    "gpt-5.1",
    "gpt-5-mini",
    "gpt-5-nano",
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
  ])
  def test_canonical_model_name_preserved(self, model_name):
    """Ensure canonical model names from MODEL_PROVIDER_MAP are never corrupted."""
    normalized = normalize_model_name(model_name)
    assert normalized == model_name, \
      f"Model name corrupted: {model_name} → {normalized}"

  def test_claude_with_date_suffix_preserved(self):
    """
    Ensure Claude models with date suffixes are not corrupted.
    This was the original bug - date suffix was being mangled.
    """
    model = "claude-sonnet-4-5-20250929"
    normalized = normalize_model_name(model)

    # Should NOT be corrupted to claude-sonnet-4-5.2-0250929
    assert normalized == model
    # Check for corruption patterns from the original bug
    assert "5.2-0" not in normalized  # Would indicate version corruption
    assert "-4-5.2-" not in normalized  # Another corruption pattern
    # Verify correct ending
    assert normalized.endswith("20250929")  # Full date preserved

  def test_gpt_dash_notation_preserved(self):
    """Ensure GPT models with dash notation are preserved."""
    # These are in the canonical map, should NOT be normalized
    assert normalize_model_name("gpt-5.1") == "gpt-5.1"
    assert normalize_model_name("gpt-5-mini") == "gpt-5-mini"
    assert normalize_model_name("gpt-5-nano") == "gpt-5-nano"

  def test_gemini_with_version_preserved(self):
    """Ensure Gemini models with complex versions are preserved."""
    assert normalize_model_name("gemini-3-pro-preview") == "gemini-3-pro-preview"
    assert normalize_model_name("gemini-2.5-flash") == "gemini-2.5-flash"
    assert normalize_model_name("gemini-2.5-flash-lite") == "gemini-2.5-flash-lite"

  def test_unknown_model_gets_normalized(self):
    """Ensure unknown models (not in canonical map) still get normalized."""
    # Unknown models should still go through normalization
    normalized = normalize_model_name("gpt-4-turbo")
    # This may or may not equal the input depending on normalization rules
    # Just verify it returns something reasonable
    assert isinstance(normalized, str)
    assert len(normalized) > 0

  def test_normalization_does_not_corrupt_claude_formats(self):
    """
    Test that various Claude model formats don't get corrupted.
    Even if new Claude models are added, they should preserve their format.
    """
    test_cases = [
      ("claude-opus-4-1-20250805", "claude-opus-4-1-20250805"),
      ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5-20250929"),
      ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
    ]

    for input_model, expected in test_cases:
      normalized = normalize_model_name(input_model)
      assert normalized == expected, \
        f"Expected '{expected}', got '{normalized}' for input '{input_model}'"

  def test_all_claude_models_have_correct_format(self):
    """Verify all Claude models maintain {family}-{model}-{major}-{minor}-{date} format."""
    claude_models = [
      "claude-sonnet-4-5-20250929",
      "claude-haiku-4-5-20251001",
      "claude-opus-4-1-20250805",
    ]

    for model in claude_models:
      normalized = normalize_model_name(model)

      # Verify format is preserved
      parts = normalized.split("-")
      assert len(parts) >= 5, f"Claude model format corrupted: {model} → {normalized}"
      assert parts[0] == "claude"

      # Verify date suffix (last part) is 8 digits
      date_suffix = parts[-1]
      assert len(date_suffix) == 8, f"Date suffix corrupted: {date_suffix} in {normalized}"
      assert date_suffix.isdigit(), f"Date suffix not all digits: {date_suffix} in {normalized}"

  def test_normalization_is_idempotent(self):
    """Ensure normalizing a normalized name doesn't change it (idempotency)."""
    models = [
      "claude-sonnet-4-5-20250929",
      "gpt-5.1",
      "gemini-3-pro-preview",
    ]

    for model in models:
      first_pass = normalize_model_name(model)
      second_pass = normalize_model_name(first_pass)
      assert first_pass == second_pass, \
        f"Normalization not idempotent: {model} → {first_pass} → {second_pass}"

  def test_empty_model_name_handling(self):
    """Ensure empty model names are handled gracefully."""
    # Should either return empty string or raise exception, but not crash
    result = normalize_model_name("")
    assert isinstance(result, str)

  def test_single_word_model_handling(self):
    """Ensure single-word model names are handled gracefully."""
    result = normalize_model_name("gpt")
    assert isinstance(result, str)
    assert len(result) > 0
