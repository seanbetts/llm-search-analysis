#!/usr/bin/env python3
"""
Audit and optionally fix JSON blobs stored in the database.

This script validates:
  1. Provider raw_response_json payloads (OpenAI, Google, Anthropic)
  2. internal_ranking_scores on SearchQuery rows
  3. metadata_json columns on query/response sources and sources_used

Use --fix to write sanitized versions back to the database; otherwise the
script only reports issues.
"""

from __future__ import annotations

import argparse
import logging
from typing import Callable, Dict, Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload, sessionmaker

from app.config import settings
from app.core.json_schemas import CitationMetadata, SourceMetadata, dump_metadata
from app.core.provider_schemas import (
  validate_anthropic_raw_response,
  validate_google_raw_response,
  validate_openai_raw_response,
)
from app.models.database import (
  Prompt,
  Provider,
  QuerySource,
  Response,
  ResponseSource,
  SearchQuery,
  SessionModel,
  SourceUsed,
)

ProviderValidator = Callable[[Dict[str, any]], Dict[str, any]]

PROVIDER_VALIDATORS: Dict[str, ProviderValidator] = {
  "openai": validate_openai_raw_response,
  "anthropic": validate_anthropic_raw_response,
  "google": validate_google_raw_response,
}


def audit_raw_responses(session, fix: bool, logger: logging.Logger) -> Tuple[int, int]:
  """Validate raw_response_json for API responses."""
  invalid = 0
  updated = 0
  responses = (
    session.query(Response)
    .options(
      joinedload(Response.prompt)
      .joinedload(Prompt.session)
      .joinedload(SessionModel.provider)
    )
    .all()
  )

  for response in responses:
    if response.data_source != "api":
      continue
    if not response.raw_response_json:
      continue
    provider_obj: Optional[Provider] = (
      response.prompt.session.provider if response.prompt and response.prompt.session else None
    )
    provider_name = provider_obj.name if provider_obj else None
    if not provider_name:
      continue
    validator = PROVIDER_VALIDATORS.get(provider_name)
    if not validator:
      continue
    try:
      sanitized = validator(response.raw_response_json)
    except ValueError as exc:
      invalid += 1
      logger.warning(
        "Invalid %s raw_response_json for response_id=%s: %s",
        provider_name,
        response.id,
        exc,
      )
      if fix:
        response.raw_response_json = None
      continue
    if sanitized != response.raw_response_json:
      updated += 1
      if fix:
        response.raw_response_json = sanitized

  return invalid, updated


def audit_internal_ranking_scores(session, fix: bool, logger: logging.Logger) -> int:
  """Ensure internal_ranking_scores columns are JSON objects."""
  invalid = 0
  queries = session.query(SearchQuery).all()
  for query in queries:
    value = query.internal_ranking_scores
    if value is None:
      continue
    if isinstance(value, dict):
      continue
    invalid += 1
    logger.warning("Invalid internal_ranking_scores on search_query_id=%s", query.id)
    if fix:
      query.internal_ranking_scores = None
  return invalid


def _sanitize_metadata(records, attr: str, model_cls, fix: bool, logger: logging.Logger) -> Tuple[int, int]:
  invalid = 0
  updated = 0
  for record in records:
    value = getattr(record, attr)
    if value is None:
      continue
    try:
      sanitized = dump_metadata(model_cls, value)
    except ValueError as exc:
      invalid += 1
      logger.warning(
        "Invalid metadata on %s id=%s: %s",
        record.__class__.__name__,
        getattr(record, "id", "unknown"),
        exc,
      )
      if fix:
        setattr(record, attr, None)
      continue
    if sanitized != value and fix:
      setattr(record, attr, sanitized)
      updated += 1
  return invalid, updated


def main() -> None:
  parser = argparse.ArgumentParser(description="Audit provider/network JSON payloads.")
  parser.add_argument(
    "--fix",
    action="store_true",
    help="Write sanitized payloads back to the database."
  )
  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
  logger = logging.getLogger("audit_json_payloads")

  connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
  engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
  SessionLocal = sessionmaker(bind=engine)

  session = SessionLocal()
  try:
    raw_invalid, raw_updated = audit_raw_responses(session, args.fix, logger)
    ranking_invalid = audit_internal_ranking_scores(session, args.fix, logger)

    query_sources = session.query(QuerySource).all()
    response_sources = session.query(ResponseSource).all()
    sources_used = session.query(SourceUsed).all()

    qs_invalid, qs_updated = _sanitize_metadata(query_sources, "metadata_json", SourceMetadata, args.fix, logger)
    rs_invalid, rs_updated = _sanitize_metadata(response_sources, "metadata_json", SourceMetadata, args.fix, logger)
    su_invalid, su_updated = _sanitize_metadata(sources_used, "metadata_json", CitationMetadata, args.fix, logger)

    total_invalid = raw_invalid + ranking_invalid + qs_invalid + rs_invalid + su_invalid
    total_updates = raw_updated + qs_updated + rs_updated + su_updated

    if args.fix:
      session.commit()
      logger.info("Applied %s metadata/response updates.", total_updates)
    else:
      session.rollback()
      logger.info("Dry run complete. %s rows would be updated.", total_updates)

    if total_invalid:
      logger.info("Found %s invalid payloads.", total_invalid)
    else:
      logger.info("No invalid payloads detected.")

  finally:
    session.close()


if __name__ == "__main__":
  main()
