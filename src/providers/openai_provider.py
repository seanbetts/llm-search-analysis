"""
OpenAI provider implementation using the Responses API with web_search tool.
"""

import time
from typing import List
from urllib.parse import urlparse
from openai import OpenAI

from .base_provider import (
    BaseProvider,
    ProviderResponse,
    SearchQuery,
    Source,
    Citation
)


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation."""

    SUPPORTED_MODELS = [
        "gpt-5.1",
        "gpt-5-mini",
        "gpt-5-nano",
    ]

    def __init__(self, api_key: str):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
        """
        super().__init__(api_key)
        self.client = OpenAI(api_key=api_key)

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openai"

    def get_supported_models(self) -> List[str]:
        """Get list of supported OpenAI models."""
        return self.SUPPORTED_MODELS

    def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
        """
        Send prompt to OpenAI with web_search enabled.

        Args:
            prompt: User's prompt
            model: Model to use (e.g., "gpt-5.1")

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
            # Call OpenAI Responses API with web_search tool
            response = self.client.responses.create(
                model=model,
                tools=[{
                    "type": "web_search",
                }],
                tool_choice="auto",
                include=["web_search_call.action.sources"],
                input=prompt
            )

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Parse the response
            return self._parse_response(response, model, response_time_ms)

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
        """
        Parse OpenAI response into standardized format.

        Args:
            response: Raw OpenAI API response
            model: Model used
            response_time_ms: Response time in milliseconds

        Returns:
            ProviderResponse object
        """
        search_queries = []
        sources = []
        citations = []
        response_text = ""

        # Extract response items
        for item in response.items:
            # Extract web_search_call items
            if item.type == "web_search_call":
                if item.status == "completed" and item.action:
                    # Extract search query
                    if item.action.type == "search" and item.action.query:
                        search_queries.append(SearchQuery(
                            query=item.action.query
                        ))

                    # Extract sources
                    if hasattr(item.action, 'sources') and item.action.sources:
                        for source in item.action.sources:
                            sources.append(Source(
                                url=source.url,
                                title=source.title if hasattr(source, 'title') else None,
                                domain=urlparse(source.url).netloc
                            ))

            # Extract message (final response)
            elif item.type == "message":
                if item.status == "completed" and item.content:
                    for content in item.content:
                        if content.type == "output_text":
                            response_text = content.text

                            # Extract citations from annotations
                            if hasattr(content, 'annotations') and content.annotations:
                                for annotation in content.annotations:
                                    if annotation.type == "url_citation":
                                        citations.append(Citation(
                                            url=annotation.url,
                                            title=annotation.title if hasattr(annotation, 'title') else None,
                                        ))

        return ProviderResponse(
            response_text=response_text,
            search_queries=search_queries,
            sources=sources,
            citations=citations,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else {},
            model=model,
            provider=self.get_provider_name(),
            response_time_ms=response_time_ms
        )
