"""Utility functions for the application."""

import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse


def extract_domain(url: str) -> Optional[str]:
  """Extract domain from URL.

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
  """Normalize model name for consistent storage.

  Converts dashes to dots for version numbers (e.g., gpt-5-1 → gpt-5.1)

  IMPORTANT: Known canonical model names are preserved as-is to prevent corruption.
  This is critical for models like Claude which use date suffixes (claude-sonnet-4-5-20250929).

  Args:
    model_name: The model name to normalize

  Returns:
    Normalized model name

  Examples:
    >>> normalize_model_name("gpt-5-1")
    'gpt-5.1'
    >>> normalize_model_name("gemini-3-0-flash")
    'gemini-3.0-flash'
    >>> normalize_model_name("claude-sonnet-4-5-20250929")
    'claude-sonnet-4-5-20250929'  # Preserved as-is
  """
  # Import here to avoid circular dependency
  try:
    from app.services.providers.provider_factory import ProviderFactory
    # If this model is in the canonical MODEL_PROVIDER_MAP, return as-is
    if model_name in ProviderFactory.MODEL_PROVIDER_MAP:
      return model_name
  except ImportError:
    # If import fails, proceed with normalization logic
    pass

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
        remainder = parts[-1][1:]
        if remainder:
          parts[-1] = remainder
        else:
          parts.pop()
        model_name = "-".join(parts)
    except (IndexError, AttributeError):
      pass

  return model_name


def calculate_average_rank(citations: list[Any]) -> Optional[float]:
  """Calculate average rank of citations.

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
  rank_values = [getattr(c, 'rank', None) for c in citations]
  ranks: list[float] = [float(r) for r in rank_values if isinstance(r, (int, float))]
  if not ranks:
    return None
  return sum(ranks) / len(ranks)


def get_model_display_name(model: str) -> str:
  """Get formatted display name for a model.

  Uses the centralized model registry from ProviderFactory as the source of truth.
  Falls back to formatting for unknown/web-capture models.

  Args:
    model: The model identifier

  Returns:
    Formatted display name

  Examples:
    >>> get_model_display_name("gpt-5.1")
    'GPT-5.1'
    >>> get_model_display_name("claude-sonnet-4-5-20250929")
    'Claude Sonnet 4.5'
    >>> get_model_display_name("chatgpt-free")
    'ChatGPT (Free)'
  """
  if not model:
    return ''

  model = normalize_model_name(model)

  # Try to get from centralized registry first
  try:
    from app.services.providers.provider_factory import ProviderFactory
    display_name = ProviderFactory.get_display_name(model)
    if not display_name and model.startswith("claude-"):
      display_name = ProviderFactory.get_display_name(model.replace(".", "-"))
    if display_name:
      return display_name
  except ImportError:
    pass

  # Special cases for web capture / network log models not in registry
  web_capture_models = {
    'ChatGPT (Free)': 'ChatGPT (Free)',
    'chatgpt-free': 'ChatGPT (Free)',
    'ChatGPT': 'ChatGPT (Free)',
  }
  if model in web_capture_models:
    return web_capture_models[model]

  # Fallback: Format unknown model IDs nicely.
  # Remove date suffixes (e.g., -20250929 or -0250929).
  core = re.sub(r'-\d{7,8}$', '', model)

  # Claude variants can appear with dotted minor versions (e.g., 4.1) or patch versions (e.g., 4-5.2).
  m = re.match(r"^(claude)-(sonnet|opus|haiku)-(\d+)[-\.](\d+)(?:\.\d+)?$", core)
  if m:
    family = m.group(2).capitalize()
    return f"Claude {family} {m.group(3)}.{m.group(4)}"

  # GPT / Gemini: keep dots (e.g., gpt-5.1), and render as prefix-joined.
  if core.startswith("gpt-"):
    return f"GPT-{core[4:]}"
  if core.startswith("gemini-"):
    return f"Gemini-{core[7:]}"

  # Generic models sometimes include trailing patch-like versions (e.g., v2.5).
  core = re.sub(r"(v\d+)\.\d+$", r"\1", core, flags=re.IGNORECASE)

  # Generic: hyphens to spaces, title-case words, preserve dots.
  return ' '.join(word.capitalize() for word in core.split('-'))


def format_pub_date(pub_date: str) -> str:
  """Format ISO pub_date to a friendly string.

  Args:
    pub_date: ISO-formatted date string

  Returns:
    Formatted date string or original if parsing fails

  Examples:
    >>> format_pub_date("2024-01-15T10:30:00")
    'Mon, Jan 15, 2024 10:30 UTC'
  """
  if not pub_date:
    return ""
  try:
    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
    return dt.strftime("%a, %b %d, %Y %H:%M UTC")
  except Exception:
    return pub_date
