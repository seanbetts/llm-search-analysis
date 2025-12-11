"""Response formatting and display utilities."""

import re
from urllib.parse import urlparse

import streamlit as st

from frontend.utils import format_pub_date


def sanitize_response_markdown(text: str) -> str:
  """Remove heavy dividers and downscale large headings so they don't exceed the section title.

  Args:
    text: Markdown text to sanitize

  Returns:
    Cleaned markdown text
  """
  if not text:
    return ""

  cleaned_lines = []
  divider_pattern = re.compile(r"^\s*[-_*]{3,}\s*$")
  heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

  for line in text.splitlines():
    # Drop markdown horizontal rules
    if divider_pattern.match(line):
      continue

    # Normalize headings: ensure none are larger than level 3
    m = heading_pattern.match(line)
    if m:
      hashes, content = m.groups()
      # Downscale: any heading becomes at most level 4 to stay below section titles
      line = f"#### {content}"
    cleaned_lines.append(line)

  cleaned = "\n".join(cleaned_lines)
  # Remove simple HTML <hr> tags as well
  cleaned = re.sub(r"<\s*hr\s*/?\s*>", "", cleaned, flags=re.IGNORECASE)
  return cleaned.strip()


def format_response_text(text: str, citations: list) -> str:
  """Format response text by converting reference-style citation links to inline links.

  ChatGPT includes markdown reference links at the bottom like:
  [1]: URL "Title"
  [2]: URL "Title"

  And uses them inline like: [Text][1]

  We convert these to inline markdown links: [Text](URL)
  Then remove the reference definitions.

  Args:
    text: Response text with reference-style links
    citations: List of citation objects (not used in current implementation)

  Returns:
    Formatted markdown text with inline links
  """
  if not text:
    return ""

  # Step 1: Extract reference-style link definitions into a mapping
  # Pattern: [N]: URL "Title" or [N]: URL
  # Note: We don't include the optional title part in the pattern because
  # it can cause the regex to match across newlines (since \s+ matches \n)
  reference_pattern = r'^\[(\d+)\]:\s+(https?://\S+)'
  references = {}
  for match in re.finditer(reference_pattern, text, flags=re.MULTILINE):
    ref_num = match.group(1)
    url = match.group(2)
    references[ref_num] = url

  # Step 2: Replace reference-style links with inline links
  # Pattern: [text][N] where N is a number
  def replace_reference_link(match):
    """Convert reference-style markdown links to inline links."""
    link_text = match.group(1)
    ref_num = match.group(2)
    if ref_num in references:
      return f"{link_text} ({_format_domain_link(references[ref_num])})"
    return match.group(0)  # Keep original if reference not found

  text = re.sub(r'\[([^\]]+)\]\[(\d+)\]', replace_reference_link, text)

  # Step 3: Remove the reference definitions from the bottom
  # Use a more specific pattern to match the entire line including optional title
  removal_pattern = r'^\[(\d+)\]:\s+https?://\S+.*$'
  text = re.sub(removal_pattern, '', text, flags=re.MULTILINE)

  # Step 4: Inject citation markers for providers (e.g., Google) that supply segments
  text = _apply_citation_links(text, citations)

  # Step 5: Clean up any resulting multiple newlines
  text = re.sub(r'\n{3,}', '\n\n', text)

  return sanitize_response_markdown(text.strip())


def _format_domain_link(url: str) -> str:
  """Return Markdown hyperlink using the domain as label."""
  try:
    domain = urlparse(url).netloc
  except Exception:
    domain = ""
  label = domain or url
  return f"[{label}]({url})"


def _apply_citation_links(text: str, citations: list) -> str:
  """Insert inline domain links based on citation metadata/snippets."""
  if not citations or not text:
    return text

  def _as_dict(obj):
    if isinstance(obj, dict):
      return obj
    return getattr(obj, "__dict__", None)

  ranked_citations = [c for c in citations if getattr(c, "rank", None) and getattr(c, "url", None)]

  replacements = []
  seen_ranges = set()
  for citation in ranked_citations:
    url = citation.url
    metadata = getattr(citation, "metadata", None)
    if metadata is None:
      raw = _as_dict(citation)
      if raw:
        metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
      continue
    start = metadata.get("segment_start_index")
    end = metadata.get("segment_end_index")
    snippet = (
      metadata.get("snippet")
      or getattr(citation, "text_snippet", None)
      or getattr(citation, "snippet_used", None)
    )
    snippet_match = snippet.strip() if isinstance(snippet, str) else None

    span = None
    if snippet_match:
      idx = text.find(snippet_match)
      if idx != -1:
        span = (idx, idx + len(snippet_match))
    if span is None and isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
      span = (start, end)
    if span is None:
      continue
    span = (int(span[0]), int(span[1]))
    if span in seen_ranges or span[0] == span[1]:
      continue
    seen_ranges.add(span)
    replacements.append((span[0], span[1], url))

  if not replacements:
    return text

  for start, end, url in sorted(replacements, key=lambda item: item[0], reverse=True):
    segment = text[start:end]
    if not segment.strip():
      continue
    domain_link = _format_domain_link(url)
    linked = f"{segment} ({domain_link})"
    text = text[:start] + linked + text[end:]

  return text


def extract_images_from_response(text: str):
  """Extract image URLs from markdown or img tags and return cleaned text.

  Args:
    text: Response text containing images

  Returns:
    Tuple of (cleaned_text, list_of_image_urls)
  """
  if not text:
    return text, []
  images = []

  # Markdown images ![alt](url)
  def md_repl(match):
    """Collect markdown image URLs and strip them from text."""
    url = match.group(1)
    if url:
      images.append(url)
    return ""  # strip from text
  text = re.sub(r"!\[[^\]]*\]\(([^) ]+)[^)]*\)", md_repl, text)

  # HTML img tags
  def html_repl(match):
    """Collect HTML image src values and strip the tags."""
    src = match.group(1)
    if src:
      images.append(src)
    return ""
  text = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html_repl, text, flags=re.IGNORECASE)

  return text.strip(), images


def display_response(response, prompt=None):
  """Display the LLM response with search metadata."""
  # Display prompt if provided
  if prompt:
    st.markdown(f"### 🗣️ *\"{prompt}\"*")

  # Provider display names
  provider_names = {
    'openai': 'OpenAI',
    'google': 'Google',
    'anthropic': 'Anthropic'
  }

  # Response metadata
  col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.5, 2, 1, 1, 1, 1, 1, 1])

  with col1:
    st.metric("Provider", provider_names.get(response.provider.lower(), response.provider))
  with col2:
    # Use backend-provided model_display_name (Phase 1.2)
    model_display = getattr(response, 'model_display_name', None) or response.model
    st.metric("Model", model_display)
  with col3:
    response_time = f"{response.response_time_ms / 1000:.1f}s" if response.response_time_ms else "N/A"
    st.metric("Response Time", response_time)
  with col4:
    st.metric("Search Queries", len(response.search_queries))
  with col5:
    # Use backend-computed sources_found metric
    sources_count = getattr(response, 'sources_found', 0)
    st.metric("Sources Found", sources_count)
  with col6:
    # Use backend-computed sources_used metric
    sources_used = getattr(response, 'sources_used', 0)
    st.metric("Sources Used", sources_used)
  with col7:
    # Use backend-computed avg_rank metric
    avg_rank = getattr(response, 'avg_rank', None)
    if avg_rank is not None:
      st.metric("Avg. Rank", f"{avg_rank:.1f}")
    else:
      st.metric("Avg. Rank", "N/A")
  with col8:
    # Use backend-computed extra_links_count metric
    extra_links = getattr(response, "extra_links_count", 0)
    st.metric("Extra Links", extra_links)

  st.divider()

  # Response text
  response_time_label = response_time if response_time else "N/A"
  st.markdown(f"### 💬 Response ({response_time_label}):")
  formatted_response = format_response_text(response.response_text, response.citations)
  formatted_response, extracted_images = extract_images_from_response(formatted_response)

  if extracted_images:
    # Render images inline with minimal gaps
    img_html = "".join([f'<img src="{url}" style="width:210px;height:135px;object-fit:cover;margin:4px 6px 4px 0;vertical-align:top;"/>' for url in extracted_images])  # noqa: E501
    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;'>{img_html}</div>", unsafe_allow_html=True)  # noqa: E501

  # Render markdown with indented container styling
  # Use newlines around content to ensure markdown processing works inside the div
  st.markdown(
    f'<div class="response-container">\n\n{formatted_response}\n\n</div>',
    unsafe_allow_html=True
  )
  st.divider()

  # Search queries and sources display
  if response.search_queries:
    st.markdown(f"### 🔍 Search Queries ({len(response.search_queries)}):")
    for i, query in enumerate(response.search_queries, 1):
      query_index = getattr(query, "order_index", None)
      label_num = query_index + 1 if query_index is not None else i
      # Display query
      st.markdown(f"""
      <div class="search-query">
          <strong>Query {label_num}:</strong> {query.query}
      </div>
      """, unsafe_allow_html=True)

    st.divider()

  # Display sources - different handling for API vs Network Log
  if getattr(response, 'data_source', 'api') == 'api':
    # API: Sources are associated with queries
    queries_with_sources = [q for q in response.search_queries if q.sources]
    if queries_with_sources:
      total_sources = sum(len(q.sources) for q in queries_with_sources)
      st.markdown(f"### 📚 Sources Found ({total_sources}):")
      for i, query in enumerate(queries_with_sources, 1):
        # Truncate long queries for display
        query_text = query.query if len(query.query) <= 60 else query.query[:60] + "..."
        with st.expander(f"📚 {query_text} ({len(query.sources)} sources)", expanded=False):
          for j, source in enumerate(query.sources, 1):
            url_display = source.url or 'No URL'
            # Use domain as title fallback when title is missing
            display_title = source.title or source.domain or 'Unknown source'
            snippet = getattr(source, "snippet_text", None)
            pub_date = getattr(source, "pub_date", None)
            snippet_display = snippet if snippet else "N/A"
            snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"  # noqa: E501
            pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
            pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"
            domain_link = f'<a href="{url_display}" target="_blank">{source.domain or "Open source"}</a>'
            st.markdown(f"""
            <div class="source-item">
                <strong>{j}. {display_title}</strong><br/>
                <small>{domain_link}</small>
                {snippet_block}
                {pub_date_block}
            </div>
            """, unsafe_allow_html=True)
      st.divider()
  else:
    # Network Log: Sources aren't associated with specific queries
    all_sources = getattr(response, 'all_sources', []) or []
    if all_sources:
      st.markdown(f"### 📚 Sources Found ({len(all_sources)}):")
      st.caption("_Note: Network logs don't provide reliable query-to-source mapping._")
      with st.expander(f"View all {len(all_sources)} sources", expanded=False):
        for j, source in enumerate(all_sources, 1):
          url_display = source.url or 'No URL'
          # Use domain as title fallback when title is missing
          display_title = source.title or source.domain or 'Unknown source'
          snippet = getattr(source, "snippet_text", None)
          pub_date = getattr(source, "pub_date", None)
          snippet_display = snippet if snippet else "N/A"
          snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"  # noqa: E501
          pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
          pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"
          domain_link = f'<a href="{url_display}" target="_blank">{source.domain or "Open source"}</a>'
          st.markdown(f"""
          <div class="source-item">
              <strong>{j}. {display_title}</strong><br/>
              <small>{domain_link}</small>
              {snippet_block}
              {pub_date_block}
          </div>
          """, unsafe_allow_html=True)
      st.divider()

  # Sources used (from web search) - only citations with ranks
  citations_with_rank = [c for c in response.citations if c.rank]
  if citations_with_rank:
    st.markdown(f"### 📝 Sources Used ({len(citations_with_rank)}):")
    st.caption("Sources the model consulted via web search")

    # Build URL -> source lookup for metadata fallback
    # Backend provides all_sources pre-aggregated for both API and network_log modes
    all_sources = getattr(response, 'all_sources', []) or []
    url_to_source = {s.url: s for s in all_sources if getattr(s, "url", None)}

    for i, citation in enumerate(citations_with_rank, 1):
      with st.container():
        url_display = citation.url or 'No URL'
        domain_link = f'<a href="{url_display}" target="_blank">{urlparse(url_display).netloc or url_display}</a>'
        # Extract query info if present in metadata
        query_idx = None
        if getattr(citation, "metadata", None):
          ref_id = citation.metadata.get("ref_id")
          if isinstance(ref_id, dict):
            try:
              query_idx = int(ref_id.get("turn_index", 0)) + 1
            except Exception:
              query_idx = None
          # fallback explicit query index in metadata
          if query_idx is None and citation.metadata.get("query_index") is not None:
            try:
              query_idx = int(citation.metadata.get("query_index")) + 1
            except Exception:
              query_idx = None
        rank_label = citation.rank if citation.rank else None
        # Display rank in parentheses after title
        rank_display = f" (Rank {rank_label})" if rank_label else ""
        # Extract domain from URL for fallback
        domain = urlparse(citation.url).netloc if citation.url else 'Unknown domain'
        display_title = citation.title or domain or 'Unknown source'
        source_fallback = url_to_source.get(citation.url)
        metadata = getattr(citation, "metadata", None) or {}
        snippet = (
          metadata.get("snippet")
          or getattr(citation, "text_snippet", None)
          or getattr(citation, "snippet_used", None)
          or getattr(source_fallback, "snippet_text", None)
        )
        pub_date_val = metadata.get("pub_date") or (getattr(source_fallback, "pub_date", None))
        snippet_display = snippet if snippet else "N/A"
        snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"  # noqa: E501
        pub_date_fmt = format_pub_date(pub_date_val) if pub_date_val else "N/A"
        pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"
        st.markdown(f"""
        <div class="citation-item">
            <strong>{i}. {display_title}{rank_display}</strong><br/>
            {domain_link}
            {snippet_block}
            {pub_date_block}
        </div>
        """, unsafe_allow_html=True)

  # Extra links (citations not from search results)
  extra_links = [c for c in response.citations if not c.rank]
  if extra_links:
    st.divider()
    st.markdown(f"### 🔗 Extra Links ({len(extra_links)}):")
    st.caption("Links mentioned in the response that weren't from search results")

    for i, citation in enumerate(extra_links, 1):
      with st.container():
        url_display = citation.url or 'No URL'
        domain_link = f'<a href="{url_display}" target="_blank">{urlparse(url_display).netloc or url_display}</a>'
        domain = urlparse(citation.url).netloc if citation.url else 'Unknown domain'
        display_title = citation.title or domain or 'Unknown source'

        # Get snippet from metadata if available
        snippet = None
        if getattr(citation, "metadata", None):
          snippet = citation.metadata.get("snippet")
        if not snippet:
          snippet = getattr(citation, "text_snippet", None) or getattr(citation, "snippet_used", None)
        snippet_display = snippet if snippet else "N/A"
        snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"

        st.markdown(f"""
        <div class="citation-item">
            <strong>{i}. {display_title}</strong><br/>
            {domain_link}
            {snippet_block}
        </div>
        """, unsafe_allow_html=True)
