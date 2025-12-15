#!/usr/bin/env python3
"""Backfill missing citation snippets and metadata."""

# ruff: noqa: E402

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

from sqlalchemy import create_engine, or_
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


def _slice_from_indices(text_candidates: List[Optional[str]], metadata: Dict[str, int]) -> Optional[str]:
  start = metadata.get("start_index")
  end = metadata.get("end_index")
  if start is None and metadata.get("segment_start_index") is not None:
    start = metadata.get("segment_start_index")
  if end is None and metadata.get("segment_end_index") is not None:
    end = metadata.get("segment_end_index")
  if start is None and isinstance(end, int) and end >= 0:
    start = 0
  if not isinstance(start, int) or not isinstance(end, int):
    return None
  for text in text_candidates:
    if not isinstance(text, str):
      continue
    if 0 <= start < end <= len(text):
      snippet = text[start:end].strip()
      if snippet:
        return snippet
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


def _extract_raw_text(raw_payload: Optional[Dict]) -> Optional[str]:
  if not isinstance(raw_payload, dict):
    return None

  output = raw_payload.get("output")
  if isinstance(output, list):
    chunks = []
    for item in output:
      if not isinstance(item, dict):
        continue
      if item.get("type") == "message":
        for content in item.get("content") or []:
          text = content.get("text")
          if text:
            chunks.append(text)
    if chunks:
      return "".join(chunks)

  candidates = raw_payload.get("candidates")
  if isinstance(candidates, list):
    chunks = []
    for candidate in candidates:
      if not isinstance(candidate, dict):
        continue
      for content in candidate.get("content") or []:
        if not isinstance(content, dict):
          continue
        for part in content.get("parts") or []:
          if isinstance(part, dict):
            text = part.get("text")
          else:
            text = None
          if text:
            chunks.append(text)
    if chunks:
      return "".join(chunks)

  content_blocks = raw_payload.get("content")
  if isinstance(content_blocks, list):
    chunks = []
    for block in content_blocks:
      text = block.get("text")
      if text:
        chunks.append(text)
    if chunks:
      return "".join(chunks)

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
        or_(
          SourceUsed.snippet_cited.is_(None),
          SourceUsed.metadata_json.is_(None),
          Response.data_source.in_(["web", "network_log"]),
        )
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
      existing_snippet = _trim_snippet(source.snippet_cited)
      snippet = existing_snippet
      data_source = (source.response.data_source or "").lower()
      raw_payload = _load_raw_payload(source.response)
      raw_text = _extract_raw_text(raw_payload) or ""

      if data_source in ("web", "network_log"):
        snippet = None
        metadata.pop("start_index", None)
        metadata.pop("end_index", None)
      else:
        if not snippet:
          texts = [response_text]
          if raw_text and raw_text != response_text:
            texts.append(raw_text)
          snippet = _slice_from_indices(texts, metadata)

        if not snippet and provider == "anthropic":
          if source.response.id not in lookup_cache:
            lookup_cache[source.response.id] = _parse_anthropic_citations(raw_payload or {})
          lookup = lookup_cache[source.response.id]
          candidates = lookup.get(source.url) or []
          if candidates:
            snippet = candidates.pop(0)

        if snippet and (metadata.get("start_index") is None or metadata.get("end_index") is None):
          span = _find_span(response_text, snippet)
          if not span and raw_text and raw_text != response_text:
            span = _find_span(raw_text, snippet)
          if span:
            metadata["start_index"], metadata["end_index"] = span

      changed = False
      if snippet != existing_snippet:
        source.snippet_cited = snippet
        changed = True
      if metadata != (source.metadata_json or {}):
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
