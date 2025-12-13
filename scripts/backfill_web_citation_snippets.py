#!/usr/bin/env python3
"""Backfill snippet_cited for web analyses by parsing response_text footnotes."""

from __future__ import annotations

import argparse
import logging
import re
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

logger = logging.getLogger("web_citation_backfill")


def _create_session() -> Session:
  engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
  )
  SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
  return SessionLocal()


def _normalize_url(url: str) -> str:
  """Normalize URL for matching by removing query params and trailing slash."""
  if not isinstance(url, str):
    return ""
  # Remove query parameters
  base_url = url.split('?')[0]
  # Remove trailing slash
  base_url = base_url.rstrip('/')
  return base_url


def _parse_footnote_definitions(text: str) -> Dict[int, Dict[str, str]]:
  """
  Parse footnote definitions from response text.

  Format: [N]: URL "Title"

  Returns:
    Dict mapping citation_number -> {url, title}
  """
  footnote_pattern = r'\[(\d+)\]:\s+(https?://[^\s]+)(?:\s+"([^"]+)")?'

  footnotes = {}
  for match in re.finditer(footnote_pattern, text):
    citation_num = int(match.group(1))
    url = match.group(2)
    title = match.group(3) if match.group(3) else None

    footnotes[citation_num] = {
      'url': url,
      'title': title
    }

  return footnotes


def _extract_snippet_before_citation(text: str, citation_match: re.Match) -> Optional[str]:
  """Extract the text snippet that appears before a citation marker."""
  position = citation_match.start()

  # Get text before the citation (up to 300 chars back)
  start = max(0, position - 300)
  context = text[start:position]

  # Find the start of the current statement/bullet
  # Look for sentence boundaries, bullets, or section markers
  boundaries = []

  # Strong boundaries (paragraph breaks, bullets)
  if '\n\n' in context:
    boundaries.append(('para', context.rfind('\n\n')))
  if '\n* ' in context:
    boundaries.append(('bullet', context.rfind('\n* ')))
  if '\n🔹 ' in context:
    boundaries.append(('bullet', context.rfind('\n🔹 ')))
  if '\n✅ ' in context:
    boundaries.append(('bullet', context.rfind('\n✅ ')))
  if '\n❌ ' in context:
    boundaries.append(('bullet', context.rfind('\n❌ ')))
  if '\n⚠️ ' in context:
    boundaries.append(('bullet', context.rfind('\n⚠️ ')))

  # Sentence boundary - but only if it's not too close to the end
  # (avoid finding periods right before the citation)
  sentence_boundary = context.rfind('. ')
  if sentence_boundary != -1 and sentence_boundary < len(context) - 20:
    boundaries.append(('sentence', sentence_boundary))

  if boundaries:
    # Sort by position and take the last one
    boundaries.sort(key=lambda x: x[1])
    boundary_type, boundary_pos = boundaries[-1]
    context = context[boundary_pos:]

  # Clean up
  context = context.strip()
  context = re.sub(r'^[*•🔹✅❌⚠️\n\s-]+', '', context)
  context = re.sub(r'\*\*', '', context)  # Remove bold
  context = re.sub(r'\*', '', context)    # Remove italics
  context = re.sub(r':\s*$', '', context).strip()  # Remove trailing colon
  context = re.sub(r'^\.\s*', '', context).strip()  # Remove leading period

  return context if len(context) > 10 else None


def _extract_snippets_from_citations(text: str) -> Dict[int, List[str]]:
  """
  Extract all snippets for each citation number from inline citations.

  Returns:
    Dict mapping citation_number -> list of snippet texts
  """
  # Find where footnotes start to avoid matching them
  footnote_start = text.find('\n[1]: https://')
  inline_text = text[:footnote_start] if footnote_start != -1 else text

  # Find all inline citations with pattern ([Source Name][N])
  all_citations = list(re.finditer(r'\(\[([^\]]+)\]\[(\d+)\]\)', inline_text))

  snippets_by_number = defaultdict(list)

  for match in all_citations:
    citation_num = int(match.group(2))
    snippet = _extract_snippet_before_citation(text, match)

    if snippet:
      snippets_by_number[citation_num].append(snippet)

  return dict(snippets_by_number)


def backfill_web_citation_snippets(dry_run: bool = False) -> None:
  """Backfill snippet_cited for web analyses by parsing response_text."""
  session = _create_session()
  try:
    # Query for web/network_log responses that need backfilling
    responses = (
      session.query(Response)
      .join(InteractionModel)
      .join(Provider)
      .options(
        joinedload(Response.sources_used),
        joinedload(Response.interaction).joinedload(InteractionModel.provider)
      )
      .filter(
        Response.data_source.in_(["web", "network_log"]),
        Provider.name == "openai"
      )
      .all()
    )

    logger.info("Loaded %s responses for processing", len(responses))

    updated_sources = 0
    updated_citation_numbers = 0
    skipped_responses = 0

    for response in responses:
      if not response.response_text:
        logger.debug("Response %s has no response_text, skipping", response.id)
        skipped_responses += 1
        continue

      # Parse footnote definitions from response text
      footnotes = _parse_footnote_definitions(response.response_text)

      if not footnotes:
        logger.debug("Response %s has no footnote definitions, skipping", response.id)
        skipped_responses += 1
        continue

      # Extract snippets for each citation number
      snippets_by_number = _extract_snippets_from_citations(response.response_text)

      # Build URL -> source mapping for this response
      url_to_source = {}
      for source in response.sources_used:
        url_norm = _normalize_url(source.url)
        url_to_source[url_norm] = source

      # Match footnotes to sources and update
      for citation_num, footnote_data in footnotes.items():
        url_norm = _normalize_url(footnote_data['url'])

        # Find matching source
        if url_norm not in url_to_source:
          logger.debug(
            "Response %s: citation [%s] URL not found in sources: %s",
            response.id, citation_num, url_norm
          )
          continue

        source = url_to_source[url_norm]

        # Update citation_number in metadata if needed
        metadata = dict(source.metadata_json or {})
        changed = False

        if metadata.get('citation_number') != citation_num:
          metadata['citation_number'] = citation_num
          source.metadata_json = metadata
          changed = True
          updated_citation_numbers += 1

        # Update snippet_cited if we have snippets for this citation
        snippets = snippets_by_number.get(citation_num, [])

        if snippets:
          # Use the first snippet (or concatenate multiple if desired)
          new_snippet = snippets[0]

          if source.snippet_cited != new_snippet:
            source.snippet_cited = new_snippet
            changed = True

        if changed:
          updated_sources += 1

    # Commit or rollback
    if dry_run:
      session.rollback()
      logger.info(
        "Dry run complete. Sources touched: %s (citation_number updates: %s), Responses skipped: %s",
        updated_sources,
        updated_citation_numbers,
        skipped_responses
      )
    else:
      session.commit()
      logger.info(
        "Backfill committed. Sources updated: %s (citation_number updates: %s), Responses skipped: %s",
        updated_sources,
        updated_citation_numbers,
        skipped_responses
      )
  finally:
    session.close()


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Backfill snippet_cited for web analyses by parsing response_text footnotes."
  )
  parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Process rows without writing changes."
  )
  args = parser.parse_args()
  logging.basicConfig(level=logging.INFO)
  backfill_web_citation_snippets(dry_run=args.dry_run)


if __name__ == "__main__":
  main()
