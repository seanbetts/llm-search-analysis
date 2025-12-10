"""
Repository for database operations on interactions (prompts + responses).
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

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

# Provider display name mapping
PROVIDER_DISPLAY_NAMES = {
  'openai': 'OpenAI',
  'google': 'Google',
  'anthropic': 'Anthropic',
  'chatgpt_network': 'ChatGPT (Network Log)',
}


class InteractionRepository:
  """Repository for managing interactions (prompts + responses)."""

  def __init__(self, db: Session):
    """
    Initialize repository with database session.

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
    sources: List[dict] = None,
    sources_found: int = 0,
    sources_used_count: int = 0,
    avg_rank: Optional[float] = None,
  ) -> int:
    """
    Save a complete interaction (prompt + response + search data).

    Args:
      prompt_text: The prompt text
      provider_name: Provider name (e.g., "openai")
      model_name: Model name (e.g., "gpt-4o")
      response_text: The response text
      response_time_ms: Response time in milliseconds
      search_queries: List of search query dicts with sources
      sources_used: List of citation dicts
      raw_response: Raw API response as dict
      data_source: Data collection mode ("api" or "network_log")
      extra_links_count: Number of extra links not from search
      sources: List of source dicts linked directly to response (for network_log mode)
      sources_found: Total number of sources from search
      sources_used_count: Number of citations with rank (from search results)
      avg_rank: Average rank of citations

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
        keys = []
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
        avg_rank=avg_rank
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
            snippet_text=source_data.get("snippet_text"),
            internal_score=source_data.get("internal_score"),
            metadata_json=source_data.get("metadata"),
          )
          self.db.add(source)
          self.db.flush()
          register_source(query_source_lookup, source.url or "", source.rank, source.id)

      # Create top-level sources (for network_log mode)
      if sources:
        for source_data in sources:
          source = ResponseSource(
            response_id=response.id,
            url=source_data.get("url", ""),
            title=source_data.get("title"),
            domain=source_data.get("domain"),
            rank=source_data.get("rank"),
            pub_date=source_data.get("pub_date"),
            snippet_text=source_data.get("snippet_text"),
            internal_score=source_data.get("internal_score"),
            metadata_json=source_data.get("metadata"),
          )
          self.db.add(source)
          self.db.flush()
          register_source(response_source_lookup, source.url or "", source.rank, source.id)

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

        source_used = SourceUsed(
          response_id=response.id,
          query_source_id=matched_query_source,
          response_source_id=matched_response_source,
          url=citation_data.get("url", ""),
          title=citation_data.get("title"),
          rank=citation_data.get("rank"),
          snippet_used=citation_data.get("snippet_used"),
          citation_confidence=citation_data.get("citation_confidence"),
          metadata_json=citation_data.get("metadata"),
        )
        self.db.add(source_used)

      self.db.commit()
      return response.id

    except SQLAlchemyError:
      self.db.rollback()
      raise

  def get_by_id(self, response_id: int) -> Optional[Response]:
    """
    Get interaction by response ID with eager loading.

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
    """
    Get recent interactions with pagination and filtering.

    Args:
      page: Page number (1-indexed)
      page_size: Number of items per page (max 100)
      data_source: Filter by data source ("api", "network_log"), or None for all
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
    """
    Delete an interaction (response + prompt + related records).

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
    """
    Compute aggregate metrics for the entire query history dataset.

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
