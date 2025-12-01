"""Service layer for LLM provider integration."""

from typing import Dict, List
from app.config import settings
from app.services.providers import ProviderFactory, ProviderResponse
from app.api.v1.schemas.responses import ProviderInfo, SendPromptResponse
from app.services.interaction_service import InteractionService


class ProviderService:
  """Service for managing LLM provider interactions."""

  def __init__(self, interaction_service: InteractionService):
    """
    Initialize service with interaction service.

    Args:
      interaction_service: InteractionService instance for saving responses
    """
    self.interaction_service = interaction_service

  def _get_api_keys(self) -> Dict[str, str]:
    """
    Get API keys from settings.

    Returns:
      Dictionary of provider names to API keys
    """
    return {
      "openai": settings.OPENAI_API_KEY,
      "google": settings.GOOGLE_API_KEY,
      "anthropic": settings.ANTHROPIC_API_KEY,
    }

  def send_prompt(
    self,
    prompt: str,
    model: str,
    save_to_db: bool = True
  ) -> SendPromptResponse:
    """
    Send prompt to LLM provider and get response.

    Args:
      prompt: User's prompt
      model: Model to use (e.g., "gpt-5.1")
      save_to_db: Whether to save the interaction to database (default True)

    Returns:
      SendPromptResponse with full interaction data

    Raises:
      ValueError: If model is not supported or API key is missing
      Exception: If API call fails
    """
    # Get API keys
    api_keys = self._get_api_keys()

    # Get provider instance
    provider = ProviderFactory.get_provider(model, api_keys)

    # Send prompt to provider
    provider_response: ProviderResponse = provider.send_prompt(prompt, model)

    # Convert to dict format for saving
    search_queries_dict = []
    for query in provider_response.search_queries:
      sources_dict = []
      for source in query.sources:
        sources_dict.append({
          "url": source.url,
          "title": source.title,
          "domain": source.domain,
          "rank": source.rank,
          "pub_date": source.pub_date,
          "snippet_text": source.snippet_text,
          "internal_score": source.internal_score,
          "metadata": source.metadata,
        })

      search_queries_dict.append({
        "query": query.query,
        "sources": sources_dict,
        "timestamp": query.timestamp,
        "order_index": query.order_index,
        "internal_ranking_scores": query.internal_ranking_scores,
        "query_reformulations": query.query_reformulations,
      })

    citations_dict = []
    for citation in provider_response.citations:
      citations_dict.append({
        "url": citation.url,
        "title": citation.title,
        "rank": citation.rank,
        "snippet_used": citation.snippet_used,
        "citation_confidence": citation.citation_confidence,
        "metadata": citation.metadata,
      })

    # Save to database if requested
    interaction_id = None
    if save_to_db:
      interaction_id = self.interaction_service.save_interaction(
        prompt=prompt,
        provider=provider_response.provider,
        model=provider_response.model,
        response_text=provider_response.response_text,
        response_time_ms=provider_response.response_time_ms or 0,
        search_queries=search_queries_dict,
        citations=citations_dict,
        raw_response=provider_response.raw_response,
        data_source=provider_response.data_source,
        extra_links_count=provider_response.extra_links_count,
      )

    # Return full response using get_interaction_details to get proper schema
    if interaction_id:
      return self.interaction_service.get_interaction_details(interaction_id)
    else:
      # If not saved, construct response directly
      from app.api.v1.schemas.responses import SearchQuery as SearchQuerySchema, Citation as CitationSchema
      from datetime import datetime

      search_queries_schema = []
      for query in provider_response.search_queries:
        from app.api.v1.schemas.responses import Source as SourceSchema
        sources_schema = [
          SourceSchema(
            url=s.url,
            title=s.title,
            domain=s.domain,
            rank=s.rank,
            pub_date=s.pub_date,
            snippet_text=s.snippet_text,
            internal_score=s.internal_score,
            metadata=s.metadata,
          )
          for s in query.sources
        ]

        search_queries_schema.append(
          SearchQuerySchema(
            query=query.query,
            sources=sources_schema,
            timestamp=query.timestamp,
            order_index=query.order_index,
            internal_ranking_scores=query.internal_ranking_scores,
            query_reformulations=query.query_reformulations,
          )
        )

      citations_schema = [
        CitationSchema(
          url=c.url,
          title=c.title,
          rank=c.rank,
          snippet_used=c.snippet_used,
          citation_confidence=c.citation_confidence,
          metadata=c.metadata,
        )
        for c in provider_response.citations
      ]

      return SendPromptResponse(
        response_text=provider_response.response_text,
        search_queries=search_queries_schema,
        citations=citations_schema,
        provider=provider_response.provider,
        model=provider_response.model,
        response_time_ms=provider_response.response_time_ms,
        data_source=provider_response.data_source,
        extra_links_count=provider_response.extra_links_count,
        interaction_id=None,
        created_at=datetime.utcnow(),
        raw_response=provider_response.raw_response,
      )

  def get_available_providers(self) -> List[ProviderInfo]:
    """
    Get list of available providers.

    Returns:
      List of ProviderInfo objects
    """
    providers = []

    # Check which API keys are configured
    api_keys = self._get_api_keys()

    # OpenAI
    if api_keys.get("openai"):
      providers.append(ProviderInfo(
        name="openai",
        display_name="OpenAI",
        is_active=True,
        supported_models=[
          "gpt-5.1",
          "gpt-5-mini",
          "gpt-5-nano",
        ]
      ))

    # Google
    if api_keys.get("google"):
      providers.append(ProviderInfo(
        name="google",
        display_name="Google",
        is_active=True,
        supported_models=[
          "gemini-3-pro-preview",
          "gemini-2.5-flash",
          "gemini-2.5-flash-lite",
        ]
      ))

    # Anthropic
    if api_keys.get("anthropic"):
      providers.append(ProviderInfo(
        name="anthropic",
        display_name="Anthropic",
        is_active=True,
        supported_models=[
          "claude-sonnet-4-5-20250929",
          "claude-haiku-4-5-20251001",
          "claude-opus-4-1-20250805",
        ]
      ))

    return providers

  def get_available_models(self) -> List[str]:
    """
    Get list of all available models from configured providers.

    Returns:
      List of model identifiers
    """
    models = []
    providers = self.get_available_providers()

    for provider in providers:
      if provider.is_active:
        models.extend(provider.supported_models)

    return models

  def get_provider_for_model(self, model: str) -> str:
    """
    Get the provider name for a given model.

    Args:
      model: Model identifier

    Returns:
      Provider name

    Raises:
      ValueError: If model is not supported
    """
    provider_name = ProviderFactory.get_provider_for_model(model)
    if not provider_name:
      raise ValueError(f"Model '{model}' is not supported")
    return provider_name
