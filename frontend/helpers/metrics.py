"""Shared metrics computation for responses.

Model display names are derived from the backend model registry when available
to avoid frontend/backend drift. The frontend keeps a small runtime cache that
can be populated by calling `load_model_display_names(...)`.

For resilience, `get_model_display_name(...)` also includes heuristic fallbacks
for common model-id patterns (e.g., `gpt-5-1` → `GPT-5.1`) and a small, stable
mapping for web-capture-only models (e.g., `chatgpt-free`).
"""

import re
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional

_WEB_CAPTURE_DISPLAY_NAMES: Dict[str, str] = {
    "ChatGPT (Free)": "ChatGPT (Free)",
    "chatgpt-free": "ChatGPT (Free)",
    "ChatGPT": "ChatGPT (Free)",
    "google-aimode": "AI Mode",
}

_MODEL_DISPLAY_NAMES: Dict[str, str] = dict(_WEB_CAPTURE_DISPLAY_NAMES)


def load_model_display_names(model_info: Iterable[Dict[str, str]]) -> None:
    """Load/refresh the in-process model display-name cache from backend metadata.

    Args:
        model_info: Iterable of dicts shaped like `{"model_id": "...", "display_name": "..."}`.
    """
    for item in model_info or []:
        if not isinstance(item, dict):
            continue
        model_id = item.get("model_id")
        display_name = item.get("display_name")
        if isinstance(model_id, str) and model_id and isinstance(display_name, str) and display_name:
            _MODEL_DISPLAY_NAMES[model_id] = display_name


def _strip_date_suffix(model: str) -> str:
    """Strip common date suffixes (e.g., `-20250929`) from model ids."""
    return re.sub(r"-\d{7,8}$", "", model)


def _heuristic_model_display_name(model: str) -> Optional[str]:
    """Return a best-effort human display name derived from model id patterns."""
    if not model:
        return None

    cleaned = _strip_date_suffix(model.strip())

    # OpenAI: gpt-5-1 -> GPT-5.1, gpt-5.1 -> GPT-5.1, gpt-5-mini -> GPT-5 Mini
    match = re.fullmatch(r"gpt-(\d+)-(\d+)", cleaned)
    if match:
        major, minor = match.groups()
        return f"GPT-{major}.{minor}"
    match = re.fullmatch(r"gpt-(\d+)\.(\d+)", cleaned)
    if match:
        major, minor = match.groups()
        return f"GPT-{major}.{minor}"
    match = re.fullmatch(r"gpt-(\d+)-(mini|nano)", cleaned)
    if match:
        major, variant = match.groups()
        return f"GPT-{major} {variant.capitalize()}"
    match = re.fullmatch(r"gpt-(\d+)\.(\d+)-(mini|nano)", cleaned)
    if match:
        major, minor, variant = match.groups()
        return f"GPT-{major}.{minor} {variant.capitalize()}"

    # Anthropic: claude-sonnet-4-5 -> Claude Sonnet 4.5
    match = re.fullmatch(r"claude-(sonnet|haiku|opus)-(\d+)-(\d+)", cleaned)
    if match:
        family, major, minor = match.groups()
        return f"Claude {family.capitalize()} {major}.{minor}"
    match = re.fullmatch(r"claude-(sonnet|haiku|opus)-(\d+)\.(\d+)", cleaned)
    if match:
        family, major, minor = match.groups()
        return f"Claude {family.capitalize()} {major}.{minor}"

    # Google: gemini-2.5-flash -> Gemini 2.5 Flash, gemini-3-pro-preview -> Gemini 3 Pro Preview
    match = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-(.+)", cleaned)
    if match:
        version, suffix = match.groups()
        tokens = [token for token in suffix.split("-") if token]
        if not tokens:
            return f"Gemini {version}"
        label = " ".join(token.capitalize() for token in tokens)
        return f"Gemini {version} {label}"

    return None


def is_known_model_id(model: str) -> bool:
    """Return True when a model id has a known/normalized display mapping.

    Args:
        model: Model identifier (e.g., `gpt-5.2`, `claude-sonnet-4-5-20250929`)
    """
    if not model:
        return False
    if model in _MODEL_DISPLAY_NAMES:
        return True
    return _heuristic_model_display_name(model) is not None


def get_model_display_name(model: str) -> str:
    """Get formatted display name for a model.

    Prefers the backend-derived registry cache when populated via
    `load_model_display_names(...)`, otherwise falls back to heuristics.

    Args:
        model: The model identifier

    Returns:
        Formatted display name

    Examples:
        >>> get_model_display_name("gpt-5.1")
        'GPT-5.1'
        >>> get_model_display_name("chatgpt-free")
        'ChatGPT (Free)'
    """
    if not model:
        return ''

    # Prefer registry cache (populated from backend) and stable web-capture labels.
    mapped = _MODEL_DISPLAY_NAMES.get(model)
    if mapped:
        return mapped

    heuristic = _heuristic_model_display_name(model)
    if heuristic:
        return heuristic

    # Fallback: Format unknown model IDs nicely
    formatted = _strip_date_suffix(model)
    # Remove any trailing version numbers like .2
    formatted = re.sub(r'\.\d+$', '', formatted)
    # Convert hyphens to spaces and capitalize words
    formatted = ' '.join(word.capitalize() for word in formatted.split('-'))
    return formatted


def compute_metrics(
    search_queries: List[SimpleNamespace],
    citations: List[SimpleNamespace],
    all_sources: Optional[List[SimpleNamespace]] = None
) -> dict:
    """Compute metrics from response data.

    This function is shared between API mode and network_log mode to ensure
    consistent metric calculation.

    Args:
        search_queries: List of search queries with sources
        citations: List of citations from the response
        all_sources: Optional list of all sources (for network_log mode)

    Returns:
        Dictionary with computed metrics:
        - sources_found: Total number of unique sources from search queries
        - sources_used: Number of citations that have a rank (were from search results)
        - avg_rank: Average rank of citations with ranks, or None if no ranked citations
        - extra_links_count: Number of citations without ranks (not from search)
    """
    # Compute sources_found - count unique sources from search queries
    sources_found = 0
    if search_queries:
        # Collect all unique URLs from search queries
        unique_urls = set()
        for query in search_queries:
            if hasattr(query, 'sources') and query.sources:
                for source in query.sources:
                    if hasattr(source, 'url') and source.url:
                        unique_urls.add(source.url)
        sources_found = len(unique_urls)

    # Fallback to all_sources if no sources found in search_queries
    # This handles network_log mode where search_queries may exist but have no sources
    if sources_found == 0 and all_sources:
        sources_found = len(all_sources)

    # Compute sources_used and avg_rank from citations
    ranked_citations = []
    unranked_citations = []

    for citation in citations:
        rank = getattr(citation, 'rank', None)
        if rank is not None:
            ranked_citations.append(rank)
        else:
            unranked_citations.append(citation)

    sources_used = len(ranked_citations)
    avg_rank = sum(ranked_citations) / len(ranked_citations) if ranked_citations else None
    extra_links_count = len(unranked_citations)

    return {
        'sources_found': sources_found,
        'sources_used': sources_used,
        'avg_rank': avg_rank,
        'extra_links_count': extra_links_count
    }
