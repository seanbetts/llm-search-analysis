"""OpenAI provider implementation using the Responses API with web_search tool."""

import time
from typing import List
from urllib.parse import urlparse

from openai import OpenAI

from app.core.provider_schemas import validate_openai_raw_response

from .base_provider import BaseProvider, Citation, ProviderResponse, SearchQuery, Source


class OpenAIProvider(BaseProvider):
  """OpenAI provider implementation."""

  SUPPORTED_MODELS = [
    "gpt-5.1",
    "gpt-5-mini",
    "gpt-5-nano",
  ]

  def __init__(self, api_key: str):
    """Initialize OpenAI provider.

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
    """Send prompt to OpenAI with web_search enabled.

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

    except ValueError:
      # Bubble up validation errors (e.g., malformed raw payloads)
      raise
    except Exception as e:
      raise Exception(f"OpenAI API error: {str(e)}")

  def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
    """Parse OpenAI Responses API response into standardized format.

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

            # Extract search query with its sources
            if hasattr(action, 'query') and action.query:
              query_sources = []

              # Extract sources for this query (requires include=["web_search_call.action.sources"])
              if hasattr(action, 'sources') and action.sources:
                for rank, source in enumerate(action.sources, 1):
                  # Only include sources that have a valid URL
                  if hasattr(source, 'url') and source.url:
                    snippet = getattr(source, 'snippet', None)
                    published_at = getattr(source, 'published_at', None)
                    source_obj = Source(
                      url=source.url,
                      title=source.title if hasattr(source, 'title') else None,
                      domain=urlparse(source.url).netloc,
                      rank=rank,
                      pub_date=published_at,
                      snippet_text=snippet,
                      metadata={"published_at": published_at} if published_at else None,
                    )
                    query_sources.append(source_obj)
                    sources.append(source_obj)

              # Create SearchQuery with its sources
              search_queries.append(SearchQuery(
                query=action.query,
                sources=query_sources
              ))

        # Handle message type
        elif output_item.type == "message":
          if output_item.status == "completed" and hasattr(output_item, 'content'):
            for content_item in output_item.content:
              if content_item.type == "output_text":
                response_text += content_item.text or ""

                # Extract citations from annotations
                if hasattr(content_item, 'annotations') and content_item.annotations:
                  for annotation in content_item.annotations:
                    if annotation.type == "url_citation":
                      # Only include citations with valid URLs
                      if hasattr(annotation, 'url') and annotation.url:
                        # Normalize URLs by removing query params for matching
                        citation_url_base = annotation.url.split('?')[0]

                        # Try to find rank from sources list
                        rank = None
                        for source in sources:
                          source_url_base = source.url.split('?')[0]
                          if source_url_base == citation_url_base:
                            rank = source.rank
                            break

                        citations.append(Citation(
                          url=annotation.url,
                          title=annotation.title if hasattr(annotation, 'title') else None,
                          rank=rank,
                          text_snippet=getattr(annotation, 'text', None),
                          snippet_used=getattr(annotation, 'text', None),
                          start_index=getattr(annotation, 'start_index', None),
                          end_index=getattr(annotation, 'end_index', None),
                        ))

    # Remove duplicate citations
    seen_urls = set()
    unique_citations = []
    for citation in citations:
      if citation.url not in seen_urls:
        seen_urls.add(citation.url)
        unique_citations.append(citation)

    try:
      raw_payload = validate_openai_raw_response(response)
    except ValueError as exc:
      raise ValueError(f"OpenAI raw payload validation failed: {exc}") from exc

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
