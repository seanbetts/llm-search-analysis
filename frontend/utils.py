"""Utility functions for the Streamlit frontend."""

from datetime import datetime


def format_pub_date(pub_date: str) -> str:
  """Format ISO pub_date to a friendly string.

  Args:
    pub_date: ISO-formatted date string

  Returns:
    Formatted date string like "Mon, Jan 15, 2024 10:30 UTC"
  """
  if not pub_date:
    return ""
  try:
    dt = datetime.fromisoformat(pub_date)
    return dt.strftime("%a, %b %d, %Y %H:%M UTC")
  except Exception:
    return pub_date
