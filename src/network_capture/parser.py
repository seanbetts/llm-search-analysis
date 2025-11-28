"""
Network log parsers for different providers.

Parses captured network responses into standardized ProviderResponse format.
"""

import json
from typing import Dict, Any, List
import sys
from pathlib import Path

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
        search_queries = []
        sources = []
        citations = []
        response_text = extracted_response_text

        try:
            # Get event stream body
            body = network_response.get('body', '')
            if not body:
                return NetworkLogParser._create_empty_response(
                    response_text, model, response_time_ms
                )

            # Parse Server-Sent Events format
            search_model_queries = []
            search_result_groups = []

            # Split by lines and parse JSON data
            lines = body.split('\n')
            for line in lines:
                if not line.startswith('data: '):
                    continue

                try:
                    # Extract JSON from "data: {...}"
                    json_str = line[6:]  # Remove "data: " prefix
                    data = json.loads(json_str)

                    # Extract search queries
                    if 'v' in data and 'message' in data['v']:
                        message = data['v']['message']
                        metadata = message.get('metadata', {})

                        # Search model queries (what ChatGPT searched for)
                        if 'search_model_queries' in metadata:
                            query_data = metadata['search_model_queries']
                            if 'queries' in query_data:
                                search_model_queries.extend(query_data['queries'])

                        # Search result groups (search results with sources)
                        if 'search_result_groups' in metadata:
                            search_result_groups.extend(metadata['search_result_groups'])

                    # Also check for patch/append operations that add search results
                    if 'p' in data and 'v' in data:
                        path = data.get('p', '')
                        value = data.get('v')
                        operation = data.get('o', '')

                        # Handle append operations for search_result_groups
                        if 'search_result_groups' in path:
                            if isinstance(value, list):
                                # Direct array of groups
                                search_result_groups.extend(value)
                            elif isinstance(value, dict) and value.get('type') == 'search_result_group':
                                # Single group
                                search_result_groups.append(value)

                        # Handle append operations for entries within a group
                        # Path like: "/message/metadata/search_result_groups/1/entries"
                        if '/entries' in path and 'search_result_groups' in path:
                            if isinstance(value, list):
                                # Find the group index from the path
                                # Path format: "/message/metadata/search_result_groups/1/entries"
                                parts = path.split('/')
                                try:
                                    group_idx = int(parts[parts.index('search_result_groups') + 1])
                                    # Make sure we have enough groups
                                    while len(search_result_groups) <= group_idx:
                                        search_result_groups.append({'entries': []})
                                    # Add entries to the group
                                    if 'entries' not in search_result_groups[group_idx]:
                                        search_result_groups[group_idx]['entries'] = []
                                    search_result_groups[group_idx]['entries'].extend(value)
                                except (ValueError, IndexError):
                                    pass

                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            # Parse search queries
            for query_text in search_model_queries:
                search_queries.append(SearchQuery(
                    query=query_text,
                    sources=[]  # Will populate sources separately
                ))

            # Parse search results into sources
            rank = 1
            for group in search_result_groups:
                domain = group.get('domain', '')
                entries = group.get('entries', [])

                for entry in entries:
                    if entry.get('type') != 'search_result':
                        continue

                    url = entry.get('url', '')
                    title = entry.get('title', '')
                    snippet = entry.get('snippet', '')
                    pub_date = entry.get('pub_date')
                    attribution = entry.get('attribution', domain)
                    ref_id = entry.get('ref_id', {})

                    source = Source(
                        url=url,
                        title=title,
                        domain=attribution,
                        rank=rank,
                        snippet_text=snippet,
                        internal_score=None,  # Not provided in this format
                        metadata={
                            'pub_date': pub_date,
                            'ref_id': ref_id
                        }
                    )
                    sources.append(source)
                    rank += 1

            # TODO: Extract citations from response text annotations
            # For now, citations extraction would require parsing the response text
            # which may have citation markers like [1], [2], etc.

        except Exception as e:
            print(f"Error parsing ChatGPT event stream: {str(e)}")
            return NetworkLogParser._create_empty_response(
                response_text, model, response_time_ms
            )

        return ProviderResponse(
            response_text=response_text,
            search_queries=search_queries,
            sources=sources,
            citations=citations,
            raw_response=network_response,
            model=model,
            provider='openai',
            response_time_ms=response_time_ms
        )

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
