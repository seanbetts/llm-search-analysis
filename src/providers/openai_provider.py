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
                input=prompt,
                tools=[{
                    "type": "web_search",
                }],
                tool_choice="auto",
                include=["web_search_call.action.sources"]  # Request sources in response
            )

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Parse the response
            return self._parse_response(response, model, response_time_ms)

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
        """
        Parse OpenAI Responses API response into standardized format.

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

        # Extract response from output array
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                # Handle web_search_call type
                if output_item.type == "web_search_call":
                    if output_item.status == "completed" and hasattr(output_item, 'action'):
                        action = output_item.action

                        # Extract search query
                        if hasattr(action, 'query') and action.query:
                            search_queries.append(SearchQuery(query=action.query))

                        # Extract sources (requires include=["web_search_call.action.sources"])
                        if hasattr(action, 'sources') and action.sources:
                            for source in action.sources:
                                sources.append(Source(
                                    url=source.url if hasattr(source, 'url') else "",
                                    title=source.title if hasattr(source, 'title') else None,
                                    domain=urlparse(source.url).netloc if hasattr(source, 'url') else None
                                ))

                # Handle message type
                elif output_item.type == "message":
                    if output_item.status == "completed" and hasattr(output_item, 'content'):
                        for content_item in output_item.content:
                            if content_item.type == "output_text":
                                response_text += content_item.text

                                # Extract citations from annotations
                                if hasattr(content_item, 'annotations') and content_item.annotations:
                                    for annotation in content_item.annotations:
                                        if annotation.type == "url_citation":
                                            citations.append(Citation(
                                                url=annotation.url if hasattr(annotation, 'url') else "",
                                                title=annotation.title if hasattr(annotation, 'title') else None
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
