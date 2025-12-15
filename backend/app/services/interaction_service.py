"""Service layer for interaction business logic."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from pydantic import TypeAdapter, ValidationError

from app.api.v1.schemas.responses import (
  Citation as CitationSchema,
)
from app.api.v1.schemas.responses import (
  InteractionSummary,
  QueryHistoryStats,
  SendPromptResponse,
)
from app.api.v1.schemas.responses import (
  SearchQuery as SearchQuerySchema,
)
from app.api.v1.schemas.responses import (
  Source as SourceSchema,
)
from app.core.json_schemas import (
  CitationMetadata,
  SourceMetadata,
  dump_metadata,
)
from app.core.utils import (
  calculate_average_rank,
  extract_domain,
  get_model_display_name,
  normalize_model_name,
)
from app.repositories.interaction_repository import InteractionRepository
from app.services.citation_tagging_service import CitationTaggingService
from app.services.providers.base_provider import Citation as CitationModel
from app.services.response_formatter import format_response_with_citations


class InteractionService:
  """Service for managing interactions with business logic."""
  _json_dict_adapter = TypeAdapter(Dict[str, Any])
  _list_str_adapter = TypeAdapter(List[str])

  def __init__(
    self,
    repository: InteractionRepository,
    citation_tagger: Optional[CitationTaggingService] = None,
  ):
    """Initialize service with repository.

    Args:
      repository: InteractionRepository instance
      citation_tagger: Optional service for annotating citations
    """
    self.repository = repository
    self.citation_tagger = citation_tagger or CitationTaggingService.from_settings()

  def save_interaction(
    self,
    prompt: str,
    provider: str,
    model: str,
    response_text: str,
    response_time_ms: int,
    search_queries: List[dict],
    citations: List[dict],
    raw_response: Optional[dict],
    data_source: str = "api",
    extra_links_count: int = 0,
    sources: Optional[List[dict]] = None,
    enable_citation_tagging: Optional[bool] = None,
  ) -> int:
    """Save interaction with business logic applied.

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
      raw_response: Raw API response (validated JSON)
      data_source: Data collection mode
      extra_links_count: Number of extra links
      sources: List of source dicts linked directly to response (for web capture mode)
      enable_citation_tagging: Optional per-interaction override (web captures only)

    Returns:
      The response ID
    """
    # Normalize model name (e.g., gpt-5-1 → gpt-5.1)
    normalized_model = normalize_model_name(model)

    normalized_queries = self._normalize_search_queries(search_queries)
    normalized_citations = self._normalize_citations(citations)
    normalized_sources = self._normalize_sources(sources)
    normalized_raw_response = self._normalize_raw_response(raw_response)

    # Extract domains from search query sources
    for query in normalized_queries:
      for source in query.get("sources", []):
        if "url" in source and not source.get("domain"):
          source["domain"] = extract_domain(source["url"])

    # Extract domains from citations
    for citation in normalized_citations:
      if "url" in citation and not citation.get("domain"):
        citation["domain"] = extract_domain(citation["url"])

    # Extract domains from top-level sources (web capture mode)
    if normalized_sources:
      for source in normalized_sources:
        if "url" in source and not source.get("domain"):
          source["domain"] = extract_domain(source["url"])

    # Compute metrics
    # sources_found: Total sources from search queries or top-level sources (web mode)
    if data_source in ("web", "network_log") and normalized_sources:
      sources_found = len(normalized_sources)
    else:
      sources_found = sum(len(q.get("sources", [])) for q in normalized_queries)

    # sources_used: Count of citations with rank (from search results)
    sources_used = len([c for c in normalized_citations if c.get("rank") is not None])

    # avg_rank: Average rank of citations (excluding None)
    # Convert dicts to objects for calculate_average_rank
    citation_objects = [SimpleNamespace(**c) for c in normalized_citations]
    avg_rank = calculate_average_rank(citation_objects)

    # Save to database
    return self.repository.save(
      prompt_text=prompt,
      provider_name=provider,
      model_name=normalized_model,
      response_text=response_text,
      response_time_ms=response_time_ms,
      search_queries=normalized_queries,
      sources_used=normalized_citations,
      raw_response=normalized_raw_response or {},
      data_source=data_source,
      extra_links_count=extra_links_count,
      sources=normalized_sources,
      sources_found=sources_found,
      sources_used_count=sources_used,
      avg_rank=avg_rank,
      citation_tagging_requested=enable_citation_tagging,
    )

  def _set_web_citation_tagging_status(self, response_id: int) -> str:
    """Set initial citation tagging status for a saved web capture.

    This method does not run any tagging; it only sets the status so callers
    can decide whether to enqueue a background job.
    """
    response = self.repository.get_by_id(response_id)
    if not response:
      return "unknown"

    response.citation_tagging_error = None
    response.citation_tagging_started_at = None
    response.citation_tagging_completed_at = None

    if not response.citation_tagging_requested:
      response.citation_tagging_status = "disabled"
      self.repository.db.commit()
      return "disabled"

    # Evaluate effective config for this request (not env-global).
    tagger = CitationTaggingService.from_settings(enabled_override=True)
    if not tagger.config.enabled:
      response.citation_tagging_status = "disabled"
      self.repository.db.commit()
      return "disabled"

    if response.data_source not in ("web", "network_log"):
      response.citation_tagging_status = "skipped"
      self.repository.db.commit()
      return "skipped"

    taggable = [
      source
      for source in (response.sources_used or [])
      if isinstance(source.snippet_cited, str) and source.snippet_cited.strip()
    ]
    if not taggable:
      response.citation_tagging_status = "skipped"
      self.repository.db.commit()
      return "skipped"

    response.citation_tagging_status = "queued"
    self.repository.db.commit()
    return "queued"

  def get_recent_interactions(
    self,
    page: int = 1,
    page_size: int = 20,
    data_source: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
  ) -> Tuple[List[InteractionSummary], int, Optional[QueryHistoryStats]]:
    """Get recent interactions with pagination and filtering.

    Classifies citations into:
    - Sources Used: Citations that came from search results
    - Extra Links: Citations not from search results

    Args:
      page: Page number (1-indexed)
      page_size: Number of items per page (max 100)
      data_source: Filter by data source ("api", "web"). Legacy "network_log" values are also supported.
      provider: Filter by provider name (e.g., "openai")
      model: Filter by model name (e.g., "gpt-4o")
      date_from: Filter by created_at >= date_from
      date_to: Filter by created_at <= date_to

    Returns:
      Tuple of (List of InteractionSummary objects, total count)
    """
    responses, total_count = self.repository.get_recent(
      page=page,
      page_size=page_size,
      data_source=data_source,
      provider=provider,
      model=model,
      date_from=date_from,
      date_to=date_to
    )

    summaries: List[InteractionSummary] = []
    for response in responses:
      # Calculate counts
      search_query_count = len(response.search_queries)
      # For web captures: sources are linked directly to response
      # For api: sources are linked to search queries
      if response.data_source in ('web', 'network_log'):
        source_count = len(response.response_sources) if response.response_sources else 0
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

      interaction = response.interaction
      model = interaction.model_name if interaction else ""
      # Use display_name if available, otherwise fall back to name
      provider_obj = interaction.provider if interaction else None
      if provider_obj and provider_obj.display_name:
        provider_display = provider_obj.display_name
      elif provider_obj:
        provider_display = provider_obj.name
      else:
        provider_display = ""
      prompt_text = interaction.prompt_text if interaction else ""
      summary = InteractionSummary(
        interaction_id=response.id,
        prompt=prompt_text,
        provider=provider_display,
        model=model,
        model_display_name=get_model_display_name(model) if model else None,
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

    stats_payload = self.repository.get_history_stats()
    stats = QueryHistoryStats(**stats_payload) if stats_payload else None

    return summaries, total_count, stats

  def get_interaction_details(self, interaction_id: int) -> Optional[SendPromptResponse]:
    """Get full interaction details with average rank calculation.

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
    for query in (response.search_queries or []):
      sources = [
        SourceSchema(
          url=s.url,
          title=s.title,
          domain=s.domain,
          rank=s.rank,
          pub_date=s.pub_date,
          search_description=None,
          snippet_text=None,
          internal_score=s.internal_score,
          metadata=s.metadata_json,
        )
        for s in (query.sources or [])
      ]

      search_queries.append(
        SearchQuerySchema(
          query=query.search_query or "",
          sources=sources,
          timestamp=query.created_at.isoformat() if query.created_at else None,
          order_index=query.order_index,
          internal_ranking_scores=query.internal_ranking_scores,
          query_reformulations=query.query_reformulations,
        )
      )

    # Convert citations to schemas
    citations = []
    for c in (response.sources_used or []):
      citation_metadata = c.metadata_json or {}
      influence_summary = c.influence_summary if isinstance(c.influence_summary, str) else None
      citations.append(
        CitationSchema(
          url=c.url,
          title=c.title,
          rank=c.rank,
          text_snippet=c.snippet_cited,
          start_index=citation_metadata.get("start_index"),
          end_index=citation_metadata.get("end_index"),
          published_at=citation_metadata.get("published_at"),
          snippet_cited=c.snippet_cited,
          citation_confidence=c.citation_confidence,
          metadata=citation_metadata,
          function_tags=c.function_tags or [],
          stance_tags=c.stance_tags or [],
          provenance_tags=c.provenance_tags or [],
          influence_summary=influence_summary,
        )
      )

    # Populate all_sources for both API and web capture data
    # This provides a consistent, pre-aggregated list for the frontend
    all_sources = []
    if response.data_source in ('web', 'network_log') and response.response_sources:
      # Network_log: sources are directly on response
      all_sources = [
        SourceSchema(
          url=s.url,
          title=s.title,
          domain=s.domain,
          rank=s.rank,
          pub_date=s.pub_date,
          search_description=s.search_description,
          snippet_text=s.search_description,
          internal_score=s.internal_score,
          metadata=s.metadata_json,
        )
        for s in (response.response_sources or [])
      ]
    else:
      # API: gather all sources from search queries
      for query in (response.search_queries or []):
        for s in (query.sources or []):
          all_sources.append(
            SourceSchema(
              url=s.url,
              title=s.title,
              domain=s.domain,
              rank=s.rank,
              pub_date=s.pub_date,
              search_description=None,
              snippet_text=None,
              internal_score=s.internal_score,
              metadata=s.metadata_json,
            )
          )

    # Use stored computed metrics from database
    interaction = response.interaction
    model = interaction.model_name if interaction else ""
    # Use display_name if available, otherwise fall back to name
    provider_obj = interaction.provider if interaction else None
    provider_name = provider_obj.name if provider_obj else ""
    if provider_obj and provider_obj.display_name:
      provider_display = provider_obj.display_name
    elif provider_obj:
      provider_display = provider_obj.name
    else:
      provider_display = ""
    prompt_text = interaction.prompt_text if interaction else ""
    skip_format_providers = {"openai", "google"}
    if (provider_name or "").lower() in skip_format_providers:
      formatted_response = response.response_text or ""
    else:
      formatted_response = self._format_response_text_with_citations(response.response_text or "", citations)
    response_metadata: Dict[str, Any] = {}
    if response.avg_rank is not None:
      response_metadata["average_rank"] = response.avg_rank
    if response.data_source in ("web", "network_log"):
      response_metadata["citation_tagging_status"] = response.citation_tagging_status
      response_metadata["citation_tagging_error"] = response.citation_tagging_error
      response_metadata["citation_tagging_started_at"] = (
        response.citation_tagging_started_at.isoformat()
        if response.citation_tagging_started_at
        else None
      )
      response_metadata["citation_tagging_completed_at"] = (
        response.citation_tagging_completed_at.isoformat()
        if response.citation_tagging_completed_at
        else None
      )
      citations_total = len(response.sources_used or [])
      citations_annotated = 0
      for citation in response.sources_used or []:
        has_tags = any([
          bool(citation.function_tags),
          bool(citation.stance_tags),
          bool(citation.provenance_tags),
        ])
        has_influence = isinstance(citation.influence_summary, str) and bool(citation.influence_summary.strip())
        if has_tags or has_influence:
          citations_annotated += 1
      response_metadata["citation_annotations"] = {
        "total_citations": citations_total,
        "annotated_citations": citations_annotated,
      }

    return SendPromptResponse(
      prompt=prompt_text,
      response_text=formatted_response,
      search_queries=search_queries,
      citations=citations,
      all_sources=all_sources,
      provider=provider_display,
      model=model,
      model_display_name=get_model_display_name(model) if model else None,
      response_time_ms=response.response_time_ms,
      data_source=response.data_source,
      extra_links_count=response.extra_links_count,
      sources_found=response.sources_found or 0,
      sources_used=response.sources_used_count or 0,
      avg_rank=response.avg_rank,
      interaction_id=response.id,
      created_at=response.created_at,
      raw_response=response.raw_response_json,
      metadata=response_metadata or None,
    )

  def save_network_log_interaction(
    self,
    provider: str,
    model: str,
    prompt: str,
    response_text: str,
    search_queries: List[dict],
    sources: List[dict],
    citations: List[dict],
    response_time_ms: int,
    raw_response: Optional[dict],
    extra_links_count: int = 0,
    enable_citation_tagging: bool = True,
  ) -> SendPromptResponse:
    """Save web capture interaction and return formatted response.

    This is a convenience method for the /save-network-log endpoint that
    saves the interaction and returns a fully formatted SendPromptResponse.

    Args:
      provider: Provider name
      model: Model name
      prompt: The prompt text
      response_text: The response text
      search_queries: List of search query dicts
      sources: List of source dicts (for web capture mode)
      citations: List of citation dicts
      response_time_ms: Response time in milliseconds
      raw_response: Raw response data
      extra_links_count: Number of extra links
      enable_citation_tagging: Whether to queue citation tagging for this web capture

    Returns:
      SendPromptResponse with interaction_id and all data
    """
    # Save to database
    response_id = self.save_interaction(
      prompt=prompt,
      provider=provider,
      model=model,
      response_text=response_text,
      response_time_ms=response_time_ms,
      search_queries=search_queries,
      citations=citations,
      raw_response=raw_response or {},
      data_source="web",
      extra_links_count=extra_links_count,
      sources=sources,
      enable_citation_tagging=enable_citation_tagging,
    )

    # Mark citation tagging status so the API can enqueue work without blocking the request.
    self._set_web_citation_tagging_status(response_id)

    # Retrieve the saved interaction to return full data
    details = self.get_interaction_details(response_id)
    assert details is not None
    return details

  def delete_interaction(self, interaction_id: int) -> bool:
    """Delete an interaction.

    Args:
      interaction_id: The interaction (response) ID to delete

    Returns:
      True if deleted, False if not found
    """
    return self.repository.delete(interaction_id)

  # Internal helpers -----------------------------------------------------

  def _normalize_raw_response(self, raw_response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if raw_response is None:
      return None
    try:
      return self._json_dict_adapter.validate_python(raw_response)
    except ValidationError as exc:
      raise ValueError(f"Invalid raw_response payload: {exc}") from exc

  def _normalize_search_queries(self, search_queries: List[dict]) -> List[dict]:
    normalized = []
    for query in search_queries or []:
      if not isinstance(query, dict):
        raise ValueError("Each search query must be an object")
      normalized_query = dict(query)
      sources = normalized_query.get("sources", []) or []
      normalized_query["sources"] = [self._normalize_source_dict(src) for src in sources]

      if "internal_ranking_scores" in normalized_query:
        normalized_query["internal_ranking_scores"] = self._ensure_optional_dict(
          normalized_query["internal_ranking_scores"],
          "internal_ranking_scores",
        )

      if normalized_query.get("query_reformulations") is not None:
        try:
          normalized_query["query_reformulations"] = self._list_str_adapter.validate_python(
            normalized_query["query_reformulations"]
          )
        except ValidationError as exc:
          raise ValueError(f"query_reformulations must be a list of strings: {exc}") from exc

      normalized.append(normalized_query)
    return normalized

  def _normalize_sources(self, sources: Optional[List[dict]]) -> Optional[List[dict]]:
    if not sources:
      return None
    return [self._normalize_source_dict(source) for source in sources]

  def _normalize_source_dict(self, source: dict) -> dict:
    if not isinstance(source, dict):
      raise ValueError("Source entries must be objects")
    normalized = dict(source)
    normalized["metadata"] = self._normalize_source_metadata(normalized.get("metadata"))
    return normalized

  def _normalize_source_metadata(self, metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return dump_metadata(SourceMetadata, metadata)

  def _normalize_citations(self, citations: List[dict]) -> List[dict]:
    normalized = []
    for citation in citations or []:
      if not isinstance(citation, dict):
        raise ValueError("Citation entries must be objects")
      normalized_citation = dict(citation)
      normalized_citation["metadata"] = dump_metadata(CitationMetadata, normalized_citation.get("metadata"))
      normalized.append(normalized_citation)
    return normalized

  def _format_response_text_with_citations(self, text: str, citations: List[CitationSchema]) -> str:
    """Apply inline formatting using normalized citation metadata."""
    citation_models: List[CitationModel] = []
    for citation in citations or []:
      citation_models.append(
        CitationModel(
          url=citation.url,
          title=citation.title,
          text_snippet=citation.text_snippet,
          rank=citation.rank,
          start_index=citation.start_index,
          end_index=citation.end_index,
          metadata=citation.metadata or {},
        )
      )
    return format_response_with_citations(text or "", citation_models)

  def _ensure_optional_dict(self, value: Any, label: str) -> Optional[Dict[str, Any]]:
    if value is None:
      return None
    try:
      return self._json_dict_adapter.validate_python(value)
    except ValidationError as exc:
      raise ValueError(f"{label} must be a JSON object: {exc}") from exc
