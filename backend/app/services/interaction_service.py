"""Service layer for interaction business logic."""

from typing import List, Optional
from datetime import datetime

from app.repositories.interaction_repository import InteractionRepository
from app.core.utils import normalize_model_name, extract_domain, calculate_average_rank
from app.api.v1.schemas.responses import (
  SendPromptResponse,
  InteractionSummary,
  SearchQuery as SearchQuerySchema,
  Source as SourceSchema,
  Citation as CitationSchema,
)


class InteractionService:
  """Service for managing interactions with business logic."""

  def __init__(self, repository: InteractionRepository):
    """
    Initialize service with repository.

    Args:
      repository: InteractionRepository instance
    """
    self.repository = repository

  def save_interaction(
    self,
    prompt: str,
    provider: str,
    model: str,
    response_text: str,
    response_time_ms: int,
    search_queries: List[dict],
    citations: List[dict],
    raw_response: dict,
    data_source: str = "api",
    extra_links_count: int = 0,
  ) -> int:
    """
    Save interaction with business logic applied.

    Applies:
    - Model name normalization
    - Domain extraction from URLs
    - Citation classification

    Args:
      prompt: The prompt text
      provider: Provider name
      model: Model name (will be normalized)
      response_text: The response text
      response_time_ms: Response time in milliseconds
      search_queries: List of search query dicts
      citations: List of citation dicts
      raw_response: Raw API response
      data_source: Data collection mode
      extra_links_count: Number of extra links

    Returns:
      The response ID
    """
    # Normalize model name (e.g., gpt-5-1 → gpt-5.1)
    normalized_model = normalize_model_name(model)

    # Extract domains from search query sources
    for query in search_queries:
      for source in query.get("sources", []):
        if "url" in source and not source.get("domain"):
          source["domain"] = extract_domain(source["url"])

    # Extract domains from citations
    for citation in citations:
      if "url" in citation and not citation.get("domain"):
        citation["domain"] = extract_domain(citation["url"])

    # Save to database
    return self.repository.save(
      prompt_text=prompt,
      provider_name=provider,
      model_name=normalized_model,
      response_text=response_text,
      response_time_ms=response_time_ms,
      search_queries=search_queries,
      sources_used=citations,
      raw_response=raw_response,
      data_source=data_source,
      extra_links_count=extra_links_count,
    )

  def get_recent_interactions(
    self,
    limit: int = 50,
    data_source: Optional[str] = None
  ) -> List[InteractionSummary]:
    """
    Get recent interactions with citation classification.

    Classifies citations into:
    - Sources Used: Citations that came from search results
    - Extra Links: Citations not from search results

    Args:
      limit: Maximum number of results
      data_source: Filter by data source

    Returns:
      List of InteractionSummary objects
    """
    responses = self.repository.get_recent(limit=limit, data_source=data_source)

    summaries = []
    for response in responses:
      # Calculate counts
      search_query_count = len(response.search_queries)
      # For network_log: sources are linked directly to response
      # For api: sources are linked to search queries
      if response.data_source == 'network_log':
        source_count = len(response.sources) if response.sources else 0
      else:
        source_count = sum(len(q.sources) for q in response.search_queries)
      citation_count = len(response.sources_used)

      # Calculate average rank
      average_rank = calculate_average_rank(response.sources_used)

      # Create preview (first 200 chars)
      response_preview = (
        response.response_text[:200]
        if response.response_text
        else ""
      )

      summary = InteractionSummary(
        interaction_id=response.id,
        prompt=response.prompt.prompt_text if response.prompt else "",
        provider=response.prompt.session.provider.name if response.prompt and response.prompt.session else "",
        model=response.prompt.session.model_used if response.prompt and response.prompt.session else "",
        response_preview=response_preview,
        search_query_count=search_query_count,
        source_count=source_count,
        citation_count=citation_count,
        average_rank=average_rank,
        extra_links_count=response.extra_links_count or 0,
        response_time_ms=response.response_time_ms,
        data_source=response.data_source,
        created_at=response.created_at,
      )
      summaries.append(summary)

    return summaries

  def get_interaction_details(self, interaction_id: int) -> Optional[SendPromptResponse]:
    """
    Get full interaction details with average rank calculation.

    Args:
      interaction_id: The interaction (response) ID

    Returns:
      SendPromptResponse with full details, or None if not found
    """
    response = self.repository.get_by_id(interaction_id)
    if not response:
      return None

    # Convert search queries to schemas
    search_queries = []
    for query in response.search_queries:
      sources = [
        SourceSchema(
          url=s.url,
          title=s.title,
          domain=s.domain,
          rank=s.rank,
          pub_date=s.pub_date,
          snippet_text=s.snippet_text,
          internal_score=s.internal_score,
          metadata=s.metadata_json,
        )
        for s in (query.sources or [])
      ]

      search_queries.append(
        SearchQuerySchema(
          query=query.search_query,
          sources=sources,
          timestamp=query.created_at.isoformat() if query.created_at else None,
          order_index=query.order_index,
          internal_ranking_scores=query.internal_ranking_scores,
          query_reformulations=query.query_reformulations,
        )
      )

    # Convert citations to schemas
    citations = [
      CitationSchema(
        url=c.url,
        title=c.title,
        rank=c.rank,
        snippet_used=c.snippet_used,
        citation_confidence=c.citation_confidence,
        metadata=c.metadata_json,
      )
      for c in response.sources_used
    ]

    # For network_log mode, convert direct sources to schemas
    all_sources = None
    if response.data_source == 'network_log' and response.sources:
      all_sources = [
        SourceSchema(
          url=s.url,
          title=s.title,
          domain=s.domain,
          rank=s.rank,
          pub_date=s.pub_date,
          snippet_text=s.snippet_text,
          internal_score=s.internal_score,
          metadata=s.metadata_json,
        )
        for s in (response.sources or [])
      ]

    # Calculate average rank
    average_rank = calculate_average_rank(response.sources_used)

    return SendPromptResponse(
      prompt=response.prompt.prompt_text if response.prompt else "",
      response_text=response.response_text,
      search_queries=search_queries,
      citations=citations,
      all_sources=all_sources,
      provider=response.prompt.session.provider.name if response.prompt and response.prompt.session else "",
      model=response.prompt.session.model_used if response.prompt and response.prompt.session else "",
      response_time_ms=response.response_time_ms,
      data_source=response.data_source,
      extra_links_count=response.extra_links_count,
      interaction_id=response.id,
      created_at=response.created_at,
      raw_response=response.raw_response_json,
      metadata={"average_rank": average_rank} if average_rank else None,
    )

  def delete_interaction(self, interaction_id: int) -> bool:
    """
    Delete an interaction.

    Args:
      interaction_id: The interaction (response) ID to delete

    Returns:
      True if deleted, False if not found
    """
    return self.repository.delete(interaction_id)
