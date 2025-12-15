"""Anthropic Claude provider implementation with web search."""

import logging
import os
import time
from typing import List, Union
from urllib.parse import urlparse

import httpx
from anthropic import Anthropic

from app.core.provider_schemas import validate_anthropic_raw_response

from .base_provider import BaseProvider, Citation, ProviderResponse, SearchQuery, Source

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
  """Anthropic Claude provider implementation with web search tool.

  Uses Claude's built-in web_search_20250305 tool powered by Brave Search.
  """

  SUPPORTED_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-1-20250805",
  ]

  def __init__(self, api_key: str):
    """Initialize Anthropic provider.

    Args:
      api_key: Anthropic API key
    """
    super().__init__(api_key)
    verify: Union[bool, str] = True
    if os.getenv("LLM_INSECURE_SKIP_VERIFY", "").lower() in {"1", "true", "yes"}:
      verify = False
    else:
      verify = (
        os.getenv("REQUESTS_CA_BUNDLE")
        or os.getenv("SSL_CERT_FILE")
        or True
      )

    http_client = httpx.Client(verify=verify, timeout=60)
    self.client = Anthropic(api_key=api_key, http_client=http_client)

  def get_provider_name(self) -> str:
    """Get provider name."""
    return "anthropic"

  def get_supported_models(self) -> List[str]:
    """Get list of supported Anthropic models."""
    return self.SUPPORTED_MODELS

  def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
    """Send prompt to Anthropic Claude with web search enabled.

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
        }]  # type: ignore[typeddict-item,typeddict-unknown-key]
      )

      # Calculate response time
      response_time_ms = int((time.time() - start_time) * 1000)

      # Parse the response
      return self._parse_response(response, model, response_time_ms)

    except ValueError:
      raise
    except Exception as e:
      raise Exception(f"Anthropic API error: {str(e)}")

  def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
    """Parse Anthropic response into standardized format.

    Args:
      response: Raw Anthropic API response
      model: Model used
      response_time_ms: Response time in milliseconds

    Returns:
      ProviderResponse object
    """
    response_text = ""
    search_queries = []
    sources: List[Source] = []
    citations = []

    # Temporary storage to link queries with their results
    # Anthropic returns blocks in order: query1, result1, query2, result2, etc.
    pending_queries = []
    result_index = 0

    # Extract content blocks
    if hasattr(response, 'content') and response.content:
      current_length = 0
      for content_block in response.content:
        # Extract text responses
        if content_block.type == "text":
          block_text = content_block.text or ""
          block_start = current_length
          response_text += block_text
          current_length += len(block_text)

          # Extract citations from text blocks
          if hasattr(content_block, 'citations') and content_block.citations:
            for citation in content_block.citations:
              # Handle both dict and object formats
              url = citation.get('url') if isinstance(citation, dict) else getattr(citation, 'url', None)
              if url:
                # Try to find rank from sources list by matching URL
                rank = None
                for source in sources:
                  if source.url == url:
                    rank = source.rank
                    break

                title = citation.get('title') if isinstance(citation, dict) else getattr(citation, 'title', None)
                if isinstance(citation, dict):
                  snippet = citation.get('cited_text') or citation.get('text')
                else:
                  snippet = getattr(citation, 'cited_text', None) or getattr(citation, 'text', None)
                start_index = None
                end_index = None
                if snippet:
                  local_idx = block_text.find(snippet)
                  if local_idx != -1:
                    start_index = block_start + local_idx
                    end_index = start_index + len(snippet)
                citations.append(Citation(
                  url=url,
                  title=title,
                  rank=rank,
                  text_snippet=snippet,
                  snippet_cited=snippet,
                  start_index=start_index,
                  end_index=end_index,
                ))

        # Extract search queries from server_tool_use blocks
        elif content_block.type == "server_tool_use":
          if hasattr(content_block, 'name') and content_block.name == "web_search":
            if hasattr(content_block, 'input'):
              # input is a dict, not an object
              query = content_block.input.get('query') if isinstance(content_block.input, dict) else None
              if query:
                # Create query and add to pending list
                search_query = SearchQuery(query=query, sources=[])
                pending_queries.append(search_query)
                search_queries.append(search_query)

        # Extract sources from web_search_tool_result blocks
        elif content_block.type == "web_search_tool_result":
          if hasattr(content_block, 'content') and content_block.content:
            result_sources = []
            for rank, result in enumerate(content_block.content, 1):
              # Only include sources with valid URLs
              # Handle both dict and object formats
              url = result.get('url') if isinstance(result, dict) else getattr(result, 'url', None)
              if url:
                title = result.get('title') if isinstance(result, dict) else getattr(result, 'title', None)
                source_obj = Source(
                  url=url,
                  title=title,
                  domain=urlparse(url).netloc,
                  rank=rank
                )
                result_sources.append(source_obj)
                sources.append(source_obj)

            # Link these sources to the corresponding query
            if result_index < len(pending_queries):
              pending_queries[result_index].sources = result_sources
              result_index += 1

    # Remove duplicate citations
    seen_urls = set()
    unique_citations = []
    for citation in citations:
      if citation.url not in seen_urls:
        seen_urls.add(citation.url)
        unique_citations.append(citation)

    try:
      raw_payload = validate_anthropic_raw_response(response)
    except ValueError as exc:
      raise ValueError(f"Anthropic raw payload validation failed: {exc}") from exc

    return ProviderResponse(
      response_text=response_text,
      search_queries=search_queries,
      sources=sources,
      citations=unique_citations,
      raw_response=raw_payload,
      model=model,
      provider=self.get_provider_name(),
      response_time_ms=response_time_ms
    )
