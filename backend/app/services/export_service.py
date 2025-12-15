"""Service for exporting interactions in various formats."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.core.utils import format_pub_date
from app.services.interaction_service import InteractionService


class ExportService:
  """Service for exporting interaction data."""

  def __init__(self, interaction_service: InteractionService):
    """Initialize export service.

    Args:
      interaction_service: InteractionService instance for fetching data
    """
    self.interaction_service = interaction_service

  def build_markdown(self, interaction_id: int) -> Optional[str]:
    r"""Build a formatted markdown export of an interaction.

    Args:
      interaction_id: The interaction ID to export

    Returns:
      Markdown formatted string, or None if interaction not found

    Examples:
      >>> export_service.build_markdown(123)
      '# Interaction 123\\n\\n## Prompt\\n> What is AI?\\n...'
    """
    response = self.interaction_service.get_interaction_details(interaction_id)
    if not response:
      return None

    details: Dict[str, Any] = response.model_dump()
    lines: list[str] = []

    lines.append(f"# Interaction {interaction_id}")
    lines.append("")

    lines.append("## Prompt")
    lines.append(f"> {details.get('prompt', '')}")
    lines.append("")

    num_searches = len(details.get('search_queries', []))
    num_sources = details.get('sources_found', 0)
    num_sources_used = details.get('sources_used', 0)
    avg_rank = details.get('avg_rank')
    avg_rank_display = f"{avg_rank:.1f}" if avg_rank is not None else "N/A"
    response_time_ms = details.get('response_time_ms')
    response_time_s = f"{response_time_ms / 1000:.1f}s" if response_time_ms else "N/A"
    extra_links = details.get('extra_links_count', 0)
    data_source = details.get('data_source', 'api')
    analysis_type = 'Web' if data_source in ('web', 'network_log') else 'API'
    model_display = details.get('model_display_name') or details.get('model', 'Unknown')

    lines.append("## Metadata")
    lines.append(f"- Provider: {details.get('provider', 'Unknown')}")
    lines.append(f"- Model: {model_display}")
    lines.append(f"- Analysis: {analysis_type}")
    lines.append(f"- Response Time: {response_time_s}")
    lines.append(f"- Searches: {num_searches}")
    lines.append(f"- Sources Found: {num_sources}")
    lines.append(f"- Sources Used: {num_sources_used}")
    lines.append(f"- Avg. Rank: {avg_rank_display}")
    lines.append(f"- Extra Links: {extra_links}")
    lines.append("")

    lines.append("## Response")
    response_text = self._format_response_text(
      details.get('response_text', ''),
      details.get('citations', []),
    )
    response_text = self._nest_response_headings(response_text)
    lines.append(response_text or "_No response text available._")
    lines.append("")

    search_queries = details.get('search_queries', [])
    all_sources = details.get('all_sources') or []
    citations = details.get('citations', []) or []

    if search_queries:
      lines.append("## Search Queries")
      for idx, query in enumerate(search_queries, 1):
        q_text = query.get('query') or ''
        lines.append(f"### Query {idx}: {q_text}")
      lines.append("")

    # Sources found
    if data_source == 'api':
      queries_with_sources = [q for q in search_queries if q.get("sources")]
      if queries_with_sources:
        lines.append("## Sources Found (by Query)")
        for idx, query in enumerate(queries_with_sources, 1):
          sources = query.get('sources', []) or []
          lines.append(f"### Query {idx} Sources ({len(sources)})")
          for s_idx, src in enumerate(sources, 1):
            title = src.get('title') or src.get('domain') or 'Unknown source'
            url = src.get('url') or ''
            domain = src.get('domain') or ''
            description = src.get('search_description') or src.get('snippet_text') or 'N/A'
            if description == 'N/A' and src.get('title'):
              description = src.get('title')
            pub_date = src.get('pub_date')
            pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
            lines.append(f"{s_idx}. [{title}]({url}) ({domain})")
            lines.append(f"   - Description: {description}")
            lines.append(f"   - Published: {pub_date_fmt}")
        lines.append("")
    else:
      if all_sources:
        lines.append(f"## Sources Found ({len(all_sources)})")
        lines.append("_Note: Web Analyses don't provide reliable query-to-source mapping._")
        lines.append("")
        for s_idx, src in enumerate(all_sources, 1):
          title = src.get('title') or src.get('domain') or 'Unknown source'
          url = src.get('url') or ''
          domain = src.get('domain') or ''
          description = src.get('search_description') or src.get('snippet_text') or 'N/A'
          if description == 'N/A' and src.get('title'):
            description = src.get('title')
          pub_date = src.get('pub_date')
          pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
          lines.append(f"{s_idx}. [{title}]({url}) ({domain})")
          lines.append(f"   - Description: {description}")
          lines.append(f"   - Published: {pub_date_fmt}")
        lines.append("")

    # Sources used + extra links
    if citations:
      url_to_source = {src.get("url"): src for src in all_sources if src.get("url")}

      sources_used = [c for c in citations if c.get("rank")]
      if sources_used:
        lines.append(f"## Sources Used ({len(sources_used)})")
        for c_idx, citation in enumerate(sources_used, 1):
          url = citation.get('url') or ''
          source_fallback = url_to_source.get(url, {}) if url else {}
          title = citation.get('title') or source_fallback.get("title") or 'Unknown source'
          domain = urlparse(url).netloc if url else ''
          rank = citation.get('rank')
          rank_display = f" (Rank {rank})" if rank else ""
          description = (
            source_fallback.get("search_description")
            or source_fallback.get("snippet_text")
            or "N/A"
          )
          pub_date = source_fallback.get("pub_date") or citation.get("published_at")
          pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
          snippet_cited = citation.get('snippet_cited') or citation.get('text_snippet') or 'N/A'
          influence_summary = citation.get("influence_summary") or "N/A"
          provenance = citation.get("provenance_tags") or []
          function = citation.get("function_tags") or []
          stance = citation.get("stance_tags") or []

          lines.append(f"{c_idx}. [{title}]({url}) ({domain}){rank_display}")
          lines.append(f"   - Description: {description}")
          lines.append(f"   - Published: {pub_date_fmt}")
          lines.append("   ---")
          lines.append(f"   - Snippet Cited: {snippet_cited}")
          lines.append(f"   - Influence Summary: {influence_summary}")
          if provenance:
            lines.append(f"   - Provenance: {', '.join(provenance)}")
          if function:
            lines.append(f"   - Function: {', '.join(function)}")
          if stance:
            lines.append(f"   - Stance: {', '.join(stance)}")
        lines.append("")

      extra_links = [c for c in citations if not c.get("rank")]
      if extra_links:
        lines.append(f"## Extra Links ({len(extra_links)})")
        lines.append("Links mentioned in the response that weren't from search results.")
        lines.append("")
        for c_idx, citation in enumerate(extra_links, 1):
          url = citation.get('url') or ''
          title = citation.get('title') or urlparse(url).netloc or 'Unknown source'
          domain = urlparse(url).netloc if url else ''
          citation_metadata = citation.get("metadata") or {}
          description = citation_metadata.get("snippet") or "N/A"
          pub_date = (
            citation.get("published_at")
            or citation_metadata.get("published_at")
            or citation_metadata.get("pub_date")
          )
          pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
          snippet_cited = citation.get('snippet_cited') or citation.get('text_snippet') or 'N/A'
          influence_summary = citation.get("influence_summary") or "N/A"
          provenance = citation.get("provenance_tags") or []
          function = citation.get("function_tags") or []
          stance = citation.get("stance_tags") or []

          lines.append(f"{c_idx}. [{title}]({url}) ({domain})")
          lines.append(f"   - Description: {description}")
          lines.append(f"   - Published: {pub_date_fmt}")
          lines.append("   ---")
          lines.append(f"   - Snippet Cited: {snippet_cited}")
          lines.append(f"   - Influence Summary: {influence_summary}")
          if provenance:
            lines.append(f"   - Provenance: {', '.join(provenance)}")
          if function:
            lines.append(f"   - Function: {', '.join(function)}")
          if stance:
            lines.append(f"   - Stance: {', '.join(stance)}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"

  def _format_response_text(self, text: str, citations: list) -> str:
    """Format response text by converting reference-style citation links to inline links.

    ChatGPT includes markdown reference links at the bottom like:
    [1]: URL "Title"
    [2]: URL "Title"

    And uses them inline like: [Text][1]

    We convert these to inline markdown links: [Text](URL)

    Args:
      text: The response text to format
      citations: List of citation dicts (unused; reserved for future formatting)

    Returns:
      Formatted response text
    """
    if not text:
      return ""

    import re

    ref_pattern = r'^\[(\d+)\]:\s+(\S+)(?:\s+"([^"]*)")?$'
    refs = {}
    lines = text.split('\n')
    content_lines = []

    for line in lines:
      match = re.match(ref_pattern, line)
      if match:
        ref_num = match.group(1)
        url = match.group(2)
        refs[ref_num] = url
      else:
        content_lines.append(line)

    formatted_text = '\n'.join(content_lines)
    for ref_num, url in refs.items():
      pattern = r'\[([^\]]+)\]\[' + re.escape(ref_num) + r'\]'
      replacement = r'[\1](' + url + ')'
      formatted_text = re.sub(pattern, replacement, formatted_text)

    formatted_text = re.sub(r'^\[(\d+)\]:\s+https?://\S+.*$', '', formatted_text, flags=re.MULTILINE)
    formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text).strip()
    return formatted_text

  def _nest_response_headings(self, text: str) -> str:
    """Demote markdown headings so they nest under the Response section.

    Example: "## Title" becomes "### Title".
    """
    if not text:
      return ""

    nested_lines: list[str] = []
    for line in text.splitlines():
      stripped = line.lstrip()
      if stripped.startswith("#"):
        hashes = len(stripped) - len(stripped.lstrip("#"))
        if hashes >= 1:
          content = stripped[hashes:]
          new_hashes = min(6, hashes + 1)
          nested_lines.append(f"{'#' * new_hashes}{content}")
          continue
      nested_lines.append(line)
    return "\n".join(nested_lines).strip()
