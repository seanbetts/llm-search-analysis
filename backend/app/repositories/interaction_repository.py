"""Repository for database operations on interactions (prompts + responses)."""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, defer, joinedload

from app.models.database import (
  InteractionModel,
  Provider,
  QuerySource,
  Response,
  ResponseSource,
  SearchQuery,
  SourceUsed,
)

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
  """Normalize URL for matching by removing query params and trailing slash."""
  if not isinstance(url, str):
    return ""
  base_url = url.split('?')[0]
  base_url = base_url.rstrip('/')
  return base_url


def _parse_footnote_definitions(text: str) -> dict:
  """Parse footnote definitions from response text.

  Format: `[N]: URL "Title"`.
  Returns: dict mapping citation_number -> {url, title}.
  """
  footnote_pattern = r'\[(\d+)\]:\s+(https?://[^\s]+)(?:\s+"([^"]+)")?'
  footnotes = {}
  for match in re.finditer(footnote_pattern, text):
    citation_num = int(match.group(1))
    url = match.group(2)
    title = match.group(3) if match.group(3) else None
    footnotes[citation_num] = {'url': url, 'title': title}
  return footnotes


def _extract_snippet_before_citation(text: str, citation_match) -> Optional[str]:
  """Extract the text snippet before a citation marker."""
  position = citation_match.start()

  # Get text before citation (up to 300 chars back)
  start = max(0, position - 300)
  context = text[start:position]

  # Find boundaries (paragraphs, bullets, sentences)
  boundaries = []

  if '\n\n' in context:
    boundaries.append(('para', context.rfind('\n\n')))
  if '\n* ' in context:
    boundaries.append(('bullet', context.rfind('\n* ')))
  if '\n🔹 ' in context:
    boundaries.append(('bullet', context.rfind('\n🔹 ')))
  if '\n✅ ' in context:
    boundaries.append(('bullet', context.rfind('\n✅ ')))
  if '\n❌ ' in context:
    boundaries.append(('bullet', context.rfind('\n❌ ')))
  if '\n⚠️ ' in context:
    boundaries.append(('bullet', context.rfind('\n⚠️ ')))

  sentence_boundary = context.rfind('. ')
  if sentence_boundary != -1 and sentence_boundary < len(context) - 20:
    boundaries.append(('sentence', sentence_boundary))

  if boundaries:
    boundaries.sort(key=lambda x: x[1])
    boundary_type, boundary_pos = boundaries[-1]
    context = context[boundary_pos:]

  # Clean up
  context = context.strip()
  context = re.sub(r'^[*•🔹✅❌⚠️\n\s-]+', '', context)
  context = re.sub(r'\*\*', '', context)
  context = re.sub(r'\*', '', context)
  context = re.sub(r':\s*$', '', context).strip()
  context = re.sub(r'^\.\s*', '', context).strip()

  return context if len(context) > 10 else None


def _extract_snippets_from_citations(text: str) -> dict:
  """Extract all snippets for each citation number from inline citations.

  Returns: dict mapping citation_number -> list of snippet texts.
  """
  # Find footnote start to avoid matching them
  footnote_start = text.find('\n[1]: https://')
  inline_text = text[:footnote_start] if footnote_start != -1 else text

  # Find all inline citations with pattern ([Source Name][N])
  all_citations = list(re.finditer(r'\(\[([^\]]+)\]\[(\d+)\]\)', inline_text))

  snippets_by_number = defaultdict(list)

  for match in all_citations:
    citation_num = int(match.group(2))
    snippet = _extract_snippet_before_citation(text, match)

    if snippet:
      snippets_by_number[citation_num].append(snippet)

  return dict(snippets_by_number)


# Provider display name mapping
PROVIDER_DISPLAY_NAMES = {
  'openai': 'OpenAI',
  'google': 'Google',
  'anthropic': 'Anthropic',
  'chatgpt_network': 'ChatGPT (Web)',
}


class InteractionRepository:
  """Repository for managing interactions (prompts + responses)."""

  def __init__(self, db: Session):
    """Initialize repository with database session.

    Args:
      db: SQLAlchemy database session
    """
    self.db = db

  def save(
    self,
    prompt_text: str,
    provider_name: str,
    model_name: str,
    response_text: str,
    response_time_ms: int,
    search_queries: List[dict],
    sources_used: List[dict],
    raw_response: dict,
    data_source: str = "api",
    extra_links_count: int = 0,
    sources: Optional[List[dict]] = None,
    sources_found: int = 0,
    sources_used_count: int = 0,
    avg_rank: Optional[float] = None,
    citation_tagging_requested: Optional[bool] = None,
  ) -> int:
    """Save a complete interaction (prompt + response + search data).

    Args:
      prompt_text: The prompt text
      provider_name: Provider name (e.g., "openai")
      model_name: Model name (e.g., "gpt-4o")
      response_text: The response text
      response_time_ms: Response time in milliseconds
      search_queries: List of search query dicts with sources
      sources_used: List of citation dicts
      raw_response: Raw API response as dict
      data_source: Data collection mode ("api" or "web")
      extra_links_count: Number of extra links not from search
      sources: List of source dicts linked directly to response (for web capture mode)
      sources_found: Total number of sources from search
      sources_used_count: Number of citations with rank (from search results)
      avg_rank: Average rank of citations
      citation_tagging_requested: Optional override for whether to queue tagging for this response

    Returns:
      The response ID

    Raises:
      SQLAlchemyError: If database operation fails
    """
    try:
      query_source_lookup: dict = {}
      response_source_lookup: dict = {}

      def register_source(lookup: dict, url: str, rank: Optional[int], source_id: int):
        """Register a source in the lookup dictionary for deduplication."""
        if not url:
          return
        normalized_url = url.strip()
        key_with_rank = (normalized_url, rank if rank is not None else None)
        lookup.setdefault(key_with_rank, []).append(source_id)
        fallback_key = (normalized_url, None)
        lookup.setdefault(fallback_key, []).append(source_id)

      def match_source(lookup: dict, url: Optional[str], rank: Optional[int]) -> Optional[int]:
        """Find matching source ID from lookup dictionary by URL and rank."""
        if not url:
          return None
        normalized_url = url.strip()
        keys: list[tuple[str, Optional[int]]] = []
        if rank is not None:
          keys.append((normalized_url, rank))
        keys.append((normalized_url, None))
        for key in keys:
          ids = lookup.get(key)
          if ids:
            return ids[0]
        return None

      # Get or create provider
      provider = self.db.query(Provider).filter_by(name=provider_name).first()
      if not provider:
        provider = Provider(
          name=provider_name,
          display_name=PROVIDER_DISPLAY_NAMES.get(provider_name, provider_name.title()),
          is_active=True
        )
        self.db.add(provider)
        self.db.flush()

      # Create interaction
      interaction = InteractionModel(
        provider_id=provider.id,
        model_name=model_name,
        prompt_text=prompt_text,
        data_source=data_source,
      )
      self.db.add(interaction)
      self.db.flush()

      raw_response_text = self._extract_full_text(raw_response)

      # Create response
      response = Response(
        interaction_id=interaction.id,
        response_text=response_text,
        response_time_ms=response_time_ms,
        raw_response_json=raw_response,
        data_source=data_source,
        extra_links_count=extra_links_count,
        sources_found=sources_found,
        sources_used_count=sources_used_count,
        avg_rank=avg_rank,
        citation_tagging_requested=(
          citation_tagging_requested
          if citation_tagging_requested is not None
          else True
        ),
      )
      self.db.add(response)
      self.db.flush()

      # Create search queries and sources
      for i, query_data in enumerate(search_queries):
        search_query = SearchQuery(
          response_id=response.id,
          search_query=query_data.get("query", ""),
          order_index=query_data.get("order_index", 0),
          internal_ranking_scores=query_data.get("internal_ranking_scores"),
          query_reformulations=query_data.get("query_reformulations"),
        )
        self.db.add(search_query)
        self.db.flush()

        # Create sources for this query
        for source_data in query_data.get("sources", []):
          source = QuerySource(
            search_query_id=search_query.id,
            url=source_data.get("url", ""),
            title=source_data.get("title"),
            domain=source_data.get("domain"),
            rank=source_data.get("rank"),
            pub_date=source_data.get("pub_date"),
            internal_score=source_data.get("internal_score"),
            metadata_json=source_data.get("metadata"),
          )
          self.db.add(source)
          self.db.flush()
          register_source(query_source_lookup, source.url or "", source.rank, source.id)

      # Create top-level sources (for web capture mode)
      if sources:
        for source_data in sources:
          response_source = ResponseSource(
            response_id=response.id,
            url=source_data.get("url", ""),
            title=source_data.get("title"),
            domain=source_data.get("domain"),
            rank=source_data.get("rank"),
            pub_date=source_data.get("pub_date"),
            search_description=(
              source_data.get("search_description")
              or source_data.get("snippet_text")
            ),
            internal_score=source_data.get("internal_score"),
            metadata_json=source_data.get("metadata"),
          )
          self.db.add(response_source)
          self.db.flush()
          register_source(
            response_source_lookup,
            response_source.url or "",
            response_source.rank,
            response_source.id,
          )

      def _clean_snippet(value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
          trimmed = value.strip()
          return trimmed or None
        return None

      def _slice_from_text(text: Optional[str], meta: dict) -> Optional[str]:
        start = meta.get("start_index")
        end = meta.get("end_index")
        if start is None and meta.get("segment_start_index") is not None:
          start = meta.get("segment_start_index")
        if end is None and meta.get("segment_end_index") is not None:
          end = meta.get("segment_end_index")
        if start is None and isinstance(end, int) and end >= 0:
          start = 0
        if (
          isinstance(start, int)
          and isinstance(end, int)
          and isinstance(text, str)
          and 0 <= start < end <= len(text)
        ):
          snippet = text[start:end].strip()
          return snippet or None
        return None

      def _snippet_from_indices(meta: dict) -> Optional[str]:
        texts = [response_text]
        if raw_response_text and raw_response_text != response_text:
          texts.append(raw_response_text)
        for candidate in texts:
          snippet = _slice_from_text(candidate, meta)
          if snippet:
            return snippet
        return None

      # Parse footnotes once for web/network_log responses
      footnote_mapping = {}
      snippet_mapping = {}

      if response.data_source in ("web", "network_log") and response_text:
        footnotes = _parse_footnote_definitions(response_text)
        if footnotes:
          snippets_by_number = _extract_snippets_from_citations(response_text)

          # Build URL -> citation_number mapping
          for citation_num, footnote_data in footnotes.items():
            url_norm = _normalize_url(footnote_data['url'])
            footnote_mapping[url_norm] = citation_num
            snippet_mapping[citation_num] = snippets_by_number.get(citation_num, [])

      # Create sources used (citations)
      for citation_data in sources_used:
        matched_query_source = match_source(
          query_source_lookup,
          citation_data.get("url"),
          citation_data.get("rank"),
        )
        matched_response_source = None
        if matched_query_source is None:
          matched_response_source = match_source(
            response_source_lookup,
            citation_data.get("url"),
            citation_data.get("rank"),
          )

        metadata = citation_data.get("metadata") or {}
        if citation_data.get("start_index") is not None:
          metadata.setdefault("start_index", citation_data.get("start_index"))
        if citation_data.get("end_index") is not None:
          metadata.setdefault("end_index", citation_data.get("end_index"))
        if citation_data.get("published_at"):
          metadata.setdefault("published_at", citation_data.get("published_at"))

        # For web/network_log, always extract from footnotes (don't use provided snippets)
        if response.data_source in ("web", "network_log"):
          snippet_value = None
          if footnote_mapping:
            url_norm = _normalize_url(citation_data.get("url", ""))

            if url_norm in footnote_mapping:
              citation_num = footnote_mapping[url_norm]
              metadata["citation_number"] = citation_num

              snippets = snippet_mapping.get(citation_num, [])
              if snippets:
                snippet_value = snippets[0]
        else:
          # For API mode: do not persist snippet_cited (indices can be provider-specific and may not align).
          snippet_value = None

        source_used = SourceUsed(
          response_id=response.id,
          query_source_id=matched_query_source,
          response_source_id=matched_response_source,
          url=citation_data.get("url", ""),
          title=citation_data.get("title"),
          rank=citation_data.get("rank"),
          snippet_cited=snippet_value,
          citation_confidence=citation_data.get("citation_confidence"),
          metadata_json=metadata,
          function_tags=citation_data.get("function_tags") or [],
          stance_tags=citation_data.get("stance_tags") or [],
          provenance_tags=citation_data.get("provenance_tags") or [],
          influence_summary=citation_data.get("influence_summary"),
        )
        self.db.add(source_used)

      self.db.commit()
      return response.id

    except SQLAlchemyError:
      self.db.rollback()
      raise

  def get_by_id(self, response_id: int) -> Optional[Response]:
    """Get interaction by response ID with eager loading.

    Uses joinedload to prevent N+1 query problem.

    Args:
      response_id: The response ID

    Returns:
      Response object with relationships loaded, or None if not found
    """
    return (
      self.db.query(Response)
      .options(
        joinedload(Response.interaction)
        .joinedload(InteractionModel.provider),
        joinedload(Response.search_queries)
        .joinedload(SearchQuery.sources),
        joinedload(Response.sources_used),
        joinedload(Response.response_sources),
      )
      .filter_by(id=response_id)
      .first()
    )

  def get_recent(
    self,
    page: int = 1,
    page_size: int = 20,
    data_source: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
  ) -> Tuple[List[Response], int]:
    r"""Get recent interactions with pagination and filtering.

    Args:
      page: Page number (1-indexed)
      page_size: Number of items per page (max 100)
      data_source: Filter by data source ("api", "web"), or None for all. Legacy \"network_log\" values are accepted.
      provider: Filter by provider name (e.g., "openai"), or None for all
      model: Filter by model name (e.g., "gpt-4o"), or None for all
      date_from: Filter by created_at >= date_from, or None for no lower bound
      date_to: Filter by created_at <= date_to, or None for no upper bound

    Returns:
      Tuple of (List of Response objects with relationships loaded, total count)
    """
    # Build base query with eager loading
    query = (
      self.db.query(Response)
      .join(Response.interaction)
      .join(InteractionModel.provider)
      .options(
        defer(Response.raw_response_json),
        joinedload(Response.interaction)
        .joinedload(InteractionModel.provider),
        joinedload(Response.search_queries)
        .joinedload(SearchQuery.sources),
        joinedload(Response.sources_used),
        joinedload(Response.response_sources),
      )
    )

    # Apply filters
    if data_source:
      query = query.filter(Response.data_source == data_source)

    if provider:
      query = query.filter(Provider.name == provider)

    if model:
      query = query.filter(InteractionModel.model_name == model)

    if date_from:
      query = query.filter(Response.created_at >= date_from)

    if date_to:
      query = query.filter(Response.created_at <= date_to)

    # Get total count before pagination
    total_count = query.with_entities(func.count(Response.id)).scalar()

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    results = query.order_by(Response.created_at.desc()).offset(offset).limit(page_size).all()

    return results, total_count

  def delete(self, response_id: int) -> bool:
    """Delete an interaction (response + prompt + related records).

    Args:
      response_id: The response ID to delete

    Returns:
      True if deleted, False if not found

    Raises:
      SQLAlchemyError: If database operation fails
    """
    try:
      response = self.db.query(Response).filter_by(id=response_id).first()
      if not response:
        return False

      interaction = response.interaction
      provider = interaction.provider if interaction else None
      interaction_id = interaction.id if interaction else None
      provider_id = provider.id if provider else None

      # Delete sources used
      self.db.query(SourceUsed).filter_by(response_id=response_id).delete()

      # Delete sources and search queries
      queries = self.db.query(SearchQuery).filter_by(response_id=response_id).all()
      for query in queries:
        self.db.query(QuerySource).filter_by(search_query_id=query.id).delete()

      # Delete sources associated with response (network logs)
      self.db.query(ResponseSource).filter_by(response_id=response_id).delete()

      # Delete search queries
      self.db.query(SearchQuery).filter_by(response_id=response_id).delete()

      # Delete response
      self.db.delete(response)
      self.db.flush()

      # Delete interaction if no other responses remain
      if interaction_id:
        has_responses = self.db.query(Response.id).filter_by(interaction_id=interaction_id).first()
        if not has_responses:
          interaction_obj = self.db.query(InteractionModel).filter_by(id=interaction_id).first()
          if interaction_obj:
            self.db.delete(interaction_obj)
            self.db.flush()

      # Delete provider if no interactions remain
      if provider_id:
        has_interactions = self.db.query(InteractionModel.id).filter_by(provider_id=provider_id).first()
        if not has_interactions:
          provider_obj = self.db.query(Provider).filter_by(id=provider_id).first()
          if provider_obj:
            self.db.delete(provider_obj)

      self.db.commit()
      return True

    except SQLAlchemyError:
      self.db.rollback()
      raise

  def get_history_stats(self) -> dict:
    """Compute aggregate metrics for the entire query history dataset.

    Returns:
      Dict containing total analyses and averaged metrics.
    """
    total_analyses = self.db.query(func.count(Response.id)).scalar() or 0
    if total_analyses == 0:
      return {
        "analyses": 0,
        "avg_response_time_ms": None,
        "avg_searches": None,
        "avg_sources_found": None,
        "avg_sources_used": None,
        "avg_rank": None,
      }

    search_counts_subquery = (
      self.db.query(
        SearchQuery.response_id.label("response_id"),
        func.count(SearchQuery.id).label("count")
      )
      .group_by(SearchQuery.response_id)
      .subquery()
    )

    avg_searches = self.db.query(
      func.avg(func.coalesce(search_counts_subquery.c.count, 0))
    ).select_from(Response).outerjoin(
      search_counts_subquery,
      Response.id == search_counts_subquery.c.response_id
    ).scalar()

    avg_response_time = self.db.query(func.avg(Response.response_time_ms)).scalar()
    avg_sources_found = self.db.query(func.avg(func.coalesce(Response.sources_found, 0))).scalar()
    avg_sources_used = self.db.query(func.avg(func.coalesce(Response.sources_used_count, 0))).scalar()
    avg_rank = self.db.query(func.avg(Response.avg_rank)).scalar()

    def _as_float(value):
      return float(value) if value is not None else None

    return {
      "analyses": int(total_analyses),
      "avg_response_time_ms": _as_float(avg_response_time),
      "avg_searches": _as_float(avg_searches),
      "avg_sources_found": _as_float(avg_sources_found),
      "avg_sources_used": _as_float(avg_sources_used),
      "avg_rank": _as_float(avg_rank),
    }

  def _extract_full_text(self, raw_response: Any) -> Optional[str]:
    """Attempt to reconstruct full response text from provider payload."""
    payload = raw_response
    if payload is None:
      return None
    if isinstance(payload, (bytes, bytearray)):
      payload = payload.decode("utf-8", errors="ignore")
    if isinstance(payload, str):
      try:
        payload = json.loads(payload)
      except json.JSONDecodeError:
        return payload

    if not isinstance(payload, dict):
      return None

    output = payload.get("output")
    if isinstance(output, list):
      chunks: List[str] = []
      for item in output:
        if not isinstance(item, dict):
          continue
        if item.get("type") == "message":
          for content in item.get("content") or []:
            text = content.get("text")
            if text:
              chunks.append(text)
      if chunks:
        return "".join(chunks)

    candidates = payload.get("candidates")
    if isinstance(candidates, list):
      chunks = []
      for candidate in candidates:
        if not isinstance(candidate, dict):
          continue
        content_obj = candidate.get("content")
        if isinstance(content_obj, str):
          if content_obj:
            chunks.append(content_obj)
          continue
        contents = content_obj if isinstance(content_obj, list) else [content_obj]
        for content in contents:
          if not isinstance(content, dict):
            continue
          parts = content.get("parts") or []
          for part in parts:
            if not isinstance(part, dict):
              continue
            text = part.get("text")
            if text:
              chunks.append(text)
      if chunks:
        return "".join(chunks)

    content_list = payload.get("content")
    if isinstance(content_list, list):
      chunks = []
      for block in content_list:
        if not isinstance(block, dict):
          continue
        text = block.get("text")
        if text:
          chunks.append(text)
      if chunks:
        return "".join(chunks)

    return None
