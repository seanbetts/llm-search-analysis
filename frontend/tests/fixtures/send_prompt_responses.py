"""Shared SendPromptResponse fixtures aligned with backend schemas."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from backend.app.api.v1.schemas.responses import SendPromptResponse


def _build_api_response() -> SendPromptResponse:
  """Representative API-mode SendPromptResponse instance."""
  return SendPromptResponse(
    prompt="Summarize the impact of AI regulation in 2024.",
    response_text="Artificial intelligence regulation accelerated in 2024...",
    provider="openai",
    model="gpt-5.1",
    model_display_name="GPT-5.1",
    response_time_ms=1250,
    data_source="api",
    search_queries=[
      {
        "query": "ai regulation 2024",
        "order_index": 0,
        "sources": [
          {
            "url": "https://example.com/regulation-overview",
            "title": "2024 AI Regulation Overview",
            "domain": "example.com",
            "rank": 1,
            "pub_date": "2024-05-02",
          },
          {
            "url": "https://news.example.org/policy",
            "title": "Global Policy Tracker",
            "domain": "news.example.org",
            "rank": 2,
            "pub_date": "2024-04-18",
          },
        ],
      },
      {
        "query": "ai compliance timeline",
        "order_index": 1,
        "sources": [
          {
            "url": "https://gov.example.net/timeline",
            "title": "Compliance Timelines",
            "domain": "gov.example.net",
            "rank": 3,
            "pub_date": "2024-03-30",
          },
        ],
      },
    ],
    citations=[
      {
        "url": "https://example.com/regulation-overview",
        "title": "2024 AI Regulation Overview",
        "rank": 1,
        "text_snippet": "Key deadlines kick in during Q3.",
      },
      {
        "url": "https://news.example.org/policy",
        "title": "Global Policy Tracker",
        "rank": 2,
        "text_snippet": "The EU AI Act remains the most comprehensive.",
      },
    ],
    all_sources=[
      {
        "url": "https://example.com/regulation-overview",
        "title": "2024 AI Regulation Overview",
        "domain": "example.com",
        "rank": 1,
      },
      {
        "url": "https://news.example.org/policy",
        "title": "Global Policy Tracker",
        "domain": "news.example.org",
        "rank": 2,
      },
      {
        "url": "https://gov.example.net/timeline",
        "title": "Compliance Timelines",
        "domain": "gov.example.net",
        "rank": 3,
      },
    ],
    sources_found=3,
    sources_used=2,
    avg_rank=1.5,
    extra_links_count=0,
    interaction_id=42,
    created_at=datetime(2024, 7, 1, 12, 30, tzinfo=timezone.utc),
    raw_response={"id": "mock-openai-response"},
    metadata={"session_id": "demo-session"},
  )


def _build_network_log_response() -> SendPromptResponse:
  """Representative network_log SendPromptResponse instance."""
  return SendPromptResponse(
    prompt="Summarize the latest Anthropic research releases.",
    response_text="Claude models focused on safety research...",
    provider="anthropic",
    model="claude-sonnet-4-5-20250929",
    model_display_name="Claude Sonnet 4.5",
    response_time_ms=2100,
    data_source="network_log",
    search_queries=[
      {
        "query": "anthropic research 2024",
        "order_index": 0,
        "sources": [],
      },
    ],
    citations=[
      {
        "url": "https://anthropic.com/blog/update",
        "title": "Anthropic Research Update",
        "rank": 1,
        "text_snippet": "Anthropic released interpretability work in 2024.",
      },
      {
        "url": "https://research.anthropic.com/papers/safety",
        "title": "Safety Interpretability Paper",
        "rank": 2,
        "text_snippet": "Focus on constitutional AI techniques.",
      },
    ],
    all_sources=[
      {
        "url": "https://anthropic.com/blog/update",
        "title": "Anthropic Research Update",
        "domain": "anthropic.com",
        "rank": 1,
      },
      {
        "url": "https://research.anthropic.com/papers/safety",
        "title": "Safety Interpretability Paper",
        "domain": "anthropic.com",
        "rank": 2,
      },
      {
        "url": "https://arxiv.org/abs/1234.5678",
        "title": "Joint Interpretability Study",
        "domain": "arxiv.org",
        "rank": 3,
      },
    ],
    sources_found=3,
    sources_used=2,
    avg_rank=1.5,
    extra_links_count=0,
    interaction_id=87,
    created_at=datetime(2024, 7, 2, 8, 15, tzinfo=timezone.utc),
    raw_response={"trace_id": "network-log-123"},
    metadata={"session_id": "network-log-session"},
  )


def _to_namespace(value: Any):
  """Recursively convert nested dict/list structures to SimpleNamespace."""
  if isinstance(value, dict):
    return SimpleNamespace(**{k: _to_namespace(v) for k, v in value.items()})
  if isinstance(value, list):
    return [_to_namespace(item) for item in value]
  return value


API_SEND_PROMPT_RESPONSE = _build_api_response().model_dump()
NETWORK_LOG_SEND_PROMPT_RESPONSE = _build_network_log_response().model_dump()
API_SEND_PROMPT_RESPONSE_NS = _to_namespace(API_SEND_PROMPT_RESPONSE)
NETWORK_LOG_SEND_PROMPT_RESPONSE_NS = _to_namespace(NETWORK_LOG_SEND_PROMPT_RESPONSE)


def api_send_prompt_response_dict():
  """Return a deepcopy of the API response payload."""
  return copy.deepcopy(API_SEND_PROMPT_RESPONSE)


def network_log_send_prompt_response_dict():
  """Return a deepcopy of the network_log response payload."""
  return copy.deepcopy(NETWORK_LOG_SEND_PROMPT_RESPONSE)


def api_send_prompt_response_namespace():
  """Return a fresh SimpleNamespace tree for API response payload."""
  return _to_namespace(api_send_prompt_response_dict())


def network_log_send_prompt_response_namespace():
  """Return a fresh SimpleNamespace tree for network_log response payload."""
  return _to_namespace(network_log_send_prompt_response_dict())
