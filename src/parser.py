"""
Unified response parsing utilities.

Most parsing is done within provider implementations.
This module provides helper functions for common parsing tasks.
"""

from typing import Dict, Any
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: Full URL

    Returns:
        Domain name (e.g., "example.com")
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to specified length.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text with "..." if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_response_for_display(response_data: Dict[str, Any]) -> str:
    """
    Format provider response for user-friendly display.

    Args:
        response_data: ProviderResponse as dictionary

    Returns:
        Formatted string for display
    """
    return response_data.get("response_text", "")


def count_unique_domains(sources: list) -> int:
    """
    Count unique domains in sources list.

    Args:
        sources: List of Source objects

    Returns:
        Number of unique domains
    """
    domains = set()
    for source in sources:
        if hasattr(source, 'domain') and source.domain:
            domains.add(source.domain)
    return len(domains)
