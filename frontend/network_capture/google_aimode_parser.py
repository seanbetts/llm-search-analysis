"""Parser for Google AI Mode web capture responses.

Google AI Mode (https://www.google.com/aimode) returns a large HTML payload via
`/async/folif`. That payload contains:
  - the rendered answer text (in non-script/style HTML text nodes)
  - embedded source title/URL metadata (in serialized arrays inside comments/attrs)

This module extracts a normalized ProviderResponse compatible with the existing
web-capture persistence contract (`/api/v1/interactions/save-network-log`).
"""

from __future__ import annotations

import base64
import html as html_lib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Optional, Sequence
from urllib.parse import urlparse

from backend.app.services.providers.base_provider import Citation, ProviderResponse, Source

_DISCLAIMER_MARKER = "AI responses may include mistakes"


class _VisibleTextExtractor(HTMLParser):
  """Extract visible text while ignoring script/style blocks."""

  def __init__(self) -> None:
    super().__init__()
    self._skip_depth = 0
    self.parts: List[str] = []

  def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
    """Track when entering a script/style block."""
    if tag in ("script", "style"):
      self._skip_depth += 1

  def handle_endtag(self, tag: str) -> None:
    """Track when leaving a script/style block."""
    if tag in ("script", "style") and self._skip_depth:
      self._skip_depth -= 1

  def handle_data(self, data: str) -> None:
    """Collect visible text nodes."""
    if self._skip_depth:
      return
    if data and data.strip():
      self.parts.append(data.strip())


def _extract_visible_text(html: str) -> str:
  extractor = _VisibleTextExtractor()
  extractor.feed(html)
  text = " ".join(extractor.parts)
  text = re.sub(r"\\s+", " ", text).strip()
  return text


def _decode_js_escapes(value: str) -> str:
  r"""Decode JavaScript-style \uXXXX escapes embedded in HTML payloads."""
  try:
    return value.encode("utf-8").decode("unicode_escape")
  except Exception:
    return value


def _domain_for_url(url: str) -> Optional[str]:
  try:
    domain = urlparse(url).netloc.lower()
  except Exception:
    return None
  return domain or None


def _is_noise_url(url: str) -> bool:
  lowered = url.lower()
  if "faviconv2" in lowered or "encrypted-tbn" in lowered:
    return True
  domain = _domain_for_url(url) or ""
  if domain.endswith("gstatic.com"):
    return True
  return False


@dataclass(frozen=True, slots=True)
class ExtractedSource:
  """Lightweight extracted source data before normalization."""

  title: str
  url: str


_TITLE_URL_PATTERN = re.compile(
  r'\[\s*"(?P<title>[^"\\]{5,200})"(?P<tail>.{0,800}?)"(?P<url>https?://[^"\\\s]+)"',
  flags=re.DOTALL,
)


def extract_sources_from_folif_html(folif_html: str) -> List[ExtractedSource]:
  """Extract source title/URL pairs from a folif HTML payload."""
  if not folif_html:
    return []

  text = html_lib.unescape(folif_html)
  results: List[ExtractedSource] = []

  for match in _TITLE_URL_PATTERN.finditer(text):
    title = match.group("title").strip()
    urls = []
    urls.append(match.group("url"))
    urls.extend(re.findall(r'"(https?://[^"]+)"', match.group("tail"))[:8])
    urls = [_decode_js_escapes(u) for u in urls]

    chosen = None
    for url in urls:
      if _is_noise_url(url):
        continue
      chosen = url
      break
    if not chosen:
      continue

    results.append(ExtractedSource(title=title, url=chosen))

  # De-dup by URL while preserving first-seen order.
  seen = set()
  deduped: List[ExtractedSource] = []
  for src in results:
    key = src.url
    if key in seen:
      continue
    seen.add(key)
    deduped.append(src)
  return deduped


def parse_google_aimode_folif_html(
  folif_html: str,
  *,
  model: str = "google-aimode",
  provider: str = "google",
  response_time_ms: int = 0,
) -> ProviderResponse:
  """Parse a Google AI Mode folif HTML payload into a ProviderResponse."""
  visible_text = _extract_visible_text(html_lib.unescape(folif_html))
  if _DISCLAIMER_MARKER in visible_text:
    visible_text = visible_text.split(_DISCLAIMER_MARKER, 1)[0].strip()

  extracted_sources = extract_sources_from_folif_html(folif_html)
  sources: List[Source] = []
  citations: List[Citation] = []

  for idx, src in enumerate(extracted_sources, start=1):
    domain = _domain_for_url(src.url)
    sources.append(
      Source(
        url=src.url,
        title=src.title or None,
        domain=domain,
        rank=idx,
        pub_date=None,
        search_description=None,
        internal_score=None,
        metadata={"source_extraction": "folif_html"},
      )
    )
    citations.append(Citation(url=src.url, title=src.title or None, rank=idx))

  return ProviderResponse(
    response_text=visible_text,
    search_queries=[],
    sources=sources,
    citations=citations,
    raw_response={"capture": "google_aimode_folif"},
    model=model,
    provider=provider,
    response_time_ms=response_time_ms,
    data_source="web",
  )


def folif_html_from_browser_capture(body: Optional[str], body_bytes: Optional[bytes] = None) -> str:
  """Return HTML content from a captured response body.

  Args:
    body: UTF-8 decoded body text, if available.
    body_bytes: Raw bytes body, if available.
  """
  if isinstance(body, str) and body:
    return body
  if isinstance(body_bytes, (bytes, bytearray)) and body_bytes:
    try:
      return bytes(body_bytes).decode("utf-8", errors="replace")
    except Exception:
      return ""
  return ""


def folif_html_from_har_content_text(text: str, encoding: Optional[str]) -> str:
  """Decode HAR `response.content.text` into HTML."""
  if not text:
    return ""
  if encoding == "base64":
    try:
      return base64.b64decode(text).decode("utf-8", errors="replace")
    except Exception:
      return ""
  return text


def choose_latest_folif_response(responses: Sequence[dict]) -> Optional[str]:
  """Pick the latest /async/folif response body from captured responses."""
  candidates = [r for r in responses if isinstance(r, dict) and "/async/folif" in (r.get("url") or "")]
  if not candidates:
    return None
  # Prefer the largest body as it typically contains the full answer.
  candidates.sort(key=lambda r: int(r.get("body_size") or 0), reverse=True)
  return candidates[0].get("body")
