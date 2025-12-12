#!/usr/bin/env python3
"""Benchmark citation tagging across stored web captures and models."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
  sys.path.insert(0, str(BACKEND_PATH))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, joinedload, sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.models.database import Response  # noqa: E402
from app.services.citation_tagging_service import (  # noqa: E402
  CitationTaggingConfig,
  CitationTaggingService,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citation_benchmark")


@dataclass
class ModelSpec:
  """Benchmark target model specification."""

  provider: str
  model: str
  price_per_million: Optional[float] = None


DEFAULT_MODEL_SPECS = [
  ModelSpec("openai", "gpt-5.1", 1.25),
  ModelSpec("openai", "gpt-5-mini", 0.25),
  ModelSpec("openai", "gpt-5-nano", 0.05),
  ModelSpec("google", "gemini-2.5-pro", 1.25),
  ModelSpec("google", "gemini-2.5-flash", 0.30),
  ModelSpec("google", "gemini-2.5-flash-lite", 0.10),
]


def _create_session() -> Session:
  engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
  )
  SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
  return SessionLocal()


def _load_responses(
  session: Session,
  limit: int,
  offset: int,
  response_ids: Optional[List[int]] = None,
) -> List[Response]:
  query = (
    session.query(Response)
    .options(
      joinedload(Response.sources_used),
      joinedload(Response.interaction),
    )
    .order_by(Response.created_at.desc())
  )
  if response_ids:
    query = query.filter(Response.id.in_(response_ids))
  if offset:
    query = query.offset(offset)
  if limit:
    query = query.limit(limit)
  return query.all()


def _build_citation_dicts(response: Response) -> List[dict]:
  citations = []
  for citation in response.sources_used or []:
    snippet = (citation.snippet_cited or "").strip() if citation.snippet_cited else ""
    if not snippet:
      continue
    citations.append({
      "url": citation.url,
      "title": citation.title,
      "rank": citation.rank,
      "text_snippet": snippet,
      "snippet_cited": snippet,
      "start_index": (citation.metadata_json or {}).get("start_index"),
      "end_index": (citation.metadata_json or {}).get("end_index"),
      "metadata": citation.metadata_json or {},
      "function_tags": list(citation.function_tags or []),
      "stance_tags": list(citation.stance_tags or []),
      "provenance_tags": list(citation.provenance_tags or []),
    })
  return citations


def _parse_model_args(raw_models: Optional[List[str]]) -> List[ModelSpec]:
  if not raw_models:
    return DEFAULT_MODEL_SPECS

  defaults_lookup = {
    (spec.provider.lower(), spec.model): spec.price_per_million
    for spec in DEFAULT_MODEL_SPECS
  }
  specs: List[ModelSpec] = []
  for entry in raw_models:
    # Format: provider:model[:price]
    parts = entry.split(":")
    if len(parts) < 2:
      logger.warning("Invalid model override '%s'; expected provider:model[:price]", entry)
      continue
    provider, model = parts[0], parts[1]
    price = float(parts[2]) if len(parts) > 2 else None
    if price is None:
      price = defaults_lookup.get((provider.lower(), model))
    specs.append(ModelSpec(provider=provider, model=model, price_per_million=price))
  return specs or DEFAULT_MODEL_SPECS


def _coerce_int(value: Any) -> Optional[int]:
  try:
    if value is None:
      return None
    return int(value)
  except (TypeError, ValueError):
    return None


def _summarize_rows(rows: List[dict], path: Path) -> None:
  logger.info("Wrote %s benchmark rows to %s", len(rows), path)
  per_model = {}
  for row in rows:
    key = row.get("benchmark_model") or row.get("model")
    per_model.setdefault(key, 0)
    per_model[key] += 1
  for model, count in per_model.items():
    logger.info("  %s rows for model %s", count, model)


def main() -> None:
  parser = argparse.ArgumentParser(description="Run citation tagging across stored web captures for multiple models.")
  parser.add_argument(
    "--models",
    action="append",
    help="Override model list using provider:model[:price_per_million]. Repeat to add multiple entries.",
  )
  parser.add_argument(
    "--temperature",
    type=float,
    default=settings.CITATION_TAGGER_TEMPERATURE,
    help="Sampling temperature",
  )
  parser.add_argument("--limit", type=int, default=0, help="Number of responses to tag (0 = all)")
  parser.add_argument("--offset", type=int, default=0, help="Offset into recent web captures")
  parser.add_argument(
    "--response-id",
    action="append",
    type=int,
    dest="response_ids",
    help="Limit benchmarking to one or more specific response IDs. Repeat flag to add more.",
  )
  parser.add_argument("--openai-api-key", default=settings.OPENAI_API_KEY, help="Override OpenAI API key")
  parser.add_argument("--google-api-key", default=settings.GOOGLE_API_KEY, help="Override Google API key")
  parser.add_argument(
    "--csv-output",
    type=Path,
    default=Path("citation_tagging_benchmark.csv"),
    help="CSV path for consolidated results",
  )
  parser.add_argument("--json-output", type=Path, help="Optional path to write JSON results")
  args = parser.parse_args()

  model_specs = _parse_model_args(args.models)
  session = _create_session()
  responses = _load_responses(session, args.limit, args.offset, response_ids=args.response_ids)
  extra_log = f" response_ids={args.response_ids}" if args.response_ids else ""
  logger.info("Loaded %s responses for benchmarking%s", len(responses), extra_log)
  if not responses:
    logger.warning("No responses matched the provided filters.")
    return

  base_payloads = []
  for response in responses:
    prompt_text = response.interaction.prompt_text if response.interaction else ""
    response_text = response.response_text or ""
    citations = _build_citation_dicts(response)
    if not citations:
      continue
    base_payloads.append({
      "response_id": response.id,
      "prompt": prompt_text,
      "response_text": response_text,
      "citations": citations,
      "created_at": response.created_at.isoformat() if response.created_at else "",
      "provider": (
        response.interaction.provider.name
        if response.interaction and response.interaction.provider
        else ""
      ),
      "model": response.interaction.model_name if response.interaction else "",
    })

  if not base_payloads:
    logger.warning(
      "No citations with snippet_cited values were found for the selected responses. "
      "Ensure snippets exist or adjust your filters (e.g., --data-source all or --response-id ...)."
    )
    return

  all_rows = []
  json_results = []
  total_tagged_assignments = 0
  for spec in model_specs:
    if spec.provider.lower() == "openai" and not args.openai_api_key:
      logger.warning("Skipping %s because OPENAI_API_KEY is not set", spec.model)
      continue
    if spec.provider.lower() == "google" and not args.google_api_key:
      logger.warning("Skipping %s because GOOGLE_API_KEY is not set", spec.model)
      continue

    cfg = CitationTaggingConfig(
      enabled=True,
      provider=spec.provider,
      model=spec.model,
      temperature=args.temperature,
      openai_api_key=args.openai_api_key,
      google_api_key=args.google_api_key,
    )
    tagger = CitationTaggingService(cfg)
    logger.info("Benchmarking %s (%s)...", spec.model, spec.provider)

    for payload in base_payloads:
      citations = copy.deepcopy(payload["citations"])
      tagger.annotate_citations(payload["prompt"], payload["response_text"], citations)
      usage_records = tagger.get_last_usage_records()
      for idx, citation in enumerate(citations):
        usage = usage_records[idx] if idx < len(usage_records) else {}
        input_tokens = _coerce_int((usage or {}).get("input_tokens") or (usage or {}).get("prompt_tokens"))
        output_tokens = _coerce_int((usage or {}).get("output_tokens") or (usage or {}).get("completion_tokens"))
        total_tokens = _coerce_int((usage or {}).get("total_tokens"))
        if total_tokens is None and (input_tokens is not None or output_tokens is not None):
          total_tokens = (input_tokens or 0) + (output_tokens or 0)
        est_cost = ""
        if spec.price_per_million and total_tokens is not None:
          est_cost = (spec.price_per_million * total_tokens) / 1_000_000
        if citation.get("function_tags") or citation.get("stance_tags") or citation.get("provenance_tags"):
          total_tagged_assignments += len(citation.get("function_tags") or []) + len(citation.get("stance_tags") or []) + len(citation.get("provenance_tags") or [])
        row = {
          "benchmark_provider": spec.provider,
          "benchmark_model": spec.model,
          "price_per_million": spec.price_per_million or "",
          "response_id": payload["response_id"],
          "response_provider": payload["provider"],
          "response_model": payload["model"],
          "prompt": payload["prompt"],
          "citation_url": citation.get("url"),
          "citation_title": citation.get("title"),
          "citation_rank": citation.get("rank"),
          "function_tags": ";".join(citation.get("function_tags") or []),
          "stance_tags": ";".join(citation.get("stance_tags") or []),
          "provenance_tags": ";".join(citation.get("provenance_tags") or []),
          "input_tokens": input_tokens if input_tokens is not None else "",
          "output_tokens": output_tokens if output_tokens is not None else "",
          "total_tokens": total_tokens if total_tokens is not None else "",
          "estimated_cost": est_cost,
        }
        all_rows.append(row)
        json_results.append({
          **row,
          "function_tags": citation.get("function_tags"),
          "stance_tags": citation.get("stance_tags"),
          "provenance_tags": citation.get("provenance_tags"),
        })

  if not all_rows:
    logger.warning("No benchmark rows generated (missing API keys, models, or taggable citations?).")
    return

  if total_tagged_assignments == 0:
    logger.warning(
      "Citations were processed but no tags were produced; skipping CSV/JSON output. "
      "Check LLM API responses or adjust configuration."
    )
    return

  args.csv_output.parent.mkdir(parents=True, exist_ok=True)
  with args.csv_output.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
    writer.writeheader()
    writer.writerows(all_rows)
  _summarize_rows(all_rows, args.csv_output)

  if args.json_output:
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    with args.json_output.open("w", encoding="utf-8") as handle:
      json.dump(json_results, handle, indent=2)
    logger.info("Wrote JSON results to %s", args.json_output)


if __name__ == "__main__":
  main()
