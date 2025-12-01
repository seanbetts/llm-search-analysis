"""Utility functions for the application."""

from urllib.parse import urlparse
from typing import Optional


def extract_domain(url: str) -> Optional[str]:
  """
  Extract domain from URL.

  Args:
    url: The URL to extract domain from

  Returns:
    Domain name or None if invalid URL

  Examples:
    >>> extract_domain("https://www.example.com/path")
    'example.com'
    >>> extract_domain("https://subdomain.example.com")
    'subdomain.example.com'
  """
  try:
    parsed = urlparse(url)
    domain = parsed.netloc

    # Remove www. prefix if present
    if domain.startswith("www."):
      domain = domain[4:]

    return domain if domain else None
  except Exception:
    return None


def normalize_model_name(model_name: str) -> str:
  """
  Normalize model name for consistent storage.

  Converts dashes to dots for version numbers (e.g., gpt-5-1 → gpt-5.1)

  Args:
    model_name: The model name to normalize

  Returns:
    Normalized model name

  Examples:
    >>> normalize_model_name("gpt-5-1")
    'gpt-5.1'
    >>> normalize_model_name("gemini-3-0-flash")
    'gemini-3.0-flash'
    >>> normalize_model_name("claude-3-7-sonnet")
    'claude-3.7-sonnet'
  """
  # Handle version number patterns like x-y where y is a single digit
  # gpt-5-1 → gpt-5.1
  # gemini-3-0-flash → gemini-3.0-flash
  parts = model_name.split("-")

  if len(parts) >= 3:
    # Check if second and third parts are single digits (version numbers)
    try:
      if parts[-2].isdigit() and len(parts[-2]) == 1 and parts[-1][0].isdigit():
        # Replace the dash before the last digit with a dot
        parts[-2] = f"{parts[-2]}.{parts[-1][0]}"
        parts[-1] = parts[-1][1:] if len(parts[-1]) > 1 else None
        model_name = "-".join(p for p in parts if p)
    except (IndexError, AttributeError):
      pass

  return model_name


def calculate_average_rank(citations: list) -> Optional[float]:
  """
  Calculate average rank of citations.

  Args:
    citations: List of citation objects with rank attribute

  Returns:
    Average rank or None if no ranked citations

  Examples:
    >>> citations = [{"rank": 1}, {"rank": 3}, {"rank": 5}]
    >>> calculate_average_rank(citations)
    3.0
  """
  ranks = [c.rank for c in citations if c.rank is not None]
  if not ranks:
    return None
  return sum(ranks) / len(ranks)
