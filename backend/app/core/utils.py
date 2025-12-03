"""Utility functions for the application."""

import re
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
  if not citations:
    return None
  ranks = [getattr(c, 'rank', None) for c in citations]
  ranks = [r for r in ranks if r is not None]
  if not ranks:
    return None
  return sum(ranks) / len(ranks)


def get_model_display_name(model: str) -> str:
  """
  Get formatted display name for a model.

  Maps known model IDs to friendly display names, and formats
  unknown model IDs by converting hyphens to spaces and capitalizing.

  Args:
    model: The model identifier

  Returns:
    Formatted display name

  Examples:
    >>> get_model_display_name("gpt-5-1")
    'GPT-5.1'
    >>> get_model_display_name("claude-sonnet-4-5-20250929")
    'Claude Sonnet 4.5'
    >>> get_model_display_name("unknown-model-20250101")
    'Unknown Model'
  """
  if not model:
    return ''

  # Model display names mapping
  model_names = {
    # Anthropic (multiple format variants for robustness)
    'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
    'claude-sonnet-4-5.2-0250929': 'Claude Sonnet 4.5',  # Alternative format with .2
    'claude-sonnet-4.5-20250929': 'Claude Sonnet 4.5',   # With period separator
    'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
    'claude-haiku-4.5-20251001': 'Claude Haiku 4.5',
    'claude-opus-4-1-20250805': 'Claude Opus 4.1',
    'claude-opus-4.1-20250805': 'Claude Opus 4.1',
    # OpenAI
    'gpt-5.1': 'GPT-5.1',
    'gpt-5-1': 'GPT-5.1',
    'gpt-5-mini': 'GPT-5 Mini',
    'gpt-5-nano': 'GPT-5 Nano',
    # Google
    'gemini-3-pro-preview': 'Gemini 3 Pro (Preview)',
    'gemini-2.5-flash': 'Gemini 2.5 Flash',
    'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
    # Network capture
    'ChatGPT (Free)': 'ChatGPT (Free)',
    'chatgpt-free': 'ChatGPT (Free)',
    'ChatGPT': 'ChatGPT (Free)',
  }

  # Return mapped name if available
  if model in model_names:
    return model_names[model]

  # Fallback: Format unknown model IDs nicely
  # Remove date suffixes (e.g., -20250929 or -0250929)
  formatted = re.sub(r'-\d{7,8}$', '', model)
  # Remove any trailing version numbers like .2
  formatted = re.sub(r'\.\d+$', '', formatted)
  # Convert hyphens to spaces and capitalize words
  formatted = ' '.join(word.capitalize() for word in formatted.split('-'))
  return formatted
