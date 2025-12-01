"""
Google Gemini provider implementation with Search Grounding.
"""

import time
import requests
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

  def _resolve_redirect_url(self, redirect_url: str) -> str:
    """
    Resolve Google's grounding API redirect URL to get the actual destination.

    Args:
      redirect_url: Google's redirect URL

    Returns:
      The actual destination URL, or the original URL if resolution fails
    """
    # Check if this is a Google redirect URL
    if 'vertexaisearch.cloud.google.com/grounding-api-redirect' not in redirect_url:
      return redirect_url

    try:
      # Follow redirects with a short timeout
      response = requests.head(redirect_url, allow_redirects=True, timeout=3)
      return response.url
    except Exception:
      # If redirect resolution fails, return the original URL
      return redirect_url

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

          # First, collect all query strings
          query_strings = []
          if hasattr(metadata, 'web_search_queries') and metadata.web_search_queries:
            query_strings = list(metadata.web_search_queries)

          # Then collect all sources
          all_sources = []
          if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
            rank = 1
            for chunk in metadata.grounding_chunks:
              if hasattr(chunk, 'web') and chunk.web:
                # Only include sources with valid URIs
                if hasattr(chunk.web, 'uri') and chunk.web.uri:
                  # Resolve redirect URL to get actual destination
                  actual_url = self._resolve_redirect_url(chunk.web.uri)
                  source_obj = Source(
                    url=actual_url,
                    title=chunk.web.title if hasattr(chunk.web, 'title') else None,
                    domain=urlparse(actual_url).netloc,
                    rank=rank
                  )
                  all_sources.append(source_obj)
                  sources.append(source_obj)
                  rank += 1

          # Link sources to queries
          # Google doesn't provide explicit links, so we'll distribute sources across queries
          if query_strings:
            sources_per_query = len(all_sources) // len(query_strings)
            remainder = len(all_sources) % len(query_strings)

            start_idx = 0
            for i, query_str in enumerate(query_strings):
              # Calculate how many sources this query gets
              count = sources_per_query + (1 if i < remainder else 0)
              end_idx = start_idx + count

              # Assign sources to this query
              query_sources = all_sources[start_idx:end_idx]
              search_queries.append(SearchQuery(
                query=query_str,
                sources=query_sources
              ))
              start_idx = end_idx
          elif all_sources:
            # If we have sources but no queries, create a generic query
            search_queries.append(SearchQuery(
              query="Search",
              sources=all_sources
            ))

          # Note: Google's grounding_supports includes ALL sources, not just citations
          # We cannot reliably distinguish between sources that are merely fetched
          # vs. those that are explicitly cited in the response text.
          # Therefore, we leave citations empty for Google to maintain accuracy.

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
