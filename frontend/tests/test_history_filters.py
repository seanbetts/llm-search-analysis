"""Tests for history tab filter logic.

This module tests the model display name mapping and filtering logic used
in the History tab to handle cases where multiple model IDs map to the same
display name (e.g., Anthropic's normalized vs legacy IDs).
"""

import pandas as pd

from frontend.tabs.history import _build_model_display_mapping


def test_model_filter_handles_multiple_model_ids_per_display_name():
  """
  Ensure model filter keeps all raw ids for a display name.

  Anthropic models can produce normalized IDs (e.g., claude-sonnet-4-5.2-0250929)
  as well as legacy IDs. The mapping used by the History tab should include both
  when "Claude Sonnet 4.5" is selected so new runs remain visible.
  """
  df = pd.DataFrame([
    {"model": "claude-sonnet-4-5-20250929", "model_display": "Claude Sonnet 4.5"},
    {"model": "claude-sonnet-4-5.2-0250929", "model_display": "Claude Sonnet 4.5"},
    {"model": "gpt-5.1", "model_display": "GPT-5.1"},
    {"model": None, "model_display": "GPT-5.1"},  # Should be ignored
  ])

  mapping = _build_model_display_mapping(df)

  assert mapping["Claude Sonnet 4.5"] == {
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-5.2-0250929",
  }
  assert mapping["GPT-5.1"] == {"gpt-5.1"}
