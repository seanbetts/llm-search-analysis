"""Utilities for preparing CSV exports."""

from __future__ import annotations

import csv
from typing import Iterable, Optional

import pandas as pd


def dataframe_to_csv_bytes(
  df: pd.DataFrame,
  *,
  text_columns: Optional[Iterable[str]] = None,
  quoting: int = csv.QUOTE_ALL
) -> bytes:
  """
  Convert a DataFrame into UTF-8 encoded CSV bytes with optional text sanitization.

  Args:
    df: The DataFrame to export.
    text_columns: Optional iterable of column names whose string values should have
      Windows line endings normalized to '\n' to preserve formatting.
    quoting: csv module quoting strategy (defaults to QUOTE_ALL for compatibility).

  Returns:
    Bytes encoded CSV (UTF-8 with BOM) suitable for download_button.
  """
  clean_df = df.copy()

  if text_columns:
    for column in text_columns:
      if column in clean_df.columns:
        clean_df[column] = clean_df[column].apply(
          lambda value: value.replace("\r\n", "\n").replace("\r", "\n") if isinstance(value, str) else value
        )

  csv_string = clean_df.to_csv(index=False, quoting=quoting)
  return csv_string.encode("utf-8-sig")
