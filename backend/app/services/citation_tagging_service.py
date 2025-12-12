"""LLM-based citation tagging service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from google.genai import Client as GoogleClient
from google.genai.types import GenerateContentConfig
from openai import OpenAI
from pydantic import BaseModel, Field

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
  "official",
  "news",
  "reference",
  "review",
  "community",
  "academic",
  "documentation",
  "blog",
  "legal_or_policy",
]

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "citation_tagging_prompt.md"
PROMPT_TEMPLATE = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
INFLUENCE_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "citation_influence_prompt.md"
INFLUENCE_PROMPT_TEMPLATE = INFLUENCE_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
STRUCTURED_RESPONSE_SCHEMA = {
  "type": "object",
  "additionalProperties": False,
  "properties": {
    "function_tags": {
      "type": "array",
      "items": {"type": "string", "enum": FUNCTION_TAGS},
    },
    "stance_tags": {
      "type": "array",
      "items": {"type": "string", "enum": STANCE_TAGS},
    },
    "provenance_tags": {
      "type": "array",
      "items": {"type": "string", "enum": PROVENANCE_TAGS},
    },
  },
  "required": ["function_tags", "stance_tags", "provenance_tags"],
}

def _strip_additional_properties(value: Any) -> Any:
  if isinstance(value, dict):
    return {
      key: _strip_additional_properties(subvalue)
      for key, subvalue in value.items()
      if key != "additionalProperties"
    }
  if isinstance(value, list):
    return [_strip_additional_properties(item) for item in value]
  return value

GOOGLE_RESPONSE_SCHEMA = _strip_additional_properties(STRUCTURED_RESPONSE_SCHEMA)
INFLUENCE_RESPONSE_SCHEMA = {
  "type": "object",
  "properties": {
    "summary": {"type": "string"},
  },
  "required": ["summary"],
}


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

  def __init__(self) -> None:
    self.last_usage: Optional[Dict[str, Any]] = None

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Return raw JSON dict for the provided prompt."""
    raise NotImplementedError


class NullLLMTagger(BaseLLMTagger):
  """Fallback implementation that always returns empty tags."""

  def __init__(self) -> None:
    super().__init__()

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Return empty tag arrays."""
    return {"function_tags": [], "stance_tags": [], "provenance_tags": []}


class OpenAILLMTagger(BaseLLMTagger):
  """LLM tagger that uses the OpenAI Responses API."""

  class _CitationTagsModel(BaseModel):
    """Structured schema for OpenAI responses."""

    function_tags: List[FunctionTagLiteral] = Field(default_factory=list)
    stance_tags: List[StanceTagLiteral] = Field(default_factory=list)
    provenance_tags: List[ProvenanceTagLiteral] = Field(default_factory=list)

    class Config:
      extra = "forbid"

  def __init__(self, api_key: str, model: str, temperature: float):
    super().__init__()
    self.client = OpenAI(api_key=api_key)
    self.model = model
    self.temperature = temperature

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Call the OpenAI Responses API and parse JSON output."""
    completion = self.client.responses.parse(  # type: ignore[arg-type]
      model=self.model,
      temperature=self.temperature,
      input=[
        {
          "role": "system",
          "content": _SYSTEM_PROMPT,
        },
        {
          "role": "user",
          "content": prompt,
        },
      ],
      text_format=self._CitationTagsModel,
    )
    usage = getattr(completion, "usage", None)
    if usage:
      usage_dict = getattr(usage, "model_dump", None)
      self.last_usage = usage_dict() if callable(usage_dict) else getattr(usage, "__dict__", usage)
    else:
      self.last_usage = None
    parsed = getattr(completion, "output_parsed", None)
    return parsed.model_dump() if parsed else None


class GoogleLLMTagger(BaseLLMTagger):
  """LLM tagger that uses Google Gemini via the google-genai SDK."""

  def __init__(self, api_key: str, model: str, temperature: float):
    super().__init__()
    self.client = GoogleClient(api_key=api_key)
    self.model = model
    self.temperature = temperature

  def generate(self, prompt: str) -> Optional[Dict[str, Any]]:
    """Call Google Gemini and parse JSON output."""
    config = GenerateContentConfig(
      temperature=self.temperature,
      response_mime_type="application/json",
      response_schema=GOOGLE_RESPONSE_SCHEMA,
    )
    response = self.client.models.generate_content(
      model=self.model,
      contents=prompt,
      config=config,
    )
    usage = getattr(response, "usage_metadata", None)
    if usage:
      prompt_tokens = getattr(usage, "prompt_token_count", None)
      candidate_tokens = getattr(usage, "candidates_token_count", None)
      total_tokens = getattr(usage, "total_token_count", None)
      self.last_usage = {
        "input_tokens": prompt_tokens,
        "output_tokens": candidate_tokens,
        "total_tokens": total_tokens,
      }
    else:
      self.last_usage = None
    text_output = getattr(response, "text", None) or getattr(response, "output_text", None)
    if isinstance(text_output, list):
      text_output = text_output[0]
    return _safe_load_json(text_output or "")


class BaseLLMSummarizer:
  """Abstract base for influence summarizers."""

  def summarize(self, prompt: str) -> str:
    raise NotImplementedError


class NullLLMSummarizer(BaseLLMSummarizer):
  """Fallback summarizer that returns empty summaries."""

  def summarize(self, prompt: str) -> str:
    return ""


class OpenAIInfluenceSummarizer(BaseLLMSummarizer):
  """OpenAI-backed influence summarizer."""

  class _SummaryModel(BaseModel):
    summary: str = Field(default="")

    class Config:
      extra = "forbid"

  def __init__(self, api_key: str, model: str, temperature: float):
    self.client = OpenAI(api_key=api_key)
    self.model = model
    self.temperature = temperature

  def summarize(self, prompt: str) -> str:
    completion = self.client.responses.parse(  # type: ignore[arg-type]
      model=self.model,
      temperature=self.temperature,
      input=[
        {"role": "system", "content": "You produce concise single-sentence summaries."},
        {"role": "user", "content": prompt},
      ],
      text_format=self._SummaryModel,
    )
    parsed = getattr(completion, "output_parsed", None)
    if parsed and parsed.summary:
      return parsed.summary.strip()
    text = completion.output_text[0] if completion.output_text else ""
    return text.strip()


class GoogleInfluenceSummarizer(BaseLLMSummarizer):
  """Google-backed influence summarizer."""

  def __init__(self, api_key: str, model: str, temperature: float):
    self.client = GoogleClient(api_key=api_key)
    self.model = model
    self.temperature = temperature

  def summarize(self, prompt: str) -> str:
    config = GenerateContentConfig(
      temperature=self.temperature,
      response_mime_type="application/json",
      response_schema=INFLUENCE_RESPONSE_SCHEMA,
    )
    response = self.client.models.generate_content(
      model=self.model,
      contents=prompt,
      config=config,
    )
    text_output = getattr(response, "text", None) or getattr(response, "output_text", None)
    if isinstance(text_output, list):
      text_output = text_output[0]
    data = _safe_load_json(text_output or "")
    if isinstance(data, dict):
      summary = data.get("summary")
      if isinstance(summary, str):
        return summary.strip()
    return (text_output or "").strip()


class CitationTaggingService:
  """High-level service that orchestrates citation tagging."""

  def __init__(self, config: CitationTaggingConfig):
    self.config = config
    self._tagger = self._build_tagger(config)
    self._last_usage_records: List[Dict[str, Any]] = []

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
    self._last_usage_records = []
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
      usage_record = getattr(self._tagger, "last_usage", None)
      if isinstance(usage_record, dict):
        self._last_usage_records.append(usage_record)
      else:
        self._last_usage_records.append({})

    return citations


  def get_last_usage_records(self) -> List[Dict[str, Any]]:
    """Return usage metadata collected during the previous annotate call."""
    return list(self._last_usage_records)

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
    if not claim_span:
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
        "snippet": (
          citation.get("snippet_cited")
          or citation.get("snippet_used")
          or citation.get("text_snippet")
          or ""
        ),
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
    provenance_tags = _filter(raw.get("provenance_tags"), PROVENANCE_TAGS)
    if not provenance_tags:
      provenance_tags = self._default_provenance(citation)

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
  """Return the precise claim span using start/end indices if available."""
  start = citation.get("start_index")
  end = citation.get("end_index")
  if isinstance(start, int) and isinstance(end, int):
    if 0 <= start < end <= len(response_text):
      return response_text[start:end]
  snippet = (
    (citation.get("snippet_cited") or "")
    or (citation.get("snippet_used") or "")
    or (citation.get("text_snippet") or "")
  ).strip()
  if snippet:
    idx = (response_text or "").find(snippet)
    if idx != -1:
      return response_text[idx : idx + len(snippet)]
    return snippet
  return ""


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
  return PROMPT_TEMPLATE.format(
    prompt=payload["prompt"],
    response_text=payload["response_text"],
    claim_span=payload["claim_span"],
    citation_url=citation.get("url", ""),
    citation_title=citation.get("title", ""),
    citation_domain=citation.get("domain", ""),
    citation_rank=citation.get("rank", ""),
    citation_snippet=citation.get("snippet", ""),
    citation_ref_type=citation.get("ref_type", ""),
    citation_published_at=citation.get("published_at", ""),
  )


def _build_influence_prompt(payload: Dict[str, Any]) -> str:
  citation = payload["citation"]
  return INFLUENCE_PROMPT_TEMPLATE.format(
    prompt=payload["prompt"],
    response_text=payload["response_text"],
    claim_span=payload["claim_span"],
    citation_url=citation.get("url", ""),
    citation_title=citation.get("title", ""),
    citation_domain=citation.get("domain", ""),
    citation_rank=citation.get("rank", ""),
    citation_snippet=citation.get("snippet", ""),
    citation_ref_type=citation.get("ref_type", ""),
    citation_published_at=citation.get("published_at", ""),
    function_tags=payload.get("function_tags", ""),
    stance_tags=payload.get("stance_tags", ""),
    provenance_tags=payload.get("provenance_tags", ""),
  )


class CitationInfluenceService:
  """Generates short influence summaries for citations."""

  def __init__(self, config: CitationTaggingConfig):
    self.config = config
    self._summarizer = self._build_summarizer(config)

  def _build_summarizer(self, config: CitationTaggingConfig) -> BaseLLMSummarizer:
    if not config.enabled:
      return NullLLMSummarizer()
    provider = (config.provider or "").lower()
    if provider == "openai":
      if not config.openai_api_key:
        return NullLLMSummarizer()
      return OpenAIInfluenceSummarizer(config.openai_api_key, config.model, config.temperature)
    if provider == "google":
      if not config.google_api_key:
        return NullLLMSummarizer()
      return GoogleInfluenceSummarizer(config.google_api_key, config.model, config.temperature)
    return NullLLMSummarizer()

  def annotate_influence(
    self,
    prompt: str,
    response_text: str,
    citations: List[dict],
  ) -> List[dict]:
    if not citations:
      return citations
    for citation in citations:
      payload = self._build_payload(prompt, response_text, citation)
      if not payload:
        citation["influence_summary"] = ""
        continue
      prompt_str = _build_influence_prompt(payload)
      try:
        summary = self._summarizer.summarize(prompt_str)
      except Exception:
        logger.exception("Influence summarization failed; defaulting to empty summary")
        summary = ""
      citation["influence_summary"] = summary
    return citations

  def _build_payload(
    self,
    prompt: str,
    response_text: str,
    citation: Dict[str, Any],
  ) -> Optional[Dict[str, Any]]:
    claim_span = _extract_claim_span(response_text or "", citation)
    if not claim_span:
      return None
    metadata = citation.get("metadata") or {}
    ref_info = metadata.get("ref_id") or {}
    function_tags = citation.get("function_tags") or []
    stance_tags = citation.get("stance_tags") or []
    provenance_tags = citation.get("provenance_tags") or []
    return {
      "prompt": prompt or "",
      "response_text": response_text or "",
      "claim_span": claim_span,
      "citation": {
        "url": citation.get("url"),
        "title": citation.get("title"),
        "rank": citation.get("rank"),
        "snippet": (
          citation.get("snippet_cited")
          or citation.get("snippet_used")
          or citation.get("text_snippet")
          or ""
        ),
        "domain": citation.get("domain"),
        "ref_type": ref_info.get("ref_type"),
        "published_at": metadata.get("published_at"),
      },
      "function_tags": ", ".join(function_tags),
      "stance_tags": ", ".join(stance_tags),
      "provenance_tags": ", ".join(provenance_tags),
    }


_SYSTEM_PROMPT = (
  "You are a meticulous analyst who classifies how citations support a model's answer. "
  "Use the defined function/stance vocabularies to describe each citation. "
  "Always return structured JSON that matches the provided schema."
)
FunctionTagLiteral = Literal[
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
StanceTagLiteral = Literal["supports", "refutes", "nuances_or_qualifies", "neutral_context"]
ProvenanceTagLiteral = Literal[
  "official",
  "news",
  "reference",
  "review",
  "community",
  "academic",
  "documentation",
  "blog",
  "legal_or_policy",
]
