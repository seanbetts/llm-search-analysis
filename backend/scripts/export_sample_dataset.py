#!/usr/bin/env python
"""
Export a representative CSV dataset of recent interactions.

The sample is meant to highlight:
- Raw inputs (prompt, provider, model, data source)
- Captured telemetry (search queries, sources, citations)
- Computed metrics (average rank, coverage, response time)
- Possible analysis hooks (domain patterns, metadata flags)
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

# Ensure backend/ is on sys.path so `app.*` imports work when running from repo root
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
  sys.path.append(str(BACKEND_ROOT))

from app.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from app.core.utils import extract_domain  # noqa: E402  pylint: disable=wrong-import-position
from app.models.database import (  # noqa: E402  pylint: disable=wrong-import-position
  InteractionModel,
  Provider,
  QuerySource,
  Response,
  ResponseSource,
  SearchQuery,
  SourceUsed,
)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Export a sample CSV dataset from stored interactions.")
  parser.add_argument(
    "--output",
    default=str(Path("data") / "sample_datasets" / "llm_search_sample.csv"),
    help="Path to write the CSV file (default: data/sample_datasets/llm_search_sample.csv)",
  )
  parser.add_argument(
    "--database-url",
    default=None,
    help="Optional SQLAlchemy database URL. Defaults to app.config.settings.DATABASE_URL",
  )
  parser.add_argument(
    "--limit",
    type=int,
    default=50,
    help="Number of most recent interactions to export (default: 50)",
  )
  return parser.parse_args()


def build_session(database_url: str) -> Session:
  """Create a SQLAlchemy session for the provided database URL."""
  engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
  )
  SessionLocal = sessionmaker(bind=engine)
  return SessionLocal()


def gather_responses(session: Session, limit: int) -> List[Response]:
  """Load recent responses with all related objects eager-loaded."""
  return (
    session.query(Response)
    .options(
      joinedload(Response.interaction).joinedload(InteractionModel.provider),
      joinedload(Response.search_queries).joinedload(SearchQuery.sources),
      joinedload(Response.response_sources),
      joinedload(Response.sources_used),
    )
    .order_by(Response.created_at.desc())
    .limit(limit)
    .all()
  )


def format_queries(response: Response, limit: int = 3) -> str:
  """Return the top search queries in display order."""
  ordered = sorted(response.search_queries or [], key=lambda q: q.order_index or 0)
  return "; ".join(q.search_query or "" for q in ordered[:limit])


def format_citations(response: Response, limit: int = 3) -> str:
  """Summarize key citations for quick scanning."""
  entries = []
  for citation in (response.sources_used or [])[:limit]:
    title = citation.title or extract_domain(citation.url or "") or "Unknown source"
    rank = f" (rank {citation.rank})" if citation.rank else ""
    entries.append(f"{title}{rank}")
  return "; ".join(entries)


def citation_domain_summary(response: Response, max_domains: int = 3) -> str:
  """Count citation domains to highlight topical breadth."""
  counter = Counter()
  for citation in response.sources_used or []:
    domain = extract_domain(citation.url or "")
    if domain:
      counter[domain] += 1
  return ", ".join(f"{domain}:{count}" for domain, count in counter.most_common(max_domains))


def has_network_metadata(response: Response) -> bool:
  """Check if network-log specific metadata (internal scores/reformulations) exists."""
  for query in response.search_queries or []:
    if query.internal_ranking_scores or query.query_reformulations:
      return True
  return False


def determine_analysis_notes(response: Response, sources_used_pct: Optional[float]) -> str:
  """Create a short narrative on how the row could be analyzed."""
  notes: List[str] = []
  if response.data_source == "network_log":
    notes.append("Network capture: compare browser telemetry vs API output")
  if (response.response_time_ms or 0) >= 20000:
    notes.append("Slow response time worth reviewing")
  if response.avg_rank and response.avg_rank >= 8:
    notes.append("Citations rely on lower-ranked sources")
  if sources_used_pct is not None:
    if sources_used_pct <= 25:
      notes.append("Low conversion from search results to citations")
    elif sources_used_pct >= 80:
      notes.append("High alignment between search results and citations")
  if not notes:
    notes.append("Baseline sample for quality benchmarking")
  return " | ".join(notes)


def build_row(response: Response) -> dict:
  """Convert a Response ORM object into a CSV row with metrics + narrative."""
  interaction = response.interaction
  provider_obj = interaction.provider if interaction else Provider(name="unknown")

  search_query_count = len(response.search_queries or [])
  citation_count = len(response.sources_used or [])
  if response.data_source == "network_log":
    source_count = len(response.response_sources or [])
  else:
    source_count = sum(len(q.sources or []) for q in response.search_queries or [])

  sources_found = response.sources_found or source_count
  sources_used = response.sources_used_count or citation_count
  sources_used_pct = None
  if sources_found and sources_used is not None:
    sources_used_pct = round((sources_used / sources_found) * 100, 2) if sources_found else None

  row = {
    "interaction_id": response.id,
    "created_at": response.created_at.isoformat() if response.created_at else "",
    "provider": provider_obj.display_name or provider_obj.name,
    "model": interaction.model_name if interaction else "",
    "data_source": response.data_source,
    "prompt_excerpt": (interaction.prompt_text[:200] if interaction and interaction.prompt_text else "").replace("\n", " ").strip(),
    "response_time_ms": response.response_time_ms or 0,
    "search_query_count": search_query_count,
    "source_record_count": source_count,
    "citation_count": citation_count,
    "sources_found": sources_found,
    "sources_used": sources_used,
    "sources_used_pct": sources_used_pct if sources_used_pct is not None else "",
    "avg_rank": round(response.avg_rank, 2) if response.avg_rank is not None else "",
    "extra_links_count": response.extra_links_count or 0,
    "primary_queries": format_queries(response),
    "top_citations": format_citations(response),
    "citation_domains": citation_domain_summary(response),
    "has_network_metadata": "yes" if has_network_metadata(response) else "no",
    "has_response_sources": "yes" if response.response_sources else "no",
    "analysis_notes": determine_analysis_notes(response, sources_used_pct),
  }

  return row


def write_csv(rows: List[dict], output_path: Path) -> None:
  output_path.parent.mkdir(parents=True, exist_ok=True)
  if not rows:
    print("No interactions found; nothing to write.")
    return

  fieldnames = list(rows[0].keys())
  with output_path.open("w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
  print(f"Wrote {len(rows)} rows to {output_path}")


def main() -> None:
  args = parse_args()
  database_url = args.database_url or settings.DATABASE_URL
  session = build_session(database_url)
  try:
    responses = gather_responses(session, args.limit)
    rows = [build_row(resp) for resp in responses]
  finally:
    session.close()

  write_csv(rows, Path(args.output))


if __name__ == "__main__":
  main()
