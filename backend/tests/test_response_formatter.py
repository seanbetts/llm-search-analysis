"""Tests for backend response formatter."""

from app.services.providers.base_provider import Citation
from app.services.response_formatter import format_response_with_citations


class TestResponseFormatter:
  """Validate citation highlighting logic."""

  def test_bolds_segments_with_offsets(self):
    text = "Valve announced new hardware today."
    citations = [
      Citation(
        url="https://example.com/article",
        title="Example",
        rank=1,
        start_index=0,
        end_index=5,
      )
    ]
    formatted = format_response_with_citations(text, citations)
    assert "**Valve** ([example.com]" in formatted

  def test_uses_snippet_when_offsets_missing(self):
    text = "Steam Frame is slated to ship in 2026."
    citations = [
      Citation(
        url="https://example.com/frame",
        title="Frame",
        rank=1,
        text_snippet="Steam Frame",
      )
    ]
    formatted = format_response_with_citations(text, citations)
    assert "**Steam Frame** ([example.com]" in formatted

  def test_skips_overlapping_segments(self):
    text = "Valve Valve Valve"
    citations = [
      Citation(url="https://a.com", text_snippet="Valve"),
      Citation(url="https://b.com", text_snippet="Valve"),
    ]
    formatted = format_response_with_citations(text, citations)
    assert formatted.count("**Valve**") == 2
