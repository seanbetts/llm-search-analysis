"""
Network log parsers for different providers.

Parses captured network responses into standardized ProviderResponse format.
"""

import json
from typing import Dict, Any, List
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from providers.base_provider import (
    ProviderResponse,
    SearchQuery,
    Source,
    Citation
)


class NetworkLogParser:
    """Parser for network log responses from various providers."""

    @staticmethod
    def parse_chatgpt_log(
        network_response: Dict[str, Any],
        model: str,
        response_time_ms: int,
        extracted_response_text: str = ""
    ) -> ProviderResponse:
        """
        Parse ChatGPT network log response from event stream format.

        Args:
            network_response: Raw network response dictionary with 'body' containing SSE data
            model: Model used
            response_time_ms: Response time in milliseconds
            extracted_response_text: Response text extracted from page (optional)

        Returns:
            ProviderResponse object with parsed search data
        """
        search_queries: List[SearchQuery] = []
        sources: List[Source] = []
        citations: List[Citation] = []
        display_text = extracted_response_text or ""
        # Track links mentioned in response text but not in search results
        extra_links_count = 0

        # Metadata container for provider-specific extras
        response_metadata: Dict[str, Any] = {
            "default_model_slug": None,
            "image_behavior": None,
            "classifier": None,
            "safe_urls": [],
            "citation_ids": []
        }

        try:
            body = network_response.get('body', '')
            if not body:
                return NetworkLogParser._create_empty_response(
                    response_text, model, response_time_ms
                )

            # Temporary accumulators
            search_model_queries: List[str] = []
            search_result_groups: List[Dict[str, Any]] = []
            safe_urls: List[str] = []
            model_slug = None
            default_model_slug = None
            classifier = None
            last_assistant_message: Dict[str, Any] = {}
            content_fragments: List[str] = []

            # Parse Server-Sent Events lines
            lines = body.split('\n')
            for line in lines:
                if not line.startswith('data: '):
                    continue
                payload = None

                try:
                    data = json.loads(line[6:])
                except (json.JSONDecodeError, TypeError):
                    continue

                # Message payloads
                if isinstance(data, dict) and 'v' in data and isinstance(data.get('v'), dict):
                    payload = data['v']
                    message = payload.get('message')

                    if message:
                        author = message.get('author', {})
                        metadata = message.get('metadata', {})

                        # Capture model info if present
                        model_slug = metadata.get('model_slug', model_slug)
                        default_model_slug = metadata.get('default_model_slug', default_model_slug)

                        # Capture classifier block if present
                        if metadata.get('sonic_classification_result'):
                            classifier = metadata['sonic_classification_result']

                        # Capture search queries
                        smq = metadata.get('search_model_queries')
                        if smq and isinstance(smq, dict):
                            for q in smq.get('queries', []):
                                if isinstance(q, str):
                                    search_model_queries.append(q)

                        # Capture search result groups if present
                        if metadata.get('search_result_groups'):
                            groups = metadata['search_result_groups']
                            if isinstance(groups, list):
                                search_result_groups.extend(groups)

                        # Track assistant message for final response/citations
                        if author.get('role') == 'assistant':
                            last_assistant_message = message

                    # Some payloads have a list of groups directly in v
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict) and item.get('type') == 'search_result_group':
                            search_result_groups.append(item)

                # Patch/append operations or batched patches in list
                if isinstance(data, dict) and isinstance(data.get('v'), list):
                    for item in data.get('v', []):
                        if not isinstance(item, dict):
                            continue
                        path = item.get('p', '')
                        value = item.get('v')
                        operation = item.get('o', '')

                        if 'safe_urls' in path and isinstance(value, list):
                            safe_urls.extend(value)

                        if path.endswith('/message/content/parts/0') and isinstance(value, str):
                            content_fragments.append(value)

                        if 'search_result_groups' in path and '/entries' not in path:
                            if isinstance(value, list):
                                search_result_groups.extend(value)
                            elif isinstance(value, dict) and value.get('type') == 'search_result_group':
                                search_result_groups.append(value)

                        if 'search_result_groups' in path and '/entries' in path:
                            if not isinstance(value, list):
                                continue
                            parts = path.split('/')
                            try:
                                group_idx = int(parts[parts.index('search_result_groups') + 1])
                            except (ValueError, IndexError):
                                continue

                            while len(search_result_groups) <= group_idx:
                                search_result_groups.append({'entries': []})

                            if 'entries' not in search_result_groups[group_idx]:
                                search_result_groups[group_idx]['entries'] = []

                            if operation == 'replace':
                                search_result_groups[group_idx]['entries'] = value
                            else:
                                search_result_groups[group_idx]['entries'].extend(value)

                # Patch/append operations
                if isinstance(data, dict) and 'p' in data and 'v' in data:
                    path = data.get('p', '')
                    value = data.get('v')
                    operation = data.get('o', '')

                    # Safe URL updates
                    if 'safe_urls' in path and isinstance(value, list):
                        safe_urls.extend(value)

                    # Capture streamed content parts for assistant message
                    if path.endswith('/message/content/parts/0') and isinstance(value, str):
                        content_fragments.append(value)

                    # Entire group additions
                    if 'search_result_groups' in path and '/entries' not in path:
                        if isinstance(value, list):
                            search_result_groups.extend(value)
                        elif isinstance(value, dict) and value.get('type') == 'search_result_group':
                            search_result_groups.append(value)

                    # Entry-level additions
                    if 'search_result_groups' in path and '/entries' in path:
                        if not isinstance(value, list):
                            continue
                        parts = path.split('/')
                        try:
                            group_idx = int(parts[parts.index('search_result_groups') + 1])
                        except (ValueError, IndexError):
                            continue

                        while len(search_result_groups) <= group_idx:
                            search_result_groups.append({'entries': []})

                        if 'entries' not in search_result_groups[group_idx]:
                            search_result_groups[group_idx]['entries'] = []

                        # Replace vs append
                        if operation == 'replace':
                            search_result_groups[group_idx]['entries'] = value
                        else:
                            search_result_groups[group_idx]['entries'].extend(value)

            # Build sources with ranks per query
            # Map safe URLs for moderation info
            safe_url_set = set(safe_urls)

            def to_iso(ts: Any) -> str:
                try:
                    if ts is None:
                        return None
                    ts_float = float(ts)
                    return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
                except Exception:
                    return None

            refid_to_source = {}

            # Distribute result groups to queries sequentially
            if search_model_queries:
                grouped_results: List[List[Dict[str, Any]]] = []
                # Chunk groups roughly evenly across queries
                total_groups = len(search_result_groups)
                num_queries = len(search_model_queries)
                chunk_size = max(1, (total_groups + num_queries - 1) // num_queries)
                for i in range(num_queries):
                    start = i * chunk_size
                    end = start + chunk_size
                    grouped_results.append(search_result_groups[start:end])

                # Build SearchQuery objects with associated sources
                for q_idx, query_text in enumerate(search_model_queries):
                    query_sources: List[Source] = []
                    rank_counter = 1
                    groups_for_query = grouped_results[q_idx] if q_idx < len(grouped_results) else []

                    for group in groups_for_query:
                        domain = group.get('domain') or group.get('attribution') or ''
                        entries = group.get('entries', [])
                        for entry in entries:
                            if entry.get('type') != 'search_result':
                                continue
                            url = entry.get('url', '')
                            title = entry.get('title', '')
                            snippet = entry.get('snippet', '')
                            pub_date_iso = to_iso(entry.get('pub_date'))
                            ref_id = entry.get('ref_id', {})

                            metadata = {
                                'ref_id': ref_id,
                                'attribution': entry.get('attribution', domain),
                                'is_safe': url in safe_url_set,
                                'is_moderated': None,
                                'query_index': q_idx
                            }

                            source = Source(
                                url=url,
                                title=title,
                                domain=entry.get('attribution', domain),
                                rank=rank_counter,
                                pub_date=pub_date_iso,
                            snippet_text=snippet,
                            internal_score=None,
                            metadata=metadata
                        )
                        query_sources.append(source)
                        sources.append(source)
                        if isinstance(ref_id, dict) and {'turn_index', 'ref_type', 'ref_index'} <= set(ref_id.keys()):
                            key = f"turn{ref_id.get('turn_index')}{ref_id.get('ref_type')}{ref_id.get('ref_index')}"
                            refid_to_source[key] = source
                        rank_counter += 1

                    search_queries.append(SearchQuery(
                        query=query_text,
                        sources=query_sources,
                        order_index=q_idx
                    ))

            # Final response text and citations
            assembled_content = ''.join(content_fragments).strip()
            # Prefer DOM-extracted display text; fallback to assembled stream or flattened message
            if not display_text:
                if assembled_content:
                    display_text = NetworkLogParser._clean_response_text(assembled_content)
                elif last_assistant_message:
                    flattened = NetworkLogParser._flatten_assistant_message(last_assistant_message)
                    if flattened:
                        display_text = flattened

            citations = []
            # Use stream content to detect citation markers (DOM usually strips them)
            citation_source_text = assembled_content or display_text
            if citation_source_text and refid_to_source:
                citation_keys = NetworkLogParser._extract_citation_keys(citation_source_text)
                seen = set()
                for key in citation_keys:
                    if key in seen:
                        continue
                    seen.add(key)
                    source = refid_to_source.get(key)
                    if source:
                        citations.append(Citation(
                            url=source.url,
                            title=source.title,
                            rank=source.rank,
                            metadata={
                                "citation_id": key,
                                "ref_id": getattr(source, "metadata", {}).get("ref_id"),
                                "query_index": getattr(source, "metadata", {}).get("query_index"),
                                "snippet": getattr(source, "snippet_text", None),
                                "pub_date": source.pub_date
                            }
                        ))
                        response_metadata["citation_ids"].append(key)

            # Metadata assembly
            response_metadata["default_model_slug"] = default_model_slug
            response_metadata["classifier"] = classifier
            response_metadata["safe_urls"] = list(safe_url_set)
            response_metadata["image_behavior"] = NetworkLogParser._extract_image_behavior(last_assistant_message) if last_assistant_message else None
            # Compute extra links: URLs in display text not present in search result URLs
            extra_links_count = 0
            if display_text:
                import re
                from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

                def normalize(url: str) -> str:
                    if not url:
                        return ""
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    # Drop tracking params
                    qs = {k: v for k, v in qs.items() if not k.lower().startswith('utm_') and k.lower() not in ['source']}
                    # For YouTube, keep the video id
                    if 'v' in qs:
                        keep_qs = {'v': qs['v']}
                    else:
                        keep_qs = qs
                    new_query = urlencode(keep_qs, doseq=True)
                    normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))
                    return normalized
                resp_urls = set(normalize(u) for u in re.findall(r'https?://[^\s)]+', display_text))
                source_urls = {normalize(s.url) for s in sources if s.url}
                extra_links_count = len([u for u in resp_urls if u and u not in source_urls])
            response_metadata["extra_links_count"] = extra_links_count

            # Use discovered model slug if present
            if model_slug:
                model = model_slug

        except Exception as e:
            print(f"Error parsing ChatGPT event stream: {str(e)}")
            return NetworkLogParser._create_empty_response(
                display_text, model, response_time_ms
            )

        return ProviderResponse(
            response_text=display_text,
            search_queries=search_queries,
            sources=sources,
            citations=citations,
            raw_response=network_response,
            model=model,
            provider='openai',
            response_time_ms=response_time_ms,
            metadata=response_metadata
        )

    @staticmethod
    def _extract_inline_citations(response_text: str, sources: List[Source]) -> List[Citation]:
        """
        Extract citations from inline source attributions in ChatGPT response text.

        ChatGPT includes source attributions as standalone lines after cited content,
        typically showing the domain or source name.

        Args:
            response_text: The response text with inline attributions
            sources: List of sources to match against

        Returns:
            List of Citation objects
        """
        citations = []

        # Create a mapping of domains to sources for quick lookup
        domain_to_source = {}
        for source in sources:
            # Try multiple domain variations
            domain = source.domain.lower()
            domain_to_source[domain] = source

            # Also try title if it looks like a source name
            if source.title:
                title_lower = source.title.lower()
                domain_to_source[title_lower] = source

        # Split response into lines to find standalone source attributions
        lines = response_text.split('\n')

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines, headings (with emojis), and very long lines (likely content)
            if not line_stripped or len(line_stripped) > 100:
                continue

            # Skip lines that are clearly content (have sentence structure)
            if line_stripped.endswith(',') or line_stripped.endswith(';'):
                continue

            # Check if this line matches any source domain or title
            line_lower = line_stripped.lower()

            for key, source in domain_to_source.items():
                # Match if the line is the domain/title (exact or contains)
                if key in line_lower or line_lower in key:
                    # Make sure this isn't already a citation for this URL
                    if not any(c.url == source.url for c in citations):
                        citation = Citation(
                            url=source.url,
                            title=source.title,
                            rank=source.rank,
                            snippet_used=line_stripped  # The attribution line
                        )
                        citations.append(citation)
                        break

        return citations

    @staticmethod
    def _flatten_assistant_message(message: Dict[str, Any]) -> str:
        """Flatten assistant message content into plain text."""
        if not message:
            return ""
        content = message.get('content', {})
        # Web UI uses parts under "parts" when content_type=text; also support other shapes
        parts = content.get('parts') if isinstance(content, dict) else content
        if parts is None:
            return ""
        if isinstance(parts, list):
            return "".join([str(p) for p in parts])
        return str(parts)

    @staticmethod
    def _clean_response_text(text: str) -> str:
        """Remove private-use markers and tidy streamed content."""
        cleaned = ''.join(ch for ch in text if not (0xE000 <= ord(ch) <= 0xF8FF))
        return cleaned.strip()

    @staticmethod
    def _extract_citation_keys(text: str) -> List[str]:
        """Extract citation ids like turn0news4 from streamed content."""
        import re
        return re.findall(r"turn\d+(?:news|search)\d+", text)

    @staticmethod
    def _extract_image_behavior(message: Dict[str, Any]) -> Dict[str, Any]:
        """Detect image groups or carousels from assistant message content."""
        if not message:
            return {"has_image_group": False, "image_groups": []}
        content = message.get('content', {})
        parts = content.get('parts') if isinstance(content, dict) else content
        image_groups = []
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict):
                    img_group = part.get('image_group') or part.get('images')
                    if img_group:
                        image_groups.append(img_group)
        return {
            "has_image_group": bool(image_groups),
            "image_groups": image_groups
        }

    @staticmethod
    def _create_empty_response(
        response_text: str,
        model: str,
        response_time_ms: int
    ) -> ProviderResponse:
        """Create an empty ProviderResponse."""
        return ProviderResponse(
            response_text=response_text,
            search_queries=[],
            sources=[],
            citations=[],
            raw_response={},
            model=model,
            provider='openai',
            response_time_ms=response_time_ms
        )

    @staticmethod
    def parse_claude_log(
        network_response: Dict[str, Any],
        model: str,
        response_time_ms: int
    ) -> ProviderResponse:
        """
        Parse Claude network log response.

        Args:
            network_response: Raw network response dictionary
            model: Model used
            response_time_ms: Response time in milliseconds

        Returns:
            ProviderResponse object with network log data
        """
        # TODO: Implement Claude-specific parsing
        search_queries = []
        sources = []
        citations = []
        response_text = ""

        return ProviderResponse(
            response_text=response_text,
            search_queries=search_queries,
            sources=sources,
            citations=citations,
            raw_response=network_response,
            model=model,
            provider='anthropic',
            response_time_ms=response_time_ms
        )

    @staticmethod
    def parse_gemini_log(
        network_response: Dict[str, Any],
        model: str,
        response_time_ms: int
    ) -> ProviderResponse:
        """
        Parse Gemini network log response.

        Args:
            network_response: Raw network response dictionary
            model: Model used
            response_time_ms: Response time in milliseconds

        Returns:
            ProviderResponse object with network log data
        """
        # TODO: Implement Gemini-specific parsing
        search_queries = []
        sources = []
        citations = []
        response_text = ""

        return ProviderResponse(
            response_text=response_text,
            search_queries=search_queries,
            sources=sources,
            citations=citations,
            raw_response=network_response,
            model=model,
            provider='google',
            response_time_ms=response_time_ms
        )
