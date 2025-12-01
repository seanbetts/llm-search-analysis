"""
Repository for database operations on interactions (prompts + responses).
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.models.database import (
  Provider,
  SessionModel,
  Prompt,
  Response,
  SearchQuery,
  SourceModel,
  SourceUsed,
)


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

    Returns:
      The response ID

    Raises:
      SQLAlchemyError: If database operation fails
    """
    try:
      # Get or create provider
      provider = self.db.query(Provider).filter_by(name=provider_name).first()
      if not provider:
        provider = Provider(
          name=provider_name,
          display_name=provider_name.title(),
          is_active=True
        )
        self.db.add(provider)
        self.db.flush()

      # Create session
      session = SessionModel(
        provider_id=provider.id,
        model_used=model_name
      )
      self.db.add(session)
      self.db.flush()

      # Create prompt
      prompt = Prompt(
        session_id=session.id,
        prompt_text=prompt_text
      )
      self.db.add(prompt)
      self.db.flush()

      # Create response
      response = Response(
        prompt_id=prompt.id,
        response_text=response_text,
        response_time_ms=response_time_ms,
        raw_response_json=raw_response,
        data_source=data_source,
        extra_links_count=extra_links_count
      )
      self.db.add(response)
      self.db.flush()

      # Create search queries and sources
      for query_data in search_queries:
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
          source = SourceModel(
            search_query_id=search_query.id,
            response_id=response.id if source_data.get("response_id") else None,
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

      # Create sources used (citations)
      for citation_data in sources_used:
        source_used = SourceUsed(
          response_id=response.id,
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
        joinedload(Response.prompt)
        .joinedload(Prompt.session)
        .joinedload(SessionModel.provider),
        joinedload(Response.search_queries)
        .joinedload(SearchQuery.sources),
        joinedload(Response.sources_used),
        joinedload(Response.sources),  # Load direct sources for network_log mode
      )
      .filter_by(id=response_id)
      .first()
    )

  def get_recent(
    self,
    limit: int = 50,
    data_source: Optional[str] = None
  ) -> List[Response]:
    """
    Get recent interactions with eager loading.

    Args:
      limit: Maximum number of results
      data_source: Filter by data source ("api", "network_log"), or None for all

    Returns:
      List of Response objects with relationships loaded
    """
    query = (
      self.db.query(Response)
      .options(
        joinedload(Response.prompt)
        .joinedload(Prompt.session)
        .joinedload(SessionModel.provider),
        joinedload(Response.search_queries)
        .joinedload(SearchQuery.sources),
        joinedload(Response.sources_used),
        joinedload(Response.sources),  # Load direct sources for network_log mode
      )
      .order_by(Response.created_at.desc())
    )

    if data_source:
      query = query.filter(Response.data_source == data_source)

    return query.limit(limit).all()

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

      # Delete sources used
      self.db.query(SourceUsed).filter_by(response_id=response_id).delete()

      # Delete sources and search queries
      queries = self.db.query(SearchQuery).filter_by(response_id=response_id).all()
      for query in queries:
        self.db.query(SourceModel).filter_by(search_query_id=query.id).delete()

      # Delete sources associated with response (network logs)
      self.db.query(SourceModel).filter_by(response_id=response_id).delete()

      # Delete search queries
      self.db.query(SearchQuery).filter_by(response_id=response_id).delete()

      # Delete response
      prompt_id = response.prompt_id
      self.db.delete(response)

      # Delete prompt (orphan)
      if prompt_id:
        prompt = self.db.query(Prompt).filter_by(id=prompt_id).first()
        if prompt:
          self.db.delete(prompt)

      self.db.commit()
      return True

    except SQLAlchemyError:
      self.db.rollback()
      raise
