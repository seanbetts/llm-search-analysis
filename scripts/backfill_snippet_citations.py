#!/usr/bin/env python3
"""Backfill missing citation snippets and metadata."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
  sys.path.insert(0, str(BACKEND_PATH))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.config import settings
from app.models.database import InteractionModel, Provider, Response, SourceUsed

logger = logging.getLogger("snippet_backfill")


def _create_session() -> Session:
  engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
  )
  SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
  return SessionLocal()


def _trim_snippet(value: Optional[str]) -> Optional[str]:
  if isinstance(value, str):
    trimmed = value.strip()
    return trimmed or None
  return None


def _slice_from_indices(text: str, metadata: Dict[str, int]) -> Optional[str]:
  start = metadata.get("start_index")
  end = metadata.get("end_index")
  if isinstance(start, int) and isinstance(end, int) and isinstance(text, str):
    if 0 <= start < end <= len(text):
      snippet = text[start:end].strip()
      return snippet or None
  return None


def _find_span(text: str, snippet: str) -> Optional[Tuple[int, int]]:
  if not (isinstance(text, str) and isinstance(snippet, str)):
    return None
  idx = text.find(snippet)
  if idx == -1:
    return None
  return idx, idx + len(snippet)


def _parse_anthropic_citations(raw_payload: Dict) -> Dict[str, List[str]]:
  """Build mapping of URL → list of cited_text strings."""
  mapping: Dict[str, List[str]] = defaultdict(list)
  if not isinstance(raw_payload, dict):
    return mapping

  for block in raw_payload.get("content", []):
    if not isinstance(block, dict):
      continue
    cites = block.get("citations") or []
    for citation in cites:
      if not isinstance(citation, dict):
        continue
      url = citation.get("url")
      snippet = citation.get("cited_text") or citation.get("text")
      snippet = _trim_snippet(snippet)
      if url and snippet:
        mapping[url].append(snippet)
  return mapping


def _load_raw_payload(response: Response) -> Optional[Dict]:
  raw = response.raw_response_json
  if raw is None:
    return None
  if isinstance(raw, dict):
    return raw
  if isinstance(raw, str):
    try:
      return json.loads(raw)
    except json.JSONDecodeError:
      logger.debug("Failed to parse raw_response_json for response %s", response.id)
      return None
  return None


def backfill_snippets(dry_run: bool = False) -> None:
  session = _create_session()
  try:
    sources = (
      session.query(SourceUsed)
      .join(Response)
      .join(InteractionModel)
      .join(Provider)
      .options(
        joinedload(SourceUsed.response)
        .joinedload(Response.interaction)
        .joinedload(InteractionModel.provider)
      )
      .filter(
        (SourceUsed.snippet_cited.is_(None))
        | (SourceUsed.metadata_json.is_(None))
      )
      .all()
    )
    logger.info("Loaded %s source rows for backfill consideration", len(sources))

    updated_rows = 0
    lookup_cache: Dict[int, Dict[str, List[str]]] = {}
    for source in sources:
      provider = (source.response.interaction.provider.name or "").lower()
      response_text = source.response.response_text or ""
      metadata = dict(source.metadata_json or {})
      snippet = _trim_snippet(source.snippet_cited)

      if not snippet:
        snippet = _slice_from_indices(response_text, metadata)

      if not snippet and metadata.get("snippet"):
        snippet = _trim_snippet(metadata.get("snippet"))

      if not snippet and provider == "anthropic":
        if source.response.id not in lookup_cache:
          raw = _load_raw_payload(source.response)
          lookup_cache[source.response.id] = _parse_anthropic_citations(raw or {})
        lookup = lookup_cache[source.response.id]
        candidates = lookup.get(source.url) or []
        if candidates:
          snippet = candidates.pop(0)

      if snippet and (metadata.get("start_index") is None or metadata.get("end_index") is None):
        span = _find_span(response_text, snippet)
        if span:
          metadata["start_index"], metadata["end_index"] = span

      changed = False
      if snippet and source.snippet_cited != snippet:
        source.snippet_cited = snippet
        changed = True
      if metadata and metadata != (source.metadata_json or {}):
        source.metadata_json = metadata
        changed = True
      if changed:
        updated_rows += 1

    if dry_run:
      session.rollback()
      logger.info("Dry run complete. Rows touched: %s", updated_rows)
    else:
      session.commit()
      logger.info("Backfill committed. Rows updated: %s", updated_rows)
  finally:
    session.close()


def main() -> None:
  parser = argparse.ArgumentParser(description="Backfill missing citation snippets and metadata.")
  parser.add_argument("--dry-run", action="store_true", help="Process rows without writing changes.")
  args = parser.parse_args()
  logging.basicConfig(level=logging.INFO)
  backfill_snippets(dry_run=args.dry_run)


if __name__ == "__main__":
  main()
