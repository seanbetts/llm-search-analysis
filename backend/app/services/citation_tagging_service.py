"""LLM-based citation tagging service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from google.genai import Client as GoogleClient
from google.genai.types import GenerateContentConfig
from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

FUNCTION_TAGS = [
  "evidence",
  "elaboration",
  "background",
  "justification",
  "cause_or_reason",
  "condition",
  "contrast",
  "concession",
  "evaluation",
  "solution_or_answer",
  "enablement",
  "limitation_or_risk",
  "speculation_or_rumour",
]
STANCE_TAGS = [
  "supports",
  "refutes",
  "nuances_or_qualifies",
  "neutral_context",
]
PROVENANCE_TAGS = [
  "news",
  "reference",
  "community",
  "official",
  "review",
  "other",
]


@dataclass
class CitationTaggingConfig:
  """Runtime configuration for citation tagging."""

  enabled: bool
  provider: str
  model: str
  temperature: float = 0.0
  openai_api_key: str = ""
  google_api_key: str = ""


@dataclass
class CitationTaggingResult:
  """Structured tagging output."""

  function_tags: List[str]
  stance_tags: List[str]
  provenance_tags: List[str]


class BaseLLMTagger:
  """Abstract base class for provider-specific taggers."""

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Return raw JSON dict for the provided prompt."""
    raise NotImplementedError


class NullLLMTagger(BaseLLMTagger):
  """Fallback implementation that always returns empty tags."""

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Return empty tag arrays."""
    return {"function_tags": [], "stance_tags": [], "provenance_tags": []}


class OpenAILLMTagger(BaseLLMTagger):
  """LLM tagger that uses the OpenAI Responses API."""

  def __init__(self, api_key: str, model: str, temperature: float):
    self.client = OpenAI(api_key=api_key)
    self.model = model
    self.temperature = temperature

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Call the OpenAI Responses API and parse JSON output."""
    completion = self.client.responses.create(  # type: ignore[arg-type]
      model=self.model,
      temperature=self.temperature,
      response_format={"type": "json_object"},
      input=[
        {
          "role": "system",
          "content": [{"type": "text", "text": _SYSTEM_PROMPT}],
        },
        {
          "role": "user",
          "content": [{"type": "text", "text": prompt}],
        },
      ],
    )
    text_output = completion.output_text[0] if completion.output_text else ""
    return _safe_load_json(text_output)


class GoogleLLMTagger(BaseLLMTagger):
  """LLM tagger that uses Google Gemini via the google-genai SDK."""

  def __init__(self, api_key: str, model: str, temperature: float):
    self.client = GoogleClient(api_key=api_key)
    self.model = model
    self.temperature = temperature

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Call Google Gemini and parse JSON output."""
    config = GenerateContentConfig(
      temperature=self.temperature,
      response_mime_type="application/json",
    )
    response = self.client.models.generate_content(
      model=self.model,
      contents=prompt,
      config=config,
    )
    text_output = getattr(response, "text", None) or getattr(response, "output_text", None)
    if isinstance(text_output, list):
      text_output = text_output[0]
    return _safe_load_json(text_output or "")


class CitationTaggingService:
  """High-level service that orchestrates citation tagging."""

  def __init__(self, config: CitationTaggingConfig):
    self.config = config
    self._tagger = self._build_tagger(config)

  @classmethod
  def from_settings(cls) -> "CitationTaggingService":
    """Create service instance using global settings."""
    cfg = CitationTaggingConfig(
      enabled=settings.ENABLE_CITATION_TAGGING,
      provider=settings.CITATION_TAGGER_PROVIDER,
      model=settings.CITATION_TAGGER_MODEL,
      temperature=settings.CITATION_TAGGER_TEMPERATURE,
      openai_api_key=settings.OPENAI_API_KEY,
      google_api_key=settings.GOOGLE_API_KEY,
    )
    return cls(cfg)

  def annotate_citations(
    self,
    prompt: str,
    response_text: str,
    citations: List[dict],
  ) -> List[dict]:
    """Apply tags to each citation dictionary in-place."""
    if not citations:
      return citations

    if isinstance(self._tagger, NullLLMTagger):
      for citation in citations:
        citation.setdefault("function_tags", [])
        citation.setdefault("stance_tags", [])
        citation.setdefault("provenance_tags", self._default_provenance(citation))
      return citations

    for citation in citations:
      payload = self._build_prompt_payload(prompt, response_text, citation)
      if not payload:
        citation.setdefault("function_tags", [])
        citation.setdefault("stance_tags", [])
        citation.setdefault("provenance_tags", self._default_provenance(citation))
        continue

      prompt_str = _build_prompt_text(payload)
      try:
        raw = self._tagger.generate(prompt_str)
      except Exception:
        logger.exception("Citation tagging failed; continuing with empty tags")
        raw = None
      cleaned = self._sanitize_output(raw, citation)
      citation["function_tags"] = cleaned.function_tags
      citation["stance_tags"] = cleaned.stance_tags
      citation["provenance_tags"] = cleaned.provenance_tags

    return citations

  def _build_tagger(self, config: CitationTaggingConfig) -> BaseLLMTagger:
    if not config.enabled:
      return NullLLMTagger()

    provider = (config.provider or "").lower()
    if provider == "openai":
      if not config.openai_api_key:
        logger.warning("Citation tagging enabled but OPENAI_API_KEY is missing; returning Null tagger")
        return NullLLMTagger()
      return OpenAILLMTagger(config.openai_api_key, config.model, config.temperature)

    if provider == "google":
      if not config.google_api_key:
        logger.warning("Citation tagging enabled but GOOGLE_API_KEY is missing; returning Null tagger")
        return NullLLMTagger()
      return GoogleLLMTagger(config.google_api_key, config.model, config.temperature)

    logger.warning("Unsupported citation tagger provider '%s'; returning Null tagger", provider)
    return NullLLMTagger()

  def _build_prompt_payload(
    self,
    prompt: str,
    response_text: str,
    citation: Dict[str, Any],
  ) -> Optional[Dict[str, Any]]:
    """Extract contextual payload for the LLM prompt."""
    claim_span = _extract_claim_span(response_text or "", citation)
    snippet = citation.get("snippet_used") or citation.get("text_snippet") or ""
    if not claim_span and not snippet:
      return None

    metadata = citation.get("metadata") or {}
    ref_info = metadata.get("ref_id") or {}

    return {
      "prompt": prompt or "",
      "response_text": response_text or "",
      "claim_span": claim_span,
      "citation": {
        "url": citation.get("url"),
        "title": citation.get("title"),
        "rank": citation.get("rank"),
        "snippet": snippet,
        "domain": citation.get("domain"),
        "ref_type": ref_info.get("ref_type"),
        "published_at": metadata.get("published_at"),
      },
    }

  def _sanitize_output(
    self,
    raw: Optional[Dict[str, Any]],
    citation: Dict[str, Any],
  ) -> CitationTaggingResult:
    """Validate and normalize model output."""
    if not raw:
      return CitationTaggingResult(
        function_tags=[],
        stance_tags=[],
        provenance_tags=self._default_provenance(citation),
      )

    def _filter(values: Any, allowed: List[str]) -> List[str]:
      if not isinstance(values, list):
        return []
      cleaned = []
      for item in values:
        if isinstance(item, str):
          token = item.strip()
          if token in allowed and token not in cleaned:
            cleaned.append(token)
      return cleaned

    function_tags = _filter(raw.get("function_tags"), FUNCTION_TAGS)
    stance_tags = _filter(raw.get("stance_tags"), STANCE_TAGS)
    provenance_tags = _filter(raw.get("provenance_tags"), PROVENANCE_TAGS) or self._default_provenance(citation)

    return CitationTaggingResult(
      function_tags=function_tags,
      stance_tags=stance_tags,
      provenance_tags=provenance_tags,
    )

  def _default_provenance(self, citation: Dict[str, Any]) -> List[str]:
    metadata = citation.get("metadata") or {}
    ref_type = (metadata.get("ref_id") or {}).get("ref_type")
    if isinstance(ref_type, str) and ref_type in PROVENANCE_TAGS:
      return [ref_type]
    return []


def _extract_claim_span(response_text: str, citation: Dict[str, Any]) -> str:
  start = citation.get("start_index")
  end = citation.get("end_index")
  if isinstance(start, int) and isinstance(end, int):
    if 0 <= start < end <= len(response_text):
      return response_text[start:end]
  return citation.get("text_snippet") or citation.get("snippet_used") or ""


def _safe_load_json(value: str) -> Optional[Dict[str, Any]]:
  if not value:
    return None
  try:
    return json.loads(value)
  except json.JSONDecodeError:
    start = value.find("{")
    end = value.rfind("}")
    if 0 <= start < end:
      try:
        return json.loads(value[start : end + 1])
      except Exception:
        logger.debug("Failed to salvage JSON payload from %s", value)
  logger.warning("Citation tagger returned non-JSON output: %s", value)
  return None


def _build_prompt_text(payload: Dict[str, Any]) -> str:
  citation = payload["citation"]
  instructions = [
    "You label how citations support model answers.",
    "Return valid JSON with keys function_tags, stance_tags, provenance_tags.",
    "Always choose from the allowed vocabularies:",
    f"Function tags: {', '.join(FUNCTION_TAGS)}",
    f"Stance tags: {', '.join(STANCE_TAGS)}",
    f"Provenance tags: {', '.join(PROVENANCE_TAGS)}",
    "Do not invent new tag names and omit duplicates.",
  ]
  summary = "\n".join(instructions)
  return f"""{summary}

Prompt: {payload['prompt']}
Model Response: {payload['response_text']}
Claim Span: {payload['claim_span']}
Citation:
  URL: {citation.get('url')}
  Title: {citation.get('title')}
  Domain: {citation.get('domain')}
  Rank: {citation.get('rank')}
  Snippet: {citation.get('snippet')}
  Ref Type: {citation.get('ref_type')}
  Published: {citation.get('published_at')}

Respond with JSON only."""


_SYSTEM_PROMPT = (
  "You are a meticulous analyst who classifies how citations support a model's answer. "
  "Use the function/stance/provenance tag vocabularies to describe each citation. "
  "Always return strict JSON and never include commentary."
)
