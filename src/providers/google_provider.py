"""
Google Gemini provider implementation with Search Grounding.
"""

import time
from typing import List
from urllib.parse import urlparse
from google.genai import Client
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

from .base_provider import (
    BaseProvider,
    ProviderResponse,
    SearchQuery,
    Source,
    Citation
)


class GoogleProvider(BaseProvider):
    """Google Gemini provider implementation."""

    SUPPORTED_MODELS = [
        "gemini-3-pro-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]

    def __init__(self, api_key: str):
        """
        Initialize Google provider.

        Args:
            api_key: Google AI API key
        """
        super().__init__(api_key)
        self.client = Client(api_key=api_key)

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "google"

    def get_supported_models(self) -> List[str]:
        """Get list of supported Google models."""
        return self.SUPPORTED_MODELS

    def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
        """
        Send prompt to Google Gemini with search grounding.

        Args:
            prompt: User's prompt
            model: Model to use (e.g., "gemini-3.0")

        Returns:
            ProviderResponse with search data

        Raises:
            ValueError: If model is not supported
            Exception: If API call fails
        """
        if not self.validate_model(model):
            raise ValueError(
                f"Model '{model}' not supported. "
                f"Supported models: {self.SUPPORTED_MODELS}"
            )

        # Track response time
        start_time = time.time()

        try:
            # Create config with Google Search grounding
            # Must wrap GoogleSearch in Tool object for it to work
            tool = Tool(google_search=GoogleSearch())
            config = GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                tools=[tool],
            )

            # Generate content using new SDK
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Parse the response
            return self._parse_response(response, model, response_time_ms)

        except Exception as e:
            raise Exception(f"Google API error: {str(e)}")

    def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
        """
        Parse Google response into standardized format.

        Args:
            response: Raw Google API response
            model: Model used
            response_time_ms: Response time in milliseconds

        Returns:
            ProviderResponse object
        """
        search_queries = []
        sources = []
        citations = []
        response_text = ""

        # Extract response text
        if response.text:
            response_text = response.text

        # Extract grounding metadata if available
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata = candidate.grounding_metadata

                    # Extract search queries from web_search_queries field
                    if hasattr(metadata, 'web_search_queries') and metadata.web_search_queries:
                        for query in metadata.web_search_queries:
                            search_queries.append(SearchQuery(query=query))

                    # Extract sources from grounding chunks
                    if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                        for chunk in metadata.grounding_chunks:
                            if hasattr(chunk, 'web') and chunk.web:
                                sources.append(Source(
                                    url=chunk.web.uri if hasattr(chunk.web, 'uri') else "",
                                    title=chunk.web.title if hasattr(chunk.web, 'title') else None,
                                    domain=urlparse(chunk.web.uri).netloc if hasattr(chunk.web, 'uri') else None
                                ))

                    # Extract citations from grounding supports
                    if hasattr(metadata, 'grounding_supports') and metadata.grounding_supports:
                        for support in metadata.grounding_supports:
                            if hasattr(support, 'segment') and hasattr(support, 'grounding_chunk_indices'):
                                # Citations are linked to chunks
                                for idx in support.grounding_chunk_indices:
                                    if idx < len(metadata.grounding_chunks):
                                        chunk = metadata.grounding_chunks[idx]
                                        if hasattr(chunk, 'web') and chunk.web:
                                            citations.append(Citation(
                                                url=chunk.web.uri if hasattr(chunk.web, 'uri') else "",
                                                title=chunk.web.title if hasattr(chunk.web, 'title') else None,
                                            ))

        # Remove duplicate citations
        seen_urls = set()
        unique_citations = []
        for citation in citations:
            if citation.url not in seen_urls:
                seen_urls.add(citation.url)
                unique_citations.append(citation)

        return ProviderResponse(
            response_text=response_text,
            search_queries=search_queries,
            sources=sources,
            citations=unique_citations,
            raw_response={},  # Google responses may not be easily serializable
            model=model,
            provider=self.get_provider_name(),
            response_time_ms=response_time_ms
        )
