"""Shared helpers for interactive tabs."""

from types import SimpleNamespace
from typing import Any, Dict, List

from frontend.helpers.metrics import compute_metrics, get_model_display_name


def build_api_response(response_data: Dict[str, Any]) -> SimpleNamespace:
  """Convert backend API payload into response namespace for rendering."""
  search_queries = []
  for query_data in response_data.get('search_queries', []):
    sources = [SimpleNamespace(**src) for src in query_data.get('sources', [])]
    search_query = SimpleNamespace(
      query=query_data.get('query'),
      sources=sources,
      timestamp=query_data.get('timestamp'),
      order_index=query_data.get('order_index'),
    )
    search_queries.append(search_query)

  citations = [SimpleNamespace(**citation) for citation in response_data.get('citations', [])]
  all_sources = [SimpleNamespace(**src) for src in response_data.get('all_sources', [])]

  return SimpleNamespace(
    provider=response_data.get('provider'),
    model=response_data.get('model'),
    model_display_name=response_data.get('model_display_name'),
    response_text=response_data.get('response_text'),
    search_queries=search_queries,
    all_sources=all_sources,
    citations=citations,
    response_time_ms=response_data.get('response_time_ms'),
    data_source=response_data.get('data_source', 'api'),
    sources_found=response_data.get('sources_found', 0),
    sources_used=response_data.get('sources_used', 0),
    avg_rank=response_data.get('avg_rank'),
    extra_links_count=response_data.get('extra_links_count', 0),
    raw_response=response_data.get('raw_response', {}),
  )


def build_web_response(provider_response) -> SimpleNamespace:
  """Convert ChatGPTCapturer ProviderResponse into response namespace."""
  search_queries: List[SimpleNamespace] = []
  for query in provider_response.search_queries:
    sources = [SimpleNamespace(
      url=s.url,
      title=s.title,
      domain=s.domain,
      rank=s.rank,
      pub_date=s.pub_date,
      search_description=getattr(s, "search_description", None) or getattr(s, "snippet_text", None),
      internal_score=s.internal_score,
      metadata=s.metadata,
    ) for s in query.sources]

    search_queries.append(SimpleNamespace(
      query=query.query,
      sources=sources,
      timestamp=query.timestamp,
      order_index=query.order_index,
    ))

  citations = [SimpleNamespace(
    url=c.url,
    title=c.title,
    rank=c.rank,
    text_snippet=c.text_snippet,
    snippet_cited=c.snippet_cited,
    citation_confidence=c.citation_confidence,
    function_tags=c.function_tags,
    stance_tags=c.stance_tags,
    provenance_tags=c.provenance_tags,
    influence_summary=c.influence_summary,
    metadata=c.metadata,
  ) for c in provider_response.citations]

  all_sources = [SimpleNamespace(
    url=s.url,
    title=s.title,
    domain=s.domain,
    rank=s.rank,
    pub_date=s.pub_date,
    search_description=getattr(s, "search_description", None) or getattr(s, "snippet_text", None),
    internal_score=s.internal_score,
    metadata=s.metadata,
  ) for s in provider_response.sources]

  metrics = compute_metrics(search_queries, citations, all_sources)

  return SimpleNamespace(
    provider=provider_response.provider,
    model=provider_response.model,
    model_display_name=get_model_display_name(provider_response.model),
    response_text=provider_response.response_text,
    search_queries=search_queries,
    all_sources=all_sources,
    citations=citations,
    response_time_ms=provider_response.response_time_ms,
    data_source='web',
    sources_found=metrics['sources_found'],
    sources_used=metrics['sources_used'],
    avg_rank=metrics['avg_rank'],
    extra_links_count=metrics['extra_links_count'],
    raw_response=provider_response.raw_response,
  )
