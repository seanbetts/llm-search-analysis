"""Tests for provider raw_response validation schemas."""

import pytest

from app.core.provider_schemas import (
  validate_anthropic_raw_response,
  validate_google_raw_response,
  validate_openai_raw_response,
)
from tests.fixtures import provider_payloads as fixtures


class TestProviderPayloadSchemas:
  """Ensure provider payload validators accept canonical JSON samples."""

  def test_openai_payload_valid(self):
    payload = fixtures.OPENAI_RESPONSE
    sanitized = validate_openai_raw_response(payload)
    assert sanitized["id"] == payload["id"]
    assert len(sanitized["output"]) == 2

  def test_openai_payload_invalid(self):
    with pytest.raises(ValueError):
      validate_openai_raw_response(fixtures.OPENAI_INVALID)

  def test_anthropic_payload_valid(self):
    payload = fixtures.ANTHROPIC_RESPONSE
    sanitized = validate_anthropic_raw_response(payload)
    assert sanitized["id"] == payload["id"]
    assert len(sanitized["content"]) == 3

  def test_anthropic_payload_invalid(self):
    with pytest.raises(ValueError):
      validate_anthropic_raw_response(fixtures.ANTHROPIC_INVALID)

  def test_google_payload_valid(self):
    payload = fixtures.GOOGLE_RESPONSE
    sanitized = validate_google_raw_response(payload)
    assert sanitized["text"] == payload["text"]
    assert len(sanitized["candidates"]) == 1

  def test_google_payload_invalid(self):
    with pytest.raises(ValueError):
      validate_google_raw_response(fixtures.GOOGLE_INVALID)
