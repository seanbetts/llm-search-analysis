#!/usr/bin/env python3
"""Benchmark citation tagging across stored web captures."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.config import settings
from app.models.database import Response
from app.services.citation_tagging_service import (
  CitationTaggingConfig,
  CitationTaggingService,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citation_benchmark")


def _create_session() -> Session:
  engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
  )
  SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
  return SessionLocal()


def _load_responses(session: Session, limit: int, offset: int) -> List[Response]:
  return (
    session.query(Response)
    .filter(Response.data_source == "web")
    .options(
      joinedload(Response.sources_used),
      joinedload(Response.interaction),
    )
    .order_by(Response.created_at.desc())
    .offset(offset)
    .limit(limit)
    .all()
  )


def _build_citation_dicts(response: Response) -> List[dict]:
  citations = []
  for citation in response.sources_used or []:
    citations.append({
      "url": citation.url,
      "title": citation.title,
      "rank": citation.rank,
      "text_snippet": citation.snippet_used,
      "snippet_used": citation.snippet_used,
      "start_index": (citation.metadata_json or {}).get("start_index"),
      "end_index": (citation.metadata_json or {}).get("end_index"),
      "metadata": citation.metadata_json or {},
      "function_tags": list(citation.function_tags or []),
      "stance_tags": list(citation.stance_tags or []),
      "provenance_tags": list(citation.provenance_tags or []),
    })
  return citations


def main() -> None:
  parser = argparse.ArgumentParser(description="Run citation tagging against stored web captures.")
  parser.add_argument(
    "--provider",
    default=settings.CITATION_TAGGER_PROVIDER,
    help="LLM provider to use (openai or google)",
  )
  parser.add_argument(
    "--model",
    default=settings.CITATION_TAGGER_MODEL,
    help="Provider model identifier",
  )
  parser.add_argument(
    "--temperature",
    type=float,
    default=settings.CITATION_TAGGER_TEMPERATURE,
    help="Sampling temperature",
  )
  parser.add_argument("--limit", type=int, default=10, help="Number of responses to tag")
  parser.add_argument("--offset", type=int, default=0, help="Offset into recent web captures")
  parser.add_argument("--openai-api-key", default=settings.OPENAI_API_KEY, help="Override OpenAI API key")
  parser.add_argument("--google-api-key", default=settings.GOOGLE_API_KEY, help="Override Google API key")
  parser.add_argument("--output", type=Path, help="Optional path to write JSON results")
  args = parser.parse_args()

  cfg = CitationTaggingConfig(
    enabled=True,
    provider=args.provider,
    model=args.model,
    temperature=args.temperature,
    openai_api_key=args.openai_api_key,
    google_api_key=args.google_api_key,
  )
  tagger = CitationTaggingService(cfg)

  session = _create_session()
  responses = _load_responses(session, args.limit, args.offset)
  logger.info("Loaded %s web responses for benchmarking", len(responses))

  results = []
  for response in responses:
    prompt_text = response.interaction.prompt_text if response.interaction else ""
    response_text = response.response_text or ""
    citations = _build_citation_dicts(response)
    tagger.annotate_citations(prompt_text, response_text, citations)

    for citation in citations:
      results.append({
        "response_id": response.id,
        "prompt": prompt_text,
        "url": citation.get("url"),
        "function_tags": citation.get("function_tags"),
        "stance_tags": citation.get("stance_tags"),
        "provenance_tags": citation.get("provenance_tags"),
      })

  if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
      json.dump(results, handle, indent=2)
    logger.info("Wrote %s tagged citations to %s", len(results), args.output)
  else:
    logger.info("Tagged %s citations across %s responses", len(results), len(responses))
    for entry in results[:5]:
      logger.info(
        "Response %s | %s => function=%s stance=%s provenance=%s",
        entry["response_id"],
        entry["url"],
        entry["function_tags"],
        entry["stance_tags"],
        entry["provenance_tags"],
      )


if __name__ == "__main__":
  main()
