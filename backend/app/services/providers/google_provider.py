"""Google Gemini provider implementation with Search Grounding."""

import time
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests
from google.genai import Client
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

from app.core.provider_schemas import validate_google_raw_response

from .base_provider import BaseProvider, Citation, ProviderResponse, SearchQuery, Source


class GoogleProvider(BaseProvider):
  """Google Gemini provider implementation."""

  SUPPORTED_MODELS = [
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
  ]

  def __init__(self, api_key: str):
    """Initialize Google provider.

    Args:
      api_key: Google AI API key
    """
    super().__init__(api_key)
    self.client = Client(api_key=api_key)

  def get_provider_name(self) -> str:
    """Get provider name."""
    return "google"

  def _resolve_redirect_url(self, redirect_url: str) -> str:
    """Resolve Google's grounding API redirect URL to get the actual destination.

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
    """Send prompt to Google Gemini with search grounding.

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

    except ValueError:
      raise
    except Exception as e:
      raise Exception(f"Google API error: {str(e)}")

  def _parse_response(self, response, model: str, response_time_ms: int) -> ProviderResponse:
    """Parse Google response into standardized format.

    Args:
      response: Raw Google API response
      model: Model used
      response_time_ms: Response time in milliseconds

    Returns:
      ProviderResponse object
    """
    search_queries: List[SearchQuery] = []
    sources: List[Source] = []
    citations: List[Citation] = []
    response_text = response.text or ""

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
          chunk_index_to_source = {}
          if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
            rank = 1
            for chunk_idx, chunk in enumerate(metadata.grounding_chunks):
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
                  chunk_index_to_source[chunk_idx] = source_obj
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

          # Build citations using grounding_supports metadata when available
          supports_attr = getattr(metadata, 'grounding_supports', None)
          if isinstance(supports_attr, (list, tuple)):
            for support in supports_attr:
              chunk_indices = getattr(support, 'grounding_chunk_indices', None) or []
              segment = getattr(support, 'segment', None)
              segment_text = getattr(segment, 'text', None) if segment else None

              for chunk_idx in chunk_indices:
                source_obj = chunk_index_to_source.get(chunk_idx)
                if not source_obj:
                  continue

                start_index, end_index, snippet = self._extract_segment_span(
                  response_text,
                  segment_text,
                  getattr(segment, "start_index", None),
                  getattr(segment, "end_index", None),
                )

                citations.append(Citation(
                  url=source_obj.url,
                  title=source_obj.title,
                  rank=source_obj.rank,
                  text_snippet=snippet,
                  snippet_cited=snippet,
                  start_index=start_index,
                  end_index=end_index,
                  metadata={
                    "grounding_chunk_index": chunk_idx,
                    "segment_start_index": getattr(segment, "start_index", None),
                    "segment_end_index": getattr(segment, "end_index", None),
                    "confidence_scores": getattr(support, "confidence_scores", None),
                  }
                ))
                # Only need one citation per support to represent the reference
                break

    # Remove duplicate citations
    seen_urls = set()
    unique_citations = []
    for citation in citations:
      if citation.url not in seen_urls:
        seen_urls.add(citation.url)
        unique_citations.append(citation)

    try:
      raw_payload = validate_google_raw_response(response)
    except ValueError as exc:
      raise ValueError(f"Google raw payload validation failed: {exc}") from exc

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

  @staticmethod
  def _extract_segment_span(
    text: str,
    segment_text: Optional[str],
    start_index: Optional[int],
    end_index: Optional[int],
  ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Normalize segment span indices and snippet text."""
    text_length = len(text or "")
    def _clamp_indices(start: int, end: int) -> Tuple[int, int]:
      start = GoogleProvider._trim_span_start(text, start, end)
      end = GoogleProvider._trim_span_end(text, start, end)
      return start, end

    if (
      isinstance(start_index, int) and isinstance(end_index, int)
      and 0 <= start_index < end_index <= text_length
    ):
      trimmed_start, trimmed_end = _clamp_indices(start_index, end_index)
      if trimmed_start >= trimmed_end:
        return None, None, GoogleProvider._clean_segment_text(segment_text)

      segment = text[trimmed_start:trimmed_end]

      # Avoid leaking into subsequent headings separated by a blank line
      double_newline = segment.find("\n\n")
      if double_newline != -1:
        trimmed_end = trimmed_start + double_newline
        trimmed_start, trimmed_end = _clamp_indices(trimmed_start, trimmed_end)
        segment = text[trimmed_start:trimmed_end]

      # If the span begins immediately after heading markers, skip the heading line
      prefix = text[max(0, trimmed_start - 4):trimmed_start]
      newline_offset = segment.find("\n")
      if "#" in prefix and newline_offset != -1:
        trimmed_start = trimmed_start + newline_offset + 1
        trimmed_start, trimmed_end = _clamp_indices(trimmed_start, trimmed_end)
        segment = text[trimmed_start:trimmed_end]

      if trimmed_start >= trimmed_end:
        return None, None, GoogleProvider._clean_segment_text(segment_text)

      snippet = segment.strip() or GoogleProvider._clean_segment_text(segment_text)
      return trimmed_start, trimmed_end, snippet

    return None, None, GoogleProvider._clean_segment_text(segment_text)

  @staticmethod
  def _trim_span_start(text: str, start: int, end: int) -> int:
    """Skip leading markdown/bullet characters."""
    trim_chars = set(" \n\r\t*-•#")
    while start < end and text[start] in trim_chars:
      start += 1
    return start

  @staticmethod
  def _trim_span_end(text: str, start: int, end: int) -> int:
    """Trim trailing markdown/whitespace from span."""
    trim_chars = set(" \n\r\t*#")
    while end > start and text[end - 1] in trim_chars:
      end -= 1
    return end

  @staticmethod
  def _clean_segment_text(segment_text: Optional[str]) -> Optional[str]:
    """Remove markdown bullet markers from segment text."""
    if not segment_text:
      return segment_text
    cleaned = segment_text.strip()
    cleaned = cleaned.lstrip("*-•# ").rstrip("*-•# ").strip()
    return cleaned or segment_text
