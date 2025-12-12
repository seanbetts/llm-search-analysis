"""Service for exporting interactions in various formats."""

from typing import Optional
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
        # Fetch interaction details
        response = self.interaction_service.get_interaction_details(interaction_id)
        if not response:
            return None

        # Convert Pydantic model to dict for easier access
        details = response.model_dump()

        lines = []
        lines.append(f"# Interaction {interaction_id}")
        lines.append("")

        # Prompt
        lines.append("## Prompt")
        lines.append(f"> {details.get('prompt', '')}")
        lines.append("")

        # Metadata
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

        # Use model_display_name if available, fallback to model
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

        # Response
        lines.append("## Response")
        response_text = self._format_response_text(
            details.get('response_text', ''),
            details.get('citations', [])
        )
        lines.append(response_text or "_No response text available._")
        lines.append("")

        # Search queries and sources
        search_queries = details.get('search_queries', [])

        if search_queries:
            lines.append("## Search Queries")
            for idx, query in enumerate(search_queries, 1):
                q_text = query.get('query') or ''
                lines.append(f"### Query {idx}: {q_text}")
            lines.append("")

            # For API data, sources are associated with queries
            if data_source == 'api':
                lines.append("## Sources (by Query)")
                for idx, query in enumerate(search_queries, 1):
                    sources = query.get('sources', [])
                    lines.append(f"### Query {idx} Sources ({len(sources)})")
                    for s_idx, src in enumerate(sources, 1):
                        title = src.get('title') or src.get('domain') or 'Unknown source'
                        url = src.get('url') or ''
                        domain = src.get('domain') or ''
                        snippet = src.get('snippet_text') or 'N/A'
                        if snippet == 'N/A' and src.get('title'):
                            snippet = src.get('title')
                        pub_date = src.get('pub_date')
                        pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                        lines.append(f"{s_idx}. [{title}]({url}) ({domain})")
                        lines.append(f"   - Snippet: {snippet}")
                        lines.append(f"   - Published: {pub_date_fmt}")
            # For network logs, sources aren't associated with specific queries
            else:
                all_sources = details.get('all_sources') or []
                if all_sources:
                    lines.append(f"## Sources Found ({len(all_sources)})")
                    lines.append("_Note: Network logs don't provide reliable query-to-source mapping._")
                    lines.append("")
                    for s_idx, src in enumerate(all_sources, 1):
                        title = src.get('title') or src.get('domain') or 'Unknown source'
                        url = src.get('url') or ''
                        domain = src.get('domain') or ''
                        snippet = src.get('snippet_text') or 'N/A'
                        if snippet == 'N/A' and src.get('title'):
                            snippet = src.get('title')
                        pub_date = src.get('pub_date')
                        pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                        lines.append(f"{s_idx}. [{title}]({url}) ({domain})")
                        lines.append(f"   - Snippet: {snippet}")
                        lines.append(f"   - Published: {pub_date_fmt}")
            lines.append("")

        # Sources used (citations)
        citations = details.get('citations', [])
        if citations:
            lines.append("## Sources Used")
            for c_idx, citation in enumerate(citations, 1):
                title = citation.get('title') or 'Unknown source'
                url = citation.get('url') or ''
                domain = urlparse(url).netloc if url else ''
                rank = citation.get('rank')
                rank_display = f" (Rank {rank})" if rank else ""
                snippet = citation.get('snippet_cited') or citation.get('text_snippet') or 'N/A'
                lines.append(f"{c_idx}. [{title}]({url}) ({domain}){rank_display}")
                lines.append(f"   - Snippet: {snippet}")

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
            citations: List of citation dicts

        Returns:
            Formatted response text
        """
        if not text:
            return ""

        import re

        # Extract reference-style links from the text
        # Pattern: [number]: URL "optional title"
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

        # Convert inline references [text][num] to [text](url)
        formatted_text = '\n'.join(content_lines)
        for ref_num, url in refs.items():
            # Pattern: [any text][ref_num]
            pattern = r'\[([^\]]+)\]\[' + re.escape(ref_num) + r'\]'
            replacement = r'[\1](' + url + ')'
            formatted_text = re.sub(pattern, replacement, formatted_text)

        return formatted_text
