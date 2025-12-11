"""Tests for CSV export helper utilities."""

import csv

import pandas as pd

from frontend.helpers.export_utils import dataframe_to_csv_bytes


def test_dataframe_to_csv_bytes_normalizes_selected_columns():
  """Only targeted text columns should have carriage returns stripped."""
  df = pd.DataFrame(
    [
      {
        "Prompt": "Line1\r\nLine2",
        "Model": "gpt-5.1",
        "Notes": "Keep\rCR",
      }
    ]
  )

  result = dataframe_to_csv_bytes(df, text_columns=["Prompt"])
  decoded = result.decode("utf-8-sig")

  assert "Line1\nLine2" in decoded  # normalized newline
  assert "\rCR" in decoded          # untouched column
  assert decoded.startswith('"Prompt","Model","Notes"')


def test_dataframe_to_csv_bytes_respects_custom_quoting():
  """Custom quoting options should flow through to pandas."""
  df = pd.DataFrame([{"Prompt": "text", "Model": "gpt-5.1"}])
  result = dataframe_to_csv_bytes(df, quoting=csv.QUOTE_MINIMAL)
  decoded = result.decode("utf-8-sig")

  assert decoded.startswith("Prompt,Model")
  assert "text" in decoded and '"' not in decoded.splitlines()[1]
