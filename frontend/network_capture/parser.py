"""Network log parsers for different providers.

Parses captured network responses into standardized ProviderResponse format.

IMPORTANT NOTE ON CHATGPT NETWORK LOGS:
ChatGPT network logs do NOT provide reliable mapping between search queries
and their results. Sources are tracked separately from queries. See
NETWORK_LOG_FINDINGS.md for full analysis.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Import data models from backend
from backend.app.services.providers.base_provider import (
    Citation,
    ProviderResponse,
    SearchQuery,
    Source,
)


class NetworkLogParser:
    """Parser for network log responses from various providers."""

    @staticmethod
    def _normalize_url_for_match(url: str) -> str:
        """Normalize URLs for matching across sources and citations.

        ChatGPT often includes tracking parameters or minor variations in URLs
        between search results and markdown citations. For matching purposes we
        aggressively normalize to scheme+host+path, stripping query/fragment and
        common host prefixes.
        """
        from urllib.parse import urlparse, urlunparse

        if not isinstance(url, str) or not url.strip():
            return ""
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path or ""
        if path.endswith("/") and path != "/":
            path = path[:-1]
        normalized = urlunparse((parsed.scheme or "https", host, path, "", "", ""))
        return normalized

    @staticmethod
    def parse_chatgpt_response_text_fallback(
        extracted_response_text: str,
        model: str,
        response_time_ms: int,
    ) -> ProviderResponse:
        """Fallback parser that extracts citations from response markdown only.

        When the ChatGPT streaming/event payload isn't captured reliably, we can still
        recover citations from the copied markdown footnotes:

          [1]: https://example.com "Title"

        This does not provide search queries or full search results, but it allows
        the app to persist and display Sources Used/Extra Links for the interaction.
        """
        if not extracted_response_text:
            return NetworkLogParser._create_empty_response("", model, response_time_ms)

        footnote_pattern = r'^\[(\d+)\]:\s+(https?://\S+)(?:\s+"([^"]+)")?\s*$'
        seen_urls: set[str] = set()
        citations: List[Citation] = []

        for match in re.finditer(footnote_pattern, extracted_response_text, flags=re.MULTILINE):
            url = match.group(2)
            norm = NetworkLogParser._normalize_url_for_match(url)
            if not norm or norm in seen_urls:
                continue
            seen_urls.add(norm)
            title = match.group(3) if match.group(3) else None
            citations.append(Citation(url=url, title=title, rank=None))

        return ProviderResponse(
            response_text=extracted_response_text,
            search_queries=[],
            sources=[],
            citations=citations,
            raw_response={"fallback": "response_text_only"},
            model=model,
            provider="openai",
            response_time_ms=response_time_ms,
            data_source="web",
        )

    @staticmethod
    def parse_chatgpt_log(
        network_response: Dict[str, Any],
        model: str,
        response_time_ms: int,
        extracted_response_text: str = ""
    ) -> ProviderResponse:
        """Parse ChatGPT network log response from event stream format.

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
                return NetworkLogParser._create_empty_response("", model, response_time_ms)

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

            def strip_html_tags(text: str) -> str:
                """Remove HTML tags from text."""
                if not isinstance(text, str):
                    return text
                # Remove HTML tags using regex
                return re.sub(r'<[^>]+>', '', text).strip()

            def to_iso(ts: Any) -> str:
                """Convert timestamp-like values into ISO-8601 strings or return cleaned string."""
                try:
                    if ts is None:
                        return None
                    # Strip HTML tags if ts is a string
                    if isinstance(ts, str):
                        cleaned = strip_html_tags(ts)
                        # Try to convert to timestamp
                        try:
                            ts_float = float(cleaned)
                            return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
                        except (ValueError, TypeError):
                            # If conversion fails, return the cleaned string as-is
                            # (ChatGPT sometimes returns pre-formatted dates)
                            return cleaned if cleaned else None
                    # For non-string values, try direct conversion
                    ts_float = float(ts)
                    return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
                except Exception:
                    return None

            normalize = NetworkLogParser._normalize_url_for_match

            # Collect additional entries directly from the SSE body to avoid missing groups
            def extract_entries_from_body(body_text: str) -> List[Dict[str, Any]]:
                """Parse SSE body for extra search result groups."""
                entries: List[Dict[str, Any]] = []
                lines = body_text.split('\n')
                for line in lines:
                    if not line.startswith('data: '):
                        continue
                    try:
                        payload = json.loads(line[6:])
                    except Exception:
                        continue
                    if not isinstance(payload, dict):
                        continue

                    # Helper to append any groups found
                    def add_groups(groups):
                        """Append entries extracted from SSE payload groups."""
                        if isinstance(groups, list):
                            for g in groups:
                                if isinstance(g, dict):
                                    entries.extend(g.get('entries', []) or [])
                        elif isinstance(groups, dict):
                            entries.extend(groups.get('entries', []) or [])

                    v = payload.get('v')
                    if isinstance(v, dict) and 'message' in v:
                        meta = v['message'].get('metadata', {})
                        add_groups(meta.get('search_result_groups'))
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict) and item.get('type') == 'search_result_group':
                                add_groups(item)
                    if isinstance(payload.get('v'), list):
                        for item in payload['v']:
                            if not isinstance(item, dict):
                                continue
                            path = item.get('p', '')
                            val = item.get('v')
                            if 'search_result_groups' in path:
                                add_groups(val)
                    if 'p' in payload:
                        path = payload.get('p', '')
                        val = payload.get('v')
                        if 'search_result_groups' in path:
                            add_groups(val)

                return [e for e in entries if isinstance(e, dict)]

            # Parse all sources from search result groups plus any missed entries in the body
            extra_entries = extract_entries_from_body(body)
            rank_counter = 1
            seen_urls = set()  # Deduplicate sources by URL
            combined_groups = list(search_result_groups)  # shallow copy
            if extra_entries:
                combined_groups.append({'entries': extra_entries})

            for group in combined_groups:
                domain = group.get('domain') or group.get('attribution') or ''
                entries = group.get('entries', [])

                for entry in entries:
                    if entry.get('type') != 'search_result':
                        continue

                    url = entry.get('url', '')
                    if not url:
                        continue

                    # Deduplicate by normalized URL
                    clean = normalize(url)
                    if clean in seen_urls:
                        continue
                    seen_urls.add(clean)

                    title = strip_html_tags(entry.get('title', ''))
                    snippet = strip_html_tags(entry.get('snippet', ''))
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
                        search_description=snippet,
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
            response_metadata["image_behavior"] = (
                NetworkLogParser._extract_image_behavior(last_assistant_message) if last_assistant_message else None
            )
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
            extra_links_count=extra_links_count,
            data_source='web'
        )

    @staticmethod
    def _extract_markdown_citations(
      response_text: str, sources: List[Source]
    ) -> Tuple[List[Citation], int]:
        """Extract citations from markdown reference links in ChatGPT response text.

        ChatGPT uses markdown reference format: [N]: URL "Title"

        Args:
            response_text: The response text with markdown reference links
            sources: List of sources fetched from search results

        Returns:
            Tuple of (List of Citation objects, extra_links_count)
            - Citations include both sources used (from search) and extra links
            - extra_links_count is the number of citations NOT from search results
        """
        normalize = NetworkLogParser._normalize_url_for_match
        # Build URL mapping from sources for quick lookup
        source_map = {normalize(s.url): s for s in sources}

        citations: List[Citation] = []
        extra_links_count = 0
        seen_norm_urls = set()

        # 1) Reference-style definitions: [N]: URL "Title"
        ref_def_pattern = r'^\[(\d+)\]:\s*(https?://[^\s"]+)(?:\s+"([^"]*)")?\s*$'
        def _normalize_snippet(snippet: Optional[str]) -> Optional[str]:
            if snippet is None:
                return None
            normalized = snippet.strip()
            return normalized or None

        def strip_html(text: str) -> str:
            """Remove HTML tags from text."""
            if not isinstance(text, str):
                return text
            return re.sub(r'<[^>]+>', '', text).strip()

        for match in re.finditer(ref_def_pattern, response_text, flags=re.MULTILINE):
            ref_num, url, title = match.group(1), match.group(2), strip_html(match.group(3) or "")
            norm = normalize(url)
            if norm in seen_norm_urls:
                continue
            seen_norm_urls.add(norm)

            if norm in source_map:
                src = source_map[norm]
                snippet = _normalize_snippet(
                    getattr(src, "search_description", None) or getattr(src, "snippet_text", None)
                )
                citations.append(Citation(
                    url=src.url,
                    title=src.title or title,
                    rank=src.rank,
                    text_snippet=snippet,
                    metadata={
                        "citation_number": int(ref_num),
                        "query_index": None,  # Network logs don't provide query association
                        "snippet": getattr(src, "search_description", None) or getattr(src, "snippet_text", None),
                        "pub_date": src.pub_date
                    }
                ))
            else:
                extra_links_count += 1
                citations.append(Citation(
                    url=url,
                    title=title or "",
                    rank=None,
                    metadata={
                        "citation_number": int(ref_num),
                        "is_extra_link": True
                    }
                ))

        # 2) Inline markdown links: [text](URL) -- ignore image markdown ![...](...)
        inline_pattern = r'(?<!!)\[([^\]]+)\]\((https?://[^\s)]+)\)'
        for match in re.finditer(inline_pattern, response_text):
            link_text, url = strip_html(match.group(1)), match.group(2)
            norm = normalize(url)
            if norm in seen_norm_urls:
                continue
            seen_norm_urls.add(norm)

            if norm in source_map:
                src = source_map[norm]
                snippet = _normalize_snippet(
                    getattr(src, "search_description", None) or getattr(src, "snippet_text", None)
                )
                citations.append(Citation(
                    url=src.url,
                    title=src.title or link_text,
                    rank=src.rank,
                    text_snippet=snippet,
                    metadata={
                        "citation_number": None,
                        "query_index": None,
                        "snippet": getattr(src, "search_description", None) or getattr(src, "snippet_text", None),
                        "pub_date": src.pub_date
                    }
                ))
            else:
                extra_links_count += 1
                citations.append(Citation(
                    url=url,
                    title=link_text,
                    rank=None,
                    metadata={
                        "citation_number": None,
                        "is_extra_link": True
                    }
                ))

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
            response_time_ms=response_time_ms,
            data_source='web'
        )

    @staticmethod
    def parse_claude_log(
        network_response: Dict[str, Any],
        model: str,
        response_time_ms: int
    ) -> ProviderResponse:
        """Parse Claude network log response.

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
        """Parse Gemini network log response.

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
