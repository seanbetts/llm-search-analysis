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
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from backend.app.services.providers.base_provider import Citation, ProviderResponse, SearchQuery, Source

_DISCLAIMER_MARKER = "AI responses may include mistakes"


class _MarkdownAndCitationsExtractor(HTMLParser):
  """Extract markdown-like text and citation anchors from folif HTML.

  Google AI Mode embeds the rendered answer as HTML. We want reasonably readable
  markdown for persistence and also need to identify citation links and a best-effort
  snippet (sentence immediately preceding the citation link).
  """

  def __init__(self) -> None:
    super().__init__()
    self._skip_depth = 0
    self._lines: List[str] = []
    self._current_line: List[str] = []
    self._block_text: List[str] = []

    self._in_li = False
    self._pending_link: Optional[Tuple[str, str]] = None  # (href, anchor_text)

    # url -> (title, snippet)
    self.citations: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

  def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
    """Track when entering a script/style block."""
    if tag in ("script", "style"):
      self._skip_depth += 1
      return
    if self._skip_depth:
      return

    if tag == "br":
      self._flush_line()
      return

    if tag in ("p", "div", "section", "article"):
      self._flush_line()
      self._flush_block()
      self._ensure_blank_line()
      return

    if tag in ("ul", "ol"):
      self._flush_line()
      self._flush_block()
      self._ensure_blank_line()
      return

    if tag == "li":
      self._flush_line()
      self._flush_block()
      self._in_li = True
      self._current_line.append("- ")
      return

    if tag == "a":
      href = None
      for key, value in attrs or []:
        if key == "href":
          href = value
          break
      if href:
        self._pending_link = (href, "")
      return

  def handle_endtag(self, tag: str) -> None:
    """Track when leaving a script/style block."""
    if tag in ("script", "style") and self._skip_depth:
      self._skip_depth -= 1
      return
    if self._skip_depth:
      return

    if tag == "a" and self._pending_link:
      href, anchor_text = self._pending_link
      self._pending_link = None
      normalized = _normalize_outgoing_url(href)
      if normalized:
        snippet = _extract_last_sentence("".join(self._block_text))
        title = anchor_text.strip() or None
        self.citations.setdefault(normalized, (title, snippet))
        # Render as a markdown link when possible.
        if title:
          self._current_line.append(f"[{title}]({normalized})")
        else:
          self._current_line.append(normalized)
      return

    if tag == "li":
      self._in_li = False
      self._flush_line()
      self._flush_block()
      self._ensure_blank_line()
      return

    if tag in ("p", "div", "section", "article"):
      self._flush_line()
      self._flush_block()
      self._ensure_blank_line()
      return

  def handle_data(self, data: str) -> None:
    """Collect visible text nodes."""
    if self._skip_depth:
      return
    if data and data.strip():
      text = data.strip()
      if not text:
        return
      if self._pending_link:
        href, anchor_text = self._pending_link
        self._pending_link = (href, anchor_text + text)
      else:
        # Accumulate raw block text for snippet extraction (sentence preceding a link).
        self._block_text.append(text + " ")
        self._current_line.append(text)

  def _flush_line(self) -> None:
    line = " ".join(part for part in self._current_line if part).strip()
    self._current_line = []
    if not line:
      return
    line = re.sub(r"\s+", " ", line).strip()
    self._lines.append(line)

  def _flush_block(self) -> None:
    block = "".join(self._block_text).strip()
    self._block_text = []
    if not block:
      return

  def _ensure_blank_line(self) -> None:
    if not self._lines:
      return
    if self._lines[-1] != "":
      self._lines.append("")

  def get_markdown(self) -> str:
    """Return extracted markdown text with light cleanup."""
    self._flush_line()
    markdown = "\n".join(self._lines)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    return markdown


def _extract_markdown_and_citations(html: str) -> tuple[str, Dict[str, Tuple[Optional[str], Optional[str]]]]:
  extractor = _MarkdownAndCitationsExtractor()
  extractor.feed(html)
  return extractor.get_markdown(), extractor.citations


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


def _normalize_outgoing_url(url: str) -> Optional[str]:
  """Normalize Google redirect/tracking URLs to a stable destination URL."""
  if not url or not isinstance(url, str):
    return None

  url = html_lib.unescape(url.strip())
  if url.startswith("//"):
    url = "https:" + url

  # Handle google redirect URLs like https://www.google.com/url?q=DEST&...
  try:
    parsed = urlparse(url)
    if parsed.netloc.endswith("google.com") and parsed.path == "/url":
      qs = parse_qs(parsed.query or "")
      target = qs.get("q", [None])[0]
      if isinstance(target, str) and target.startswith("http"):
        url = unquote(target)
        parsed = urlparse(url)
  except Exception:
    pass

  try:
    parsed = urlparse(url)
  except Exception:
    return None

  if not parsed.scheme.startswith("http"):
    return None
  if _is_noise_url(url):
    return None

  # Strip common tracking query params.
  qs = parse_qs(parsed.query or "")
  keep: Dict[str, List[str]] = {}
  for key, values in qs.items():
    if key.lower().startswith("utm_"):
      continue
    if key in {"ved", "usg", "opi", "sa", "ei"}:
      continue
    keep[key] = values
  query = "&".join([f"{k}={v[0]}" for k, v in keep.items() if v])
  cleaned = parsed._replace(query=query, fragment="")
  return urlunparse(cleaned)


def _extract_last_sentence(text: str) -> Optional[str]:
  """Return the last sentence-like chunk from text for snippet attribution."""
  if not text:
    return None
  cleaned = re.sub(r"\s+", " ", text).strip()
  if not cleaned:
    return None
  # Prefer the last sentence ending in punctuation.
  sentences = re.findall(r"[^.!?]{10,}[.!?]", cleaned)
  if sentences:
    return sentences[-1].strip()
  # Fallback: last ~200 chars.
  return cleaned[-200:].strip()


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
  search_queries: Optional[Sequence[SearchQuery]] = None,
  response_text_override: Optional[str] = None,
) -> ProviderResponse:
  """Parse a Google AI Mode folif HTML payload into a ProviderResponse."""
  unescaped = html_lib.unescape(folif_html or "")
  markdown_text, citation_map = _extract_markdown_and_citations(unescaped)

  response_text = (response_text_override or "").strip() or markdown_text
  if _DISCLAIMER_MARKER in response_text:
    response_text = response_text.split(_DISCLAIMER_MARKER, 1)[0].strip()

  # AI Mode often appends a "N sites" sources block; keep it out of response text.
  lines = [line.rstrip() for line in response_text.splitlines()]
  for idx, line in enumerate(lines):
    if re.match(r"^\d+\s+sites\b", line.strip(), flags=re.IGNORECASE):
      lines = lines[:idx]
      break
  response_text = "\n".join([line for line in lines if line.strip()]).strip()

  extracted_sources = extract_sources_from_folif_html(folif_html)
  normalized_sources: List[Source] = []
  sources_by_url: Dict[str, Source] = {}

  has_search = bool(search_queries)
  if has_search:
    for idx, src in enumerate(extracted_sources, start=1):
      normalized_url = _normalize_outgoing_url(src.url) or src.url
      domain = _domain_for_url(normalized_url)
      source = Source(
        url=normalized_url,
        title=src.title or None,
        domain=domain,
        rank=idx,
        pub_date=None,
        search_description=None,
        internal_score=None,
        metadata={"source_extraction": "folif_html"},
      )
      normalized_sources.append(source)
      sources_by_url[normalized_url] = source

  citations: List[Citation] = []
  seen_citation_urls = set()
  for url, (title, snippet) in citation_map.items():
    if url in seen_citation_urls:
      continue
    seen_citation_urls.add(url)
    rank = None
    if has_search:
      match = sources_by_url.get(url)
      if match and isinstance(match.rank, int):
        rank = match.rank
    citations.append(
      Citation(
        url=url,
        title=title,
        rank=rank,
        snippet_cited=snippet,
      )
    )

  return ProviderResponse(
    response_text=response_text,
    search_queries=list(search_queries or []),
    sources=normalized_sources,
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
