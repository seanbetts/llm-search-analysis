"""Background jobs for web citation tagging.

Web capture persistence derives `snippet_cited` during DB save (by parsing the
response text). Citation tagging requires `snippet_cited` to exist, so we run
tagging as a post-save job using a fresh DB session.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.utils import extract_domain
from app.models.database import Response, SourceUsed
from app.services.citation_tagging_service import (
  CitationInfluenceService,
  CitationTaggingService,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 6


def _create_session_factory() -> sessionmaker:
  connect_args = {}
  if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False, "timeout": 30}
  engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
  return sessionmaker(bind=engine, autoflush=False, autocommit=False)


_SessionLocal = _create_session_factory()


def enqueue_web_citation_tagging(
  response_id: int,
  prompt: str,
  response_text: str,
) -> None:
  """Run citation tagging in a detached background thread."""
  thread = threading.Thread(
    target=_run_web_citation_tagging_job,
    args=(response_id, prompt, response_text),
    daemon=True,
    name=f"citation_tagging:{response_id}",
  )
  thread.start()


def _update_status(
  session: Session,
  response: Response,
  *,
  status: str,
  error: Optional[str] = None,
  started_at: Optional[datetime] = None,
  completed_at: Optional[datetime] = None,
) -> None:
  response.citation_tagging_status = status
  response.citation_tagging_error = error
  if started_at is not None:
    response.citation_tagging_started_at = started_at
  if completed_at is not None:
    response.citation_tagging_completed_at = completed_at
  session.commit()


def _run_web_citation_tagging_job(response_id: int, prompt: str, response_text: str) -> None:
  session: Session = _SessionLocal()
  try:
    response = session.get(Response, response_id)
    if not response:
      return
    if response.data_source not in ("web", "network_log"):
      return

    if not response.citation_tagging_requested:
      _update_status(session, response, status="disabled")
      return

    tagger_config_probe = CitationTaggingService.from_settings(enabled_override=True)
    if not tagger_config_probe.config.enabled:
      _update_status(session, response, status="disabled")
      return

    started_at = datetime.utcnow()
    _update_status(session, response, status="running", started_at=started_at, error=None)

    sources_used = session.scalars(
      select(SourceUsed).where(SourceUsed.response_id == response_id)
    ).all()
    taggable = [s for s in sources_used if isinstance(s.snippet_cited, str) and s.snippet_cited.strip()]
    if not taggable:
      _update_status(session, response, status="skipped", completed_at=datetime.utcnow())
      return

    citations = []
    for source in taggable:
      metadata = source.metadata_json or {}
      citations.append({
        "source_used_id": source.id,
        "url": source.url,
        "title": source.title,
        "rank": source.rank,
        "snippet_cited": source.snippet_cited,
        "start_index": metadata.get("start_index"),
        "end_index": metadata.get("end_index"),
        "metadata": metadata,
        "domain": extract_domain(source.url),
      })

    def _process_one(citation: dict) -> dict:
      local_tagger = CitationTaggingService.from_settings(enabled_override=True)
      local_tagger.annotate_citations(prompt=prompt, response_text=response_text, citations=[citation])
      local_influence = CitationInfluenceService(local_tagger.config)
      local_influence.annotate_influence(prompt=prompt, response_text=response_text, citations=[citation])
      return citation

    max_workers = min(DEFAULT_MAX_CONCURRENCY, max(1, len(citations)))
    updated_payloads: list[dict] = []
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
      futures = [pool.submit(_process_one, citation) for citation in citations]
      for future in as_completed(futures):
        updated_payloads.append(future.result())
    elapsed = time.perf_counter() - start
    logger.info(
      "Citation tagging completed for response_id=%s (%s citations, %s workers) in %.2fs",
      response_id,
      len(citations),
      max_workers,
      elapsed,
    )

    updated = {
      c.get("source_used_id"): c
      for c in updated_payloads
      if c.get("source_used_id") is not None
    }
    for source in taggable:
      payload = updated.get(source.id)
      if not payload:
        continue
      source.function_tags = payload.get("function_tags") or []
      source.stance_tags = payload.get("stance_tags") or []
      source.provenance_tags = payload.get("provenance_tags") or []
      influence_summary = payload.get("influence_summary")
      source.influence_summary = (
        influence_summary
        if isinstance(influence_summary, str) and influence_summary.strip()
        else None
      )

    session.commit()
    _update_status(session, response, status="completed", completed_at=datetime.utcnow())

  except Exception as exc:
    try:
      response = session.get(Response, response_id)
      if response:
        _update_status(session, response, status="failed", error=str(exc), completed_at=datetime.utcnow())
    except Exception:
      session.rollback()
    logger.exception("Citation tagging job failed for response_id=%s", response_id)
  finally:
    session.close()
