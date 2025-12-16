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
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from backend.app.services.providers.base_provider import Citation, ProviderResponse, SearchQuery, Source

_DISCLAIMER_MARKER = "AI responses may include mistakes"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_DATE_RE = re.compile(r"\b(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})\b")


class _MarkdownAndCitationsExtractor(HTMLParser):
  """Extract markdown-like text and citation anchors from folif HTML.

  Google AI Mode embeds the rendered answer as HTML. We want reasonably readable
  markdown for persistence and also need to identify citation links and a best-effort
  snippet (sentence immediately preceding the citation link).
  """

  def __init__(self, *, container_id: str) -> None:
    super().__init__()
    self._container_id = container_id
    self._skip_depth = 0
    self._lines: List[str] = []
    self._current_line: List[str] = []
    self._block_text: List[str] = []

    self._in_li = False
    self._pending_link: Optional[Tuple[str, str]] = None  # (href, anchor_text)
    self._pending_uuid: Optional[str] = None

    self._capture_depth: Optional[int] = None
    self._depth = 0

    # url -> (title, snippet)
    self.citations: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    # uuid -> snippet
    self.uuid_snippets: Dict[str, Optional[str]] = {}

  def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
    """Track when entering a script/style block."""
    if tag in ("script", "style"):
      self._skip_depth += 1
      return
    if self._skip_depth:
      return

    self._depth += 1

    if tag == "div":
      attrs_dict = dict(attrs or [])
      if attrs_dict.get("data-target-container-id") == self._container_id:
        self._capture_depth = self._depth

    if self._capture_depth is None:
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

    if tag == "button":
      attrs_dict = dict(attrs or [])
      uuid = attrs_dict.get("data-icl-uuid")
      if isinstance(uuid, str) and _UUID_RE.match(uuid):
        snippet = _extract_last_sentence("".join(self._block_text))
        self.uuid_snippets[uuid] = snippet
        return

  def handle_endtag(self, tag: str) -> None:
    """Track when leaving a script/style block."""
    if self._capture_depth is not None:
      if self._depth == self._capture_depth and tag == "div":
        self._capture_depth = None
      self._depth = max(0, self._depth - 1)
    else:
      self._depth = max(0, self._depth - 1)

    if tag in ("script", "style") and self._skip_depth:
      self._skip_depth -= 1
      return
    if self._skip_depth:
      return

    if self._capture_depth is None:
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
    if self._capture_depth is None:
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


def _extract_markdown_and_citations(
  html: str,
  *,
  container_id: str,
) -> tuple[str, Dict[str, Tuple[Optional[str], Optional[str]]], Dict[str, Optional[str]]]:
  extractor = _MarkdownAndCitationsExtractor(container_id=container_id)
  extractor.feed(html)
  return extractor.get_markdown(), extractor.citations, extractor.uuid_snippets


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


def _strip_heavy_inline_images(html: str) -> str:
  """Remove large `sn._setImageSrc(...)` script payloads to speed up parsing."""
  if not html:
    return ""
  return re.sub(r"<script[^>]*>\s*sn\._setImageSrc\([^<]*</script>", "", html, flags=re.DOTALL)


def _parse_uuid_source_blocks(folif_html: str) -> Dict[str, dict]:
  r"""Parse Sv6Kpe UUID metadata blocks into a uuid -> metadata dict.

  These blocks look like:
    <!--Sv6Kpe[[\"<uuid>\",[<meta>]]]-->
  """
  if not folif_html:
    return {}

  text = html_lib.unescape(folif_html)
  results: Dict[str, dict] = {}
  for match in re.finditer(r'<!--Sv6Kpe\[\["([0-9a-fA-F-]{36})"', text):
    start = match.start()
    end = text.find("-->", start)
    if end == -1:
      continue
    chunk = text[start + len("<!--Sv6Kpe"): end]
    chunk = chunk[chunk.find("[") :]
    depth = 0
    endpos = None
    for i, ch in enumerate(chunk):
      if ch == "[":
        depth += 1
      elif ch == "]":
        depth -= 1
        if depth == 0:
          endpos = i + 1
          break
    if not endpos:
      continue
    raw = chunk[:endpos]
    try:
      obj = json.loads(raw)
    except Exception:
      continue
    if not isinstance(obj, list) or len(obj) != 1 or not isinstance(obj[0], list) or len(obj[0]) < 2:
      continue
    uuid, meta = obj[0][0], obj[0][1]
    if not isinstance(uuid, str) or not _UUID_RE.match(uuid) or not isinstance(meta, list):
      continue
    results[uuid] = {"uuid": uuid, "meta": meta}
  return results


def _extract_pub_date_from_meta(meta) -> Optional[str]:  # noqa: ANN001
  """Find a date-like string in an arbitrarily nested metadata structure."""
  stack = [meta]
  while stack:
    item = stack.pop()
    if isinstance(item, str):
      m = _DATE_RE.search(item)
      if m:
        return m.group(1)
    elif isinstance(item, list):
      stack.extend(item)
  return None


class _SidebarSourcesExtractor(HTMLParser):
  """Extract source cards from the sidebar container (data-target-container-id=13)."""

  def __init__(self) -> None:
    super().__init__()
    self._skip_depth = 0
    self._depth = 0
    self._capture_depth: Optional[int] = None
    self._current: Optional[dict] = None
    self._current_text: List[str] = []
    self.items: List[dict] = []

  def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
    if tag in ("script", "style"):
      self._skip_depth += 1
      return
    if self._skip_depth:
      return
    self._depth += 1

    if tag == "div":
      attrs_dict = dict(attrs or [])
      if attrs_dict.get("data-target-container-id") == "13":
        self._capture_depth = self._depth
      return

    if self._capture_depth is None:
      return

    if tag == "a":
      attrs_dict = dict(attrs or [])
      href = attrs_dict.get("href")
      title = attrs_dict.get("aria-label") or None
      normalized = _normalize_outgoing_url(href) if isinstance(href, str) else None
      if normalized:
        self._flush_current()
        self._current = {"url": normalized, "title": title}
        self._current_text = []

  def handle_endtag(self, tag: str) -> None:
    if tag in ("script", "style") and self._skip_depth:
      self._skip_depth -= 1
      return
    if self._skip_depth:
      return

    if self._capture_depth is not None and self._depth == self._capture_depth and tag == "div":
      self._flush_current()
      self._capture_depth = None

    self._depth = max(0, self._depth - 1)

  def handle_data(self, data: str) -> None:
    if self._skip_depth or self._capture_depth is None:
      return
    text = (data or "").strip()
    if not text:
      return
    if self._current is not None:
      self._current_text.append(text)

  def _flush_current(self) -> None:
    if not self._current:
      return
    blob = " ".join(self._current_text)
    blob = re.sub(r"\s+", " ", blob).strip()
    pub_date = None
    m = _DATE_RE.search(blob)
    if m:
      pub_date = m.group(1)
    # Description: remove any date strings.
    description = _DATE_RE.sub("", blob).strip() or None
    self._current["pub_date"] = pub_date
    self._current["description"] = description
    self.items.append(self._current)
    self._current = None
    self._current_text = []


def extract_sidebar_sources_from_folif_html(folif_html: str) -> List[Source]:
  """Extract sidebar source cards (titles, urls, dates, descriptions)."""
  if not folif_html:
    return []
  html_text = _strip_heavy_inline_images(html_lib.unescape(folif_html))
  parser = _SidebarSourcesExtractor()
  parser.feed(html_text)

  sources: List[Source] = []
  seen = set()
  for idx, item in enumerate(parser.items, start=1):
    url = item.get("url")
    if not isinstance(url, str) or not url:
      continue
    if url in seen:
      continue
    seen.add(url)
    sources.append(
      Source(
        url=url,
        title=item.get("title") if isinstance(item.get("title"), str) else None,
        domain=_domain_for_url(url),
        rank=idx,
        pub_date=item.get("pub_date"),
        search_description=item.get("description"),
        internal_score=None,
        metadata={"source_extraction": "sidebar_container_13"},
      )
    )
  return sources


def _is_google_footer_link(url: str) -> bool:
  try:
    parsed = urlparse(url)
  except Exception:
    return False
  domain = (parsed.netloc or "").lower()
  path = (parsed.path or "").lower()
  if domain.endswith("google.com") and (
    path.startswith("/policies/") or path.startswith("/support/") or path.startswith("/intl/")
  ):
    return True
  if domain.endswith("support.google.com") or domain.endswith("policies.google.com"):
    return True
  return False

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
  unescaped = _strip_heavy_inline_images(unescaped)

  # Extract primary response text + in-response citations from the main answer container.
  markdown_text, anchor_citations, uuid_snippets = _extract_markdown_and_citations(unescaped, container_id="5")

  response_text = (response_text_override or "").strip() or markdown_text
  if _DISCLAIMER_MARKER in response_text:
    response_text = response_text.split(_DISCLAIMER_MARKER, 1)[0].strip()

  # Sources Found: sidebar cards. Only populate when we believe a search occurred.
  has_search = bool(search_queries)
  normalized_sources: List[Source] = extract_sidebar_sources_from_folif_html(unescaped) if has_search else []
  sources_by_url: Dict[str, Source] = {s.url: s for s in normalized_sources if s.url}

  uuid_blocks = _parse_uuid_source_blocks(unescaped)
  uuid_to_url: Dict[str, str] = {}
  uuid_to_title: Dict[str, Optional[str]] = {}
  uuid_to_pub_date: Dict[str, Optional[str]] = {}
  uuid_to_description: Dict[str, Optional[str]] = {}
  for uuid, payload in uuid_blocks.items():
    meta = payload.get("meta") or []
    if not isinstance(meta, list) or len(meta) < 6:
      continue
    title = meta[0] if isinstance(meta[0], str) else None
    description = meta[1] if isinstance(meta[1], str) else None
    url = meta[5] if isinstance(meta[5], str) else None
    normalized_url = _normalize_outgoing_url(url) if isinstance(url, str) else None
    if normalized_url:
      uuid_to_url[uuid] = normalized_url
      uuid_to_title[uuid] = title
      uuid_to_description[uuid] = description
      uuid_to_pub_date[uuid] = _extract_pub_date_from_meta(meta)

  citations: List[Citation] = []
  seen_urls = set()

  # UUID citations in the response (primary signal for "Sources Used").
  for uuid, snippet in uuid_snippets.items():
    url = uuid_to_url.get(uuid)
    if not url or url in seen_urls or _is_google_footer_link(url):
      continue
    seen_urls.add(url)
    rank = None
    if has_search:
      match = sources_by_url.get(url)
      if match and isinstance(match.rank, int):
        rank = match.rank
    citations.append(
      Citation(
        url=url,
        title=uuid_to_title.get(uuid),
        rank=rank,
        snippet_cited=snippet,
        published_at=uuid_to_pub_date.get(uuid),
        metadata={"icl_uuid": uuid, "description": uuid_to_description.get(uuid)},
      )
    )

  # Anchor links in the response (extra links or used sources when matching sidebar).
  for url, (title, snippet) in anchor_citations.items():
    if not url or url in seen_urls or _is_google_footer_link(url):
      continue
    seen_urls.add(url)
    rank = None
    if has_search:
      match = sources_by_url.get(url)
      if match and isinstance(match.rank, int):
        rank = match.rank
    citations.append(Citation(url=url, title=title, rank=rank, snippet_cited=snippet))

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
