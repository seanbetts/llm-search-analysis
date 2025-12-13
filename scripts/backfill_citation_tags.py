#!/usr/bin/env python3
"""Backfill citation tags and influence summaries for stored responses."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
  sys.path.insert(0, str(BACKEND_PATH))

from sqlalchemy import and_, create_engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.config import settings
from app.models.database import InteractionModel, Response, SourceUsed
from app.services.citation_tagging_service import (  # noqa: E402
  CitationInfluenceService,
  CitationTaggingConfig,
  CitationTaggingService,
)

logger = logging.getLogger("citation_backfill")


def _create_session() -> Session:
  engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
  )
  SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
  return SessionLocal()


def _build_services() -> Tuple[CitationTaggingService, CitationInfluenceService]:
  cfg = CitationTaggingConfig(
    enabled=True,
    provider=settings.CITATION_TAGGER_PROVIDER,
    model=settings.CITATION_TAGGER_MODEL,
    temperature=settings.CITATION_TAGGER_TEMPERATURE,
    openai_api_key=settings.OPENAI_API_KEY,
    google_api_key=settings.GOOGLE_API_KEY,
  )

  provider = (cfg.provider or "").lower()
  if provider == "openai" and not cfg.openai_api_key:
    raise RuntimeError("OPENAI_API_KEY is required for citation backfill")
  if provider == "google" and not cfg.google_api_key:
    raise RuntimeError("GOOGLE_API_KEY is required for citation backfill")
  if provider not in {"openai", "google"}:
    raise RuntimeError(f"Unsupported citation provider '{cfg.provider}'")

  tagger = CitationTaggingService(cfg)
  influence = CitationInfluenceService(cfg)
  return tagger, influence


def _load_responses(
  session: Session,
  response_ids: Optional[Sequence[int]],
  limit: Optional[int],
  include_existing: bool,
) -> List[Response]:
  """Load responses that have at least one snippet_cited entry."""
  condition = SourceUsed.snippet_cited.isnot(None)
  if not include_existing:
    condition = and_(condition, SourceUsed.influence_summary.is_(None))

  query = (
    session.query(Response)
    .join(InteractionModel)
    .options(
      joinedload(Response.interaction),
      joinedload(Response.sources_used),
    )
    .filter(Response.sources_used.any(condition))
    .order_by(Response.created_at.asc())
  )

  if response_ids:
    query = query.filter(Response.id.in_(response_ids))
  if limit:
    query = query.limit(limit)
  responses = query.all()
  logger.info("Loaded %s responses containing snippet_cited data", len(responses))
  return responses


def _iter_response_payloads(
  responses: List[Response],
  include_existing: bool,
) -> List[Tuple[Response, str, str, List[Tuple[SourceUsed, dict]]]]:
  bundles: List[Tuple[Response, str, str, List[Tuple[SourceUsed, dict]]]] = []
  for response in responses:
    prompt = response.interaction.prompt_text if response.interaction else ""
    response_text = response.response_text or ""
    pair_list: List[Tuple[SourceUsed, dict]] = []
    for source in response.sources_used or []:
      snippet = (source.snippet_cited or "").strip() if source.snippet_cited else ""
      if not snippet:
        continue
      if not include_existing and source.influence_summary:
        continue
      payload = {
        "url": source.url,
        "title": source.title,
        "rank": source.rank,
        "snippet_cited": snippet,
        "text_snippet": snippet,
        "metadata": dict(source.metadata_json or {}),
        "function_tags": [],
        "stance_tags": [],
        "provenance_tags": [],
      }
      pair_list.append((source, payload))
    if pair_list:
      bundles.append((response, prompt, response_text, pair_list))
  return bundles


def backfill_citations(
  response_ids: Optional[List[int]],
  limit: Optional[int],
  include_existing: bool = False,
  dry_run: bool = False,
) -> None:
  session = _create_session()
  tagger, influence = _build_services()
  try:
    responses = _load_responses(session, response_ids, limit, include_existing)
    bundles = _iter_response_payloads(responses, include_existing)
    if not bundles:
      logger.info("No responses with snippet_cited content found; nothing to do.")
      return
    updated_rows = 0

    for response, prompt, response_text, pairs in bundles:
      citation_payloads = [payload for _, payload in pairs]
      tagger.annotate_citations(prompt, response_text, citation_payloads)
      influence.annotate_influence(prompt, response_text, citation_payloads)
      for source, payload in pairs:
        new_function_tags = payload.get("function_tags") or []
        new_stance_tags = payload.get("stance_tags") or []
        new_provenance_tags = payload.get("provenance_tags") or []
        new_summary = payload.get("influence_summary")
        changed = False
        if source.function_tags != new_function_tags:
          source.function_tags = new_function_tags
          changed = True
        if source.stance_tags != new_stance_tags:
          source.stance_tags = new_stance_tags
          changed = True
        if source.provenance_tags != new_provenance_tags:
          source.provenance_tags = new_provenance_tags
          changed = True
        if new_summary is not None and source.influence_summary != new_summary:
          source.influence_summary = new_summary
          changed = True
        if changed:
          updated_rows += 1

    if dry_run:
      session.rollback()
      logger.info("Dry run complete. Rows that would update: %s", updated_rows)
    else:
      session.commit()
      logger.info("Backfill complete. Rows updated: %s", updated_rows)
  finally:
    session.close()


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Backfill citation tags and influence summaries.")
  parser.add_argument("--response-id", action="append", type=int, dest="response_ids", help="Limit to specific response IDs.")
  parser.add_argument("--limit", type=int, default=None, help="Limit number of responses processed.")
  parser.add_argument(
    "--include-existing",
    action="store_true",
    help="Reprocess citations even if they already have influence summaries.",
  )
  parser.add_argument("--dry-run", action="store_true", help="Run without committing changes.")
  return parser.parse_args()


def main() -> None:
  logging.basicConfig(level=logging.INFO)
  args = parse_args()
  try:
    backfill_citations(
      args.response_ids,
      args.limit,
      include_existing=args.include_existing,
      dry_run=args.dry_run,
    )
  except Exception:
    logger.exception("Citation backfill failed.")
    raise


if __name__ == "__main__":
  main()
