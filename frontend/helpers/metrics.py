"""Shared metrics computation for responses."""

import re
from types import SimpleNamespace
from typing import List, Optional


def get_model_display_name(model: str) -> str:
    """Get formatted display name for a model.

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
        'claude-sonnet-4-5.2-0250929': 'Claude Sonnet 4.5',
        'claude-sonnet-4.5-20250929': 'Claude Sonnet 4.5',
        'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
        'claude-haiku-4.5-20251001': 'Claude Haiku 4.5',
        'claude-opus-4-1-20250805': 'Claude Opus 4.1',
        'claude-opus-4.1-20250805': 'Claude Opus 4.1',
        # OpenAI
        'gpt-5.1': 'GPT-5.1',
        'gpt-5-1': 'GPT-5.1',
        'gpt-5.2': 'GPT-5.2',
        'gpt-5-2': 'GPT-5.2',
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
