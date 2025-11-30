"""
Network log parsers for different providers.

Parses captured network responses into standardized ProviderResponse format.

IMPORTANT NOTE ON CHATGPT NETWORK LOGS:
ChatGPT network logs do NOT provide reliable mapping between search queries
and their results. Sources are tracked separately from queries. See
NETWORK_LOG_FINDINGS.md for full analysis.
"""

import json
import re
from typing import Dict, Any, List, Tuple
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

            # Build search queries WITHOUT source association
            # (Network logs don't provide reliable query-to-source mapping)
            for q_idx, query_text in enumerate(search_model_queries):
                search_queries.append(SearchQuery(
                    query=query_text,
                    sources=[],  # No source association for network logs
                    order_index=q_idx
                ))

            # Build sources independently (associate with response, not individual queries)
            safe_url_set = set(safe_urls)

            def to_iso(ts: Any) -> str:
                try:
                    if ts is None:
                        return None
                    ts_float = float(ts)
                    return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
                except Exception:
                    return None

            def clean_url(url: str) -> str:
                """Normalize URL for comparison (remove tracking params)."""
                from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
                if not url:
                    return ""
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                # Drop tracking params
                qs = {k: v for k, v in qs.items() if not k.lower().startswith('utm_') and k.lower() not in ['source']}
                new_query = urlencode(qs, doseq=True)
                normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))
                return normalized

            # Parse all sources from search result groups
            rank_counter = 1
            seen_urls = set()  # Deduplicate sources by URL

            for group in search_result_groups:
                domain = group.get('domain') or group.get('attribution') or ''
                entries = group.get('entries', [])

                for entry in entries:
                    if entry.get('type') != 'search_result':
                        continue

                    url = entry.get('url', '')
                    if not url:
                        continue

                    # Deduplicate by normalized URL
                    clean = clean_url(url)
                    if clean in seen_urls:
                        continue
                    seen_urls.add(clean)

                    title = entry.get('title', '')
                    snippet = entry.get('snippet', '')
                    pub_date_iso = to_iso(entry.get('pub_date'))
                    ref_id = entry.get('ref_id', {})

                    metadata = {
                        'ref_id': ref_id,
                        'attribution': entry.get('attribution', domain),
                        'is_safe': url in safe_url_set
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
                    sources.append(source)
                    rank_counter += 1

            # Final response text
            assembled_content = ''.join(content_fragments).strip()
            # Prefer DOM-extracted display text; fallback to assembled stream or flattened message
            if not display_text:
                if assembled_content:
                    display_text = NetworkLogParser._clean_response_text(assembled_content)
                elif last_assistant_message:
                    flattened = NetworkLogParser._flatten_assistant_message(last_assistant_message)
                    if flattened:
                        display_text = flattened

            # Extract citations from markdown reference links: [N]: URL "Title"
            citations, extra_links_count = NetworkLogParser._extract_markdown_citations(
                display_text, sources
            )

            # Metadata assembly
            response_metadata["default_model_slug"] = default_model_slug
            response_metadata["classifier"] = classifier
            response_metadata["safe_urls"] = list(safe_url_set)
            response_metadata["image_behavior"] = NetworkLogParser._extract_image_behavior(last_assistant_message) if last_assistant_message else None
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
            metadata=response_metadata,
            extra_links_count=extra_links_count
        )

    @staticmethod
    def _extract_markdown_citations(response_text: str, sources: List[Source]) -> Tuple[List[Citation], int]:
        """
        Extract citations from markdown reference links in ChatGPT response text.

        ChatGPT uses markdown reference format: [N]: URL "Title"

        Args:
            response_text: The response text with markdown reference links
            sources: List of sources fetched from search results

        Returns:
            Tuple of (List of Citation objects, extra_links_count)
            - Citations include both sources used (from search) and extra links
            - extra_links_count is the number of citations NOT from search results
        """
        from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

        def clean_url(url: str) -> str:
            """Normalize URL for comparison (remove tracking params)."""
            if not url:
                return ""
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            # Drop tracking params
            qs = {k: v for k, v in qs.items() if not k.lower().startswith('utm_') and k.lower() not in ['source']}
            new_query = urlencode(qs, doseq=True)
            normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))
            return normalized

        # Parse markdown reference links: [N]: URL "Title"
        link_pattern = r'\[(\d+)\]:\s*(https?://[^\s\"]+)(?:\s+"([^"]*)")?'
        reference_links = re.findall(link_pattern, response_text)

        # Create URL mapping from sources for quick lookup
        source_map = {clean_url(s.url): s for s in sources}

        citations = []
        extra_links_count = 0

        for ref_num, url, title in reference_links:
            clean = clean_url(url)

            if clean in source_map:
                # Source used - came from search results
                source = source_map[clean]
                citation = Citation(
                    url=source.url,
                    title=source.title or title,
                    rank=source.rank,
                    metadata={
                        "citation_number": int(ref_num),
                        "query_index": None,  # Network logs don't provide query association
                        "snippet": source.snippet_text,
                        "pub_date": source.pub_date
                    }
                )
                citations.append(citation)
            else:
                # Extra link - NOT from search results (training data or other sources)
                extra_links_count += 1
                citation = Citation(
                    url=url,
                    title=title or "",
                    rank=None,  # No rank since it's not from search results
                    metadata={
                        "citation_number": int(ref_num),
                        "is_extra_link": True
                    }
                )
                citations.append(citation)

        return citations, extra_links_count

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
