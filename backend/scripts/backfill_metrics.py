#!/usr/bin/env python3
"""Recompute stored response metrics (sources_found, sources_used_count, avg_rank).

This script is useful when historical rows predate the current logic or when
manual data fixes leave metrics out of sync with actual sources/citations.
"""

from __future__ import annotations

import argparse
import logging
from typing import Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload, sessionmaker

from app.config import settings
from app.core.utils import calculate_average_rank
from app.models.database import Response, SearchQuery


def compute_metrics(response: Response) -> Tuple[int, int, float | None]:
  """Calculate sources_found, sources_used_count, and avg_rank for a response."""
  if response.data_source == "network_log":
    sources_found = len(response.response_sources or [])
  else:
    sources_found = sum(len(q.sources or []) for q in (response.search_queries or []))

  citations = response.sources_used or []
  sources_used = len([c for c in citations if c.rank is not None])
  avg_rank = calculate_average_rank(citations)
  return sources_found, sources_used, avg_rank


def main() -> None:
  parser = argparse.ArgumentParser(description="Backfill response metrics.")
  parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Compute metrics without persisting changes."
  )
  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
  logger = logging.getLogger("backfill_metrics")

  connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
  engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
  SessionLocal = sessionmaker(bind=engine)

  session = SessionLocal()
  try:
    responses = (
      session.query(Response)
      .options(
        joinedload(Response.search_queries).joinedload(SearchQuery.sources),
        joinedload(Response.response_sources),
        joinedload(Response.sources_used),
      )
      .all()
    )

    updates = 0
    for response in responses:
      sources_found, sources_used, avg_rank = compute_metrics(response)

      changed = (
        (response.sources_found or 0) != sources_found or
        (response.sources_used_count or 0) != sources_used or
        (response.avg_rank != avg_rank)
      )
      if not changed:
        continue

      response.sources_found = sources_found
      response.sources_used_count = sources_used
      response.avg_rank = avg_rank
      updates += 1

    if args.dry_run:
      session.rollback()
      logger.info("Dry run complete. %s rows would be updated.", updates)
    else:
      session.commit()
      logger.info("Updated %s responses.", updates)

  finally:
    session.close()


if __name__ == "__main__":
  main()
