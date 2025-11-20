"""
Anthropic Claude provider implementation with web search.
"""

import time
from typing import List
from urllib.parse import urlparse
from anthropic import Anthropic

from .base_provider import (
    BaseProvider,
    ProviderResponse,
    SearchQuery,
    Source,
    Citation
)


class AnthropicProvider(BaseProvider):
    """
    Anthropic Claude provider implementation with web search tool.

    Uses Claude's built-in web_search_20250305 tool powered by Brave Search.
    """

    SUPPORTED_MODELS = [
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-1-20250805",
    ]

    def __init__(self, api_key: str):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
        """
        super().__init__(api_key)
        self.client = Anthropic(api_key=api_key)

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "anthropic"

    def get_supported_models(self) -> List[str]:
        """Get list of supported Anthropic models."""
        return self.SUPPORTED_MODELS

    def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
        """
        Send prompt to Anthropic Claude with web search enabled.

        Args:
            prompt: User's prompt
            model: Model to use

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
            # Call Anthropic API with web search tool
            response = self.client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5
                }]
            )

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Parse the response
            return self._parse_response(response, model, response_time_ms)

        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
        """
        Parse Anthropic response into standardized format.

        Args:
            response: Raw Anthropic API response
            model: Model used
            response_time_ms: Response time in milliseconds

        Returns:
            ProviderResponse object
        """
        response_text = ""
        search_queries = []
        sources = []
        citations = []

        # Extract content blocks
        if hasattr(response, 'content') and response.content:
            for content_block in response.content:
                # Extract text responses
                if content_block.type == "text":
                    response_text += content_block.text

                    # Extract citations from text blocks
                    if hasattr(content_block, 'citations') and content_block.citations:
                        for citation in content_block.citations:
                            # Only include citations with valid URLs
                            if hasattr(citation, 'url') and citation.url:
                                citations.append(Citation(
                                    url=citation.url,
                                    title=citation.title if hasattr(citation, 'title') else None,
                                ))

                # Extract search queries from server_tool_use blocks
                elif content_block.type == "server_tool_use":
                    if hasattr(content_block, 'name') and content_block.name == "web_search":
                        if hasattr(content_block, 'input'):
                            # input is a dict, not an object
                            query = content_block.input.get('query') if isinstance(content_block.input, dict) else None
                            if query:
                                search_queries.append(SearchQuery(query=query))

                # Extract sources from web_search_tool_result blocks
                elif content_block.type == "web_search_tool_result":
                    if hasattr(content_block, 'content') and content_block.content:
                        for result in content_block.content:
                            # Only include sources with valid URLs
                            if hasattr(result, 'url') and result.url:
                                sources.append(Source(
                                    url=result.url,
                                    title=result.title if hasattr(result, 'title') else None,
                                    domain=urlparse(result.url).netloc
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
