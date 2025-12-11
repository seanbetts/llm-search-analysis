"""Utilities for rendering response text with inline citation formatting."""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from app.services.providers.base_provider import Citation


def _format_domain_link(url: str) -> str:
  """Return Markdown hyperlink using the domain as the label."""
  domain = ""
  try:
    domain = urlparse(url or "").netloc
  except Exception:
    domain = ""
  label = domain or url or "source"
  return f"[{label}]({url})" if url else label


def _has_overlap(span: Tuple[int, int], spans: List[Tuple[int, int]]) -> bool:
  return any(not (span[1] <= other[0] or span[0] >= other[1]) for other in spans)


def _find_span(text: str, snippet: str, used_spans: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
  """Case-insensitive search for snippet avoiding overlaps."""
  if not snippet:
    return None
  lower_text = text.lower()
  lower_snip = snippet.lower()
  idx = lower_text.find(lower_snip)
  while idx != -1:
    span = (idx, idx + len(snippet))
    if not _has_overlap(span, used_spans):
      return span
    idx = lower_text.find(lower_snip, idx + 1)
  return None


def format_response_with_citations(text: str, citations: Iterable[Citation]) -> str:
  """Bold cited segments and append (domain.com) links inline.

  Args:
    text: Original response text.
    citations: Iterable of normalized Citation objects.

  Returns:
    Markdown-safe string with bolded cited text and domain links appended.
  """
  if not text or not citations:
    return text or ""

  spans: List[Tuple[int, int, str]] = []
  used_ranges: List[Tuple[int, int]] = []

  for citation in citations:
    if not citation.url:
      continue
    start = citation.start_index
    end = citation.end_index
    span = None
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
      span = (start, end)
    else:
      snippet = citation.text_snippet or citation.snippet_used
      span = _find_span(text, snippet, used_ranges)
    if span is None or _has_overlap(span, used_ranges):
      continue
    used_ranges.append(span)
    spans.append((span[0], span[1], citation.url))

  if not spans:
    return text

  result = text
  for start, end, url in sorted(spans, key=lambda item: item[0], reverse=True):
    segment = result[start:end]
    if not segment.strip():
      continue
    domain_link = _format_domain_link(url)
    replacement = f"**{segment}** ({domain_link})"
    result = result[:start] + replacement + result[end:]

  return result
