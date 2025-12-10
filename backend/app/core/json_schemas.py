"""Typed helpers for validating nested JSON blobs before persistence."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RefId(BaseModel):
  """Reference identifier attached to network-log sources."""
  model_config = ConfigDict(extra="forbid")

  turn_index: Optional[int] = Field(default=None, ge=0)
  ref_type: Optional[str] = None
  ref_index: Optional[int] = Field(default=None, ge=0)


class SourceMetadata(BaseModel):
  """Structured metadata persisted for sources.

  Allows provider/network-log specific keys but enforces known primitives.
  """
  model_config = ConfigDict(extra="allow")

  ref_id: Optional[RefId] = None
  attribution: Optional[str] = None
  is_safe: Optional[bool] = None
  provider: Optional[str] = None
  confidence: Optional[float] = None


class CitationMetadata(BaseModel):
  """Structured metadata persisted for citations."""
  model_config = ConfigDict(extra="allow")

  citation_id: Optional[str] = None
  provider: Optional[str] = None
  confidence: Optional[float] = None


def dump_metadata(model_cls: type[BaseModel], payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
  """Validate and dump metadata dictionaries.

  Args:
    model_cls: Pydantic model class to use for validation.
    payload: Raw dict payload.

  Returns:
    Normalized dict or None.

  Raises:
    ValueError: If validation fails.
  """
  if payload is None:
    return None
  try:
    return model_cls.model_validate(payload).model_dump(exclude_none=True)
  except Exception as exc:
    raise ValueError(f"Invalid metadata payload: {exc}") from exc
