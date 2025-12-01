"""
LLM Search Analysis - Streamlit UI

Interactive web interface for testing and analyzing LLM search capabilities
across OpenAI, Google Gemini, and Anthropic Claude models.
"""

import re
import streamlit as st
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse
from src.config import Config
from src.providers.provider_factory import ProviderFactory
from src.database import Database

# Page config
st.set_page_config(
    page_title="LLM Search Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .search-query {
        background-color: var(--secondary-background-color, #e8f4f8);
        color: var(--text-color, #000);
        padding: 0.5rem 1rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
    .source-item {
        background-color: var(--secondary-background-color, #f9f9f9);
        color: var(--text-color, #000);
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
        border: 1px solid rgba(0,0,0,0.1);
    }
    .citation-item {
        background-color: var(--secondary-background-color, #fff8e1);
        color: var(--text-color, #000);
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
        border: 1px solid rgba(0,0,0,0.1);
    }
    /* Constrain images in responses to a small, uniform size and inline layout */
    .stMarkdown img {
        width: 140px;
        height: 90px;
        object-fit: cover;
        margin: 4px 8px 4px 0;
        display: inline-block;
        vertical-align: top;
        float: left;
    }
    .stMarkdown::after {
        content: "";
        display: block;
        clear: both;
    }
    .stMarkdown p {
        clear: both;
    }
    .response-container {
        margin-left: 18px;
        padding-left: 12px;
        border-left: 2px solid #d0d0d0;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables."""
    if 'response' not in st.session_state:
        st.session_state.response = None
    if 'prompt' not in st.session_state:
        st.session_state.prompt = None
    if 'error' not in st.session_state:
        st.session_state.error = None
    if 'db' not in st.session_state or not hasattr(st.session_state.db, "delete_interaction"):
        # Initialize database
        st.session_state.db = Database()
        st.session_state.db.create_tables()
        st.session_state.db.ensure_providers()
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = []
    if 'data_collection_mode' not in st.session_state:
        st.session_state.data_collection_mode = 'api'
    if 'browser_session_active' not in st.session_state:
        st.session_state.browser_session_active = False
    if 'network_headless' not in st.session_state:
        st.session_state.network_headless = False


def format_pub_date(pub_date: str) -> str:
    """Format ISO pub_date to a friendly string."""
    if not pub_date:
        return ""
    try:
        dt = datetime.fromisoformat(pub_date)
        return dt.strftime("%a, %b %d, %Y %H:%M UTC")
    except Exception:
        return pub_date


def normalize_model_id(model: str) -> str:
    """Normalize model identifiers for consistency."""
    if model == "gpt-5-1":
        return "gpt-5.1"
    return model


def sanitize_response_markdown(text: str) -> str:
    """Remove heavy dividers and downscale large headings so they don't exceed the section title."""
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


def build_interaction_markdown(details: dict, interaction_id: int = None) -> str:
    """Build a formatted markdown export of an interaction."""
    lines = []
    if interaction_id is not None:
        lines.append(f"# Interaction {interaction_id}")
        lines.append("")

    # Prompt
    lines.append("## Prompt")
    lines.append(f"> {details.get('prompt', '')}")
    lines.append("")

    # Metadata
    num_searches = len(details.get('search_queries', []))
    # For network logs, sources are in all_sources; for API, they're in query.sources
    if details.get('data_source') == 'network_log':
        num_sources = len(details.get('all_sources', []))
    else:
        num_sources = sum(len(q.get('sources', [])) for q in details.get('search_queries', []))
    # Count only citations with ranks (from search results)
    citations_with_rank = [c for c in details.get('citations', []) if c.get('rank') is not None]
    num_sources_used = len(citations_with_rank)
    avg_rank_display = f"{sum(c['rank'] for c in citations_with_rank) / len(citations_with_rank):.1f}" if citations_with_rank else "N/A"
    response_time_ms = details.get('response_time_ms')
    response_time_s = f"{response_time_ms / 1000:.1f}s" if response_time_ms else "N/A"
    # Count citations without ranks (extra links)
    extra_links = len([c for c in details.get('citations', []) if not c.get('rank')])
    analysis_type = 'Network Logs' if details.get('data_source') == 'network_log' else 'API'

    lines.append("## Metadata")
    lines.append(f"- Provider: {details.get('provider', 'Unknown')}")
    lines.append(f"- Model: {details.get('model', 'Unknown')}")
    lines.append(f"- Analysis: {analysis_type}")
    lines.append(f"- Response Time: {response_time_s}")
    lines.append(f"- Searches: {num_searches}")
    lines.append(f"- Sources Found: {num_sources}")
    lines.append(f"- Sources Used: {num_sources_used}")
    lines.append(f"- Avg. Rank: {avg_rank_display}")
    lines.append(f"- Extra Links: {extra_links}")
    lines.append("")

    # Response
    lines.append("## Response")
    # Format response text (convert citation references to inline links)
    response_text = format_response_text(details.get('response_text', ''), details.get('citations', []))
    lines.append(response_text or "_No response text available._")
    lines.append("")

    # Search queries and sources
    search_queries = details.get('search_queries', [])
    data_source = details.get('data_source', 'api')

    if search_queries:
        lines.append("## Search Queries")
        for idx, query in enumerate(search_queries, 1):
            q_text = query.get('query') or ''
            lines.append(f"### Query {idx}: {q_text}")

        lines.append("")

        # For API data, sources are associated with queries
        if data_source == 'api':
            lines.append("## Sources (by Query)")
            for idx, query in enumerate(search_queries, 1):
                sources = query.get('sources', [])
                lines.append(f"### Query {idx} Sources ({len(sources)})")
                for s_idx, src in enumerate(sources, 1):
                    title = src.get('title') or src.get('domain') or 'Unknown source'
                    url = src.get('url') or ''
                    domain = src.get('domain') or ''
                    snippet = src.get('snippet') or 'N/A'
                    if snippet == 'N/A' and src.get('title'):
                        snippet = src.get('title')
                    pub_date = src.get('pub_date')
                    pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                    lines.append(f"{s_idx}. [{title}]({url}) ({domain})")
        # For network logs, sources aren't associated with specific queries
        else:
            all_sources = details.get('all_sources', [])
            if all_sources:
                lines.append(f"## Sources Found ({len(all_sources)})")
                lines.append("_Note: Network logs don't provide reliable query-to-source mapping._")
                lines.append("")
                for s_idx, src in enumerate(all_sources, 1):
                    title = src.get('title') or src.get('domain') or 'Unknown source'
                    url = src.get('url') or ''
                    domain = src.get('domain') or ''
                    snippet = src.get('snippet') or 'N/A'
                    if snippet == 'N/A' and src.get('title'):
                        snippet = src.get('title')
                    pub_date = src.get('pub_date')
                    pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                    lines.append(f"{s_idx}. [{title}]({url}) ({domain})")
                    lines.append(f"   - Snippet: {snippet}")
                    lines.append(f"   - Published: {pub_date_fmt}")
        lines.append("")

    # Sources used
    citations = details.get('citations', [])
    if citations:
        lines.append("## Sources Used")
        for c_idx, citation in enumerate(citations, 1):
            title = citation.get('title') or 'Unknown source'
            url = citation.get('url') or ''
            domain = urlparse(url).netloc if url else ''
            q_idx = citation.get('query_index')
            rank = citation.get('rank')
            rank_bits = []
            if q_idx is not None:
                rank_bits.append(f"Query {q_idx + 1}")
            if rank:
                rank_bits.append(f"Rank {rank}")
            rank_display = f" ({', '.join(rank_bits)})" if rank_bits else ""
            snippet = citation.get('snippet') or 'N/A'
            pub_date = citation.get('pub_date')
            pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
            lines.append(f"{c_idx}. [{title}]({url}) ({domain}){rank_display}")
            lines.append(f"   - Snippet: {snippet}")
            lines.append(f"   - Published: {pub_date_fmt}")

    return "\n".join(lines).strip() + "\n"


def format_response_text(text: str, citations: list) -> str:
    """
    Format response text by converting reference-style citation links to inline links.

    ChatGPT includes markdown reference links at the bottom like:
    [1]: URL "Title"
    [2]: URL "Title"

    And uses them inline like: [Text][1]

    We convert these to inline markdown links: [Text](URL)
    Then remove the reference definitions.
    """
    if not text:
        return ""

    # Step 1: Extract reference-style link definitions into a mapping
    # Pattern: [N]: URL "Title" or [N]: URL
    # Handle titles with escaped quotes by matching everything after URL to end of line
    reference_pattern = r'^\[(\d+)\]:\s+(https?://\S+)(?:\s+.*)?$'
    references = {}
    for match in re.finditer(reference_pattern, text, flags=re.MULTILINE):
        ref_num = match.group(1)
        url = match.group(2)
        references[ref_num] = url

    # Step 2: Replace reference-style links with inline links
    # Pattern: [text][N] where N is a number
    def replace_reference_link(match):
        link_text = match.group(1)
        ref_num = match.group(2)
        if ref_num in references:
            return f"[{link_text}]({references[ref_num]})"
        return match.group(0)  # Keep original if reference not found

    text = re.sub(r'\[([^\]]+)\]\[(\d+)\]', replace_reference_link, text)

    # Step 3: Remove the reference definitions from the bottom
    text = re.sub(reference_pattern, '', text, flags=re.MULTILINE)

    # Step 4: Clean up any resulting multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return sanitize_response_markdown(text.strip())


def extract_images_from_response(text: str):
    """Extract image URLs from markdown or img tags and return cleaned text."""
    if not text:
        return text, []
    images = []

    # Markdown images ![alt](url)
    def md_repl(match):
        url = match.group(1)
        if url:
            images.append(url)
        return ""  # strip from text
    text = re.sub(r"!\[[^\]]*\]\(([^) ]+)[^)]*\)", md_repl, text)

    # HTML img tags
    def html_repl(match):
        src = match.group(1)
        if src:
            images.append(src)
        return ""
    text = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html_repl, text, flags=re.IGNORECASE)

    return text.strip(), images

def get_all_models():
    """Get all available models with provider labels."""
    try:
        api_keys = Config.get_api_keys()
        models = {}

        provider_labels = {
            'openai': '🟢 OpenAI',
            'google': '🔵 Google',
            'anthropic': '🟣 Anthropic'
        }

        # Model display names
        model_names = {
            # Anthropic
            'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
            'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
            'claude-opus-4-1-20250805': 'Claude Opus 4.1',
            # OpenAI
            'gpt-5.1': 'GPT-5.1',
            'gpt-5-mini': 'GPT-5 Mini',
            'gpt-5-nano': 'GPT-5 Nano',
            # Google
            'gemini-3-pro-preview': 'Gemini 3 Pro (Preview)',
            'gemini-2.5-flash': 'Gemini 2.5 Flash',
            'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
            # Network capture
            'ChatGPT (Free)': 'ChatGPT (Free)',
            'chatgpt-free': 'ChatGPT (Free)',
        }

        for provider_name in ['openai', 'google', 'anthropic']:
            if api_keys.get(provider_name):
                provider = ProviderFactory.create_provider(provider_name, api_keys[provider_name])
                for model in provider.get_supported_models():
                    # Get formatted model name
                    formatted_model = model_names.get(model, model)
                    # Create label: "🟢 OpenAI - GPT-5.1"
                    label = f"{provider_labels[provider_name]} - {formatted_model}"
                    models[label] = (provider_name, model)

        return models
    except Exception as e:
        st.error(f"Error loading models: {str(e)}")
        return {}

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

    # Model display names
    model_names = {
        # Anthropic
        'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
        'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
        'claude-opus-4-1-20250805': 'Claude Opus 4.1',
        # OpenAI
        'gpt-5.1': 'GPT-5.1',
        'gpt-5-1': 'GPT-5.1',
        'gpt-5-mini': 'GPT-5 Mini',
        'gpt-5-nano': 'GPT-5 Nano',
        # Google
        'gemini-3-pro-preview': 'Gemini 3 Pro (Preview)',
        'gemini-2.5-flash': 'Gemini 2.5 Flash',
        'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
        # Network capture
        'ChatGPT (Free)': 'ChatGPT (Free)',
        'chatgpt-free': 'ChatGPT (Free)',
    }

    # Response metadata
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.5, 2, 1, 1, 1, 1, 1, 1])

    with col1:
        st.metric("Provider", provider_names.get(response.provider.lower(), response.provider))
    with col2:
        st.metric("Model", model_names.get(response.model, response.model))
    with col3:
        response_time = f"{response.response_time_ms / 1000:.1f}s" if response.response_time_ms else "N/A"
        st.metric("Response Time", response_time)
    with col4:
        st.metric("Search Queries", len(response.search_queries))
    with col5:
        # Count sources differently for API vs network logs
        if getattr(response, 'data_source', 'api') == 'network_log':
            sources_count = len(response.sources)
        else:
            # API: count sources from all queries
            sources_count = sum(len(q.sources) for q in response.search_queries)
        st.metric("Sources Found", sources_count)
    with col6:
        # Count only citations with ranks (from search results)
        sources_with_rank = [c for c in response.citations if c.rank]
        st.metric("Sources Used", len(sources_with_rank))
    with col7:
        # Calculate average rank from sources used (citations with ranks)
        if sources_with_rank:
            avg_rank = sum(c.rank for c in sources_with_rank) / len(sources_with_rank)
            st.metric("Avg. Rank", f"{avg_rank:.1f}")
        else:
            st.metric("Avg. Rank", "N/A")
    with col8:
        # Use parser-provided extra_links_count if available; fallback to citations without ranks
        extra_links = getattr(response, "extra_links_count", None)
        if extra_links is None:
            extra_links = len([c for c in response.citations if not c.rank])
        st.metric("Extra Links", extra_links)

    st.divider()

    # Response text
    response_time_label = response_time if response_time else "N/A"
    st.markdown(f"### 💬 Response ({response_time_label}):")
    formatted_response = format_response_text(response.response_text, response.citations)
    formatted_response, extracted_images = extract_images_from_response(formatted_response)

    if extracted_images:
        # Render images inline with minimal gaps
        img_html = "".join([f'<img src="{url}" style="width:210px;height:135px;object-fit:cover;margin:4px 6px 4px 0;vertical-align:top;"/>' for url in extracted_images])
        st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;'>{img_html}</div>", unsafe_allow_html=True)

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
            st.markdown("### 📚 Sources (by Query):")
            for i, query in enumerate(queries_with_sources, 1):
                with st.expander(f"📚 Sources from Query {i} ({len(query.sources)} sources)", expanded=False):
                    for j, source in enumerate(query.sources, 1):
                        url_display = source.url or 'No URL'
                        url_truncated = url_display[:80] + ('...' if len(url_display) > 80 else '')
                        # Use domain as title fallback when title is missing
                        display_title = source.title or source.domain or 'Unknown source'
                        snippet = getattr(source, "snippet_text", None)
                        pub_date = getattr(source, "pub_date", None)
                        snippet_display = snippet if snippet else "N/A"
                        pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                        snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"
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
        if response.sources:
            st.markdown(f"### 📚 Sources Found ({len(response.sources)}):")
            st.caption("_Note: Network logs don't provide reliable query-to-source mapping._")
            with st.expander(f"View all {len(response.sources)} sources", expanded=False):
                for j, source in enumerate(response.sources, 1):
                    url_display = source.url or 'No URL'
                    url_truncated = url_display[:80] + ('...' if len(url_display) > 80 else '')
                    # Use domain as title fallback when title is missing
                    display_title = source.title or source.domain or 'Unknown source'
                    snippet = getattr(source, "snippet_text", None)
                    pub_date = getattr(source, "pub_date", None)
                    snippet_display = snippet if snippet else "N/A"
                    pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                    snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"
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
        # For API: sources are in query.sources; for network logs: sources are in response.sources
        if getattr(response, 'data_source', 'api') == 'network_log':
            url_to_source = {s.url: s for s in response.sources if getattr(s, "url", None)}
        else:
            # API: gather sources from all queries
            all_sources = [s for q in response.search_queries for s in q.sources]
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
                snippet_used = getattr(citation, "snippet_used", None)
                source_fallback = url_to_source.get(citation.url)
                snippet = snippet_used or (citation.metadata.get("snippet") if getattr(citation, "metadata", None) else None) or (getattr(source_fallback, "snippet_text", None))
                pub_date_val = (citation.metadata.get("pub_date") if getattr(citation, "metadata", None) else None) or (getattr(source_fallback, "pub_date", None))
                snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet or 'N/A'}</em></div>"
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
                snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet or 'N/A'}</em></div>" if snippet else ""

                st.markdown(f"""
                <div class="citation-item">
                    <strong>{i}. {display_title}</strong><br/>
                    {domain_link}
                    {snippet_block}
                </div>
                """, unsafe_allow_html=True)

def tab_interactive():
    """Tab 1: Interactive Prompting."""
    st.markdown("### 💭 Enter Your Prompt")

    # Load all available models
    models = get_all_models()

    if not models:
        st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
        return

    # Model selection (hide in network log mode since it always uses chatgpt-free)
    if st.session_state.data_collection_mode == 'network_log':
        st.info("🌐 **Network Capture Mode**: Using free ChatGPT (model selection not available)")
        st.checkbox("Run browser headless", value=st.session_state.network_headless, key="network_headless")
        # Fixed model for network capture
        selected_provider = 'openai'
        selected_model = 'chatgpt-free'
        selected_label = '🟢 OpenAI - ChatGPT'
    else:
        model_labels = list(models.keys())
        selected_label = st.selectbox(
            "Select Model",
            model_labels,
            help="Choose a model from any available provider"
        )

        # Extract provider and model from selection
        selected_provider, selected_model = models[selected_label]

    # Prompt input (Enter submits, Shift+Enter for newline)
    prompt = st.chat_input("Prompt (Enter to send, Shift+Enter for new line)")

    # Handle submission when chat_input returns a value
    if prompt is not None:
        if not prompt.strip():
            st.warning("Please enter a prompt")
            return

        # Show loading state
        # Extract formatted model name from selected_label (format: "🟢 Provider - Model Name")
        formatted_model = selected_label.split(' - ', 1)[1] if ' - ' in selected_label else selected_model
        with st.spinner(f"Querying {formatted_model}..."):
            try:
                # Check data collection mode and route accordingly
                if st.session_state.data_collection_mode == 'network_log':
                    # Use network log capture
                    from src.network_capture.chatgpt_capturer import ChatGPTCapturer

                    # Only ChatGPT is supported for network logs currently
                    if selected_provider != 'openai':
                        st.error(f"Network log mode is only supported for OpenAI/ChatGPT currently. Selected provider: {selected_provider}")
                        st.session_state.error = "Network log mode only supports OpenAI/ChatGPT"
                        return

                    # Check if ChatGPT credentials are configured
                    if not Config.CHATGPT_EMAIL or not Config.CHATGPT_PASSWORD:
                        st.error("ChatGPT credentials not found. Please add CHATGPT_EMAIL and CHATGPT_PASSWORD to your .env file.")
                        st.session_state.error = "Missing ChatGPT credentials"
                        return

                    # Initialize and use capturer
                    capturer = ChatGPTCapturer()
                    capturer.start_browser(headless=st.session_state.network_headless)

                    try:
                        # Authenticate with credentials from Config
                        # Session persistence will restore saved sessions automatically
                        if not capturer.authenticate(
                            email=Config.CHATGPT_EMAIL,
                            password=Config.CHATGPT_PASSWORD
                        ):
                            raise Exception("Failed to authenticate with ChatGPT")

                        # Send prompt and capture
                        # Always use 'chatgpt-free' for network capture (free accounts don't have model selection)
                        response = capturer.send_prompt(prompt, 'chatgpt-free')

                    finally:
                        # Always cleanup browser
                        capturer.stop_browser()

                else:
                    # Use API-based provider (default)
                    api_keys = Config.get_api_keys()
                    provider = ProviderFactory.create_provider(selected_provider, api_keys[selected_provider])

                    # Send prompt
                    response = provider.send_prompt(prompt, selected_model)

                # Save to database (works for both modes)
                try:
                    model_to_save = normalize_model_id(getattr(response, "model", None) or selected_model)
                    st.session_state.db.save_interaction(
                        provider_name=selected_provider,
                        model=model_to_save,
                        prompt=prompt,
                        response_text=response.response_text,
                        search_queries=response.search_queries,
                        sources=response.sources,
                        citations=response.citations,
                        response_time_ms=response.response_time_ms,
                        raw_response=response.raw_response,
                        data_source=st.session_state.data_collection_mode,
                        extra_links_count=getattr(response, "extra_links_count", 0)
                    )
                except Exception as db_error:
                    st.warning(f"Response saved but database error occurred: {str(db_error)}")

                # Store in session state
                st.session_state.response = response
                st.session_state.prompt = prompt
                st.session_state.error = None

            except Exception as e:
                st.session_state.error = str(e)
                st.session_state.response = None

    # Display results
    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")

    if st.session_state.response:
        st.divider()
        display_response(st.session_state.response, st.session_state.get('prompt'))

def tab_batch():
    """Tab 2: Batch Analysis."""
    st.markdown("### 📦 Batch Analysis")
    st.caption("Run multiple prompts and analyze aggregate results")

    # Load all available models
    models = get_all_models()

    if not models:
        st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
        return

    # Model selection
    model_labels = list(models.keys())
    selected_labels = st.multiselect(
        "Select Models for Batch",
        model_labels,
        default=[model_labels[0]] if model_labels else [],
        help="Choose one or more models to compare across all prompts"
    )

    # Extract providers and models from selections
    selected_models = []
    if selected_labels:
        for label in selected_labels:
            provider, model = models[label]
            selected_models.append((label, provider, model))

    # Prompt input methods
    st.markdown("#### Enter Prompts")
    input_method = st.radio("Input Method", ["Text Area", "CSV Upload"], horizontal=True)

    prompts = []

    if input_method == "Text Area":
        prompts_text = st.text_area(
            "Enter prompts (one per line)",
            height=200,
            placeholder="What is the weather today?\nTell me about AI advancements\nWho won the latest sports championship?"
        )
        if prompts_text:
            prompts = [p.strip() for p in prompts_text.split('\n') if p.strip()]

    else:  # CSV Upload
        uploaded_file = st.file_uploader("Upload CSV file with 'prompt' column", type=['csv'])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                if 'prompt' not in df.columns:
                    st.error("CSV must have a 'prompt' column")
                else:
                    prompts = df['prompt'].dropna().tolist()
                    st.success(f"Loaded {len(prompts)} prompts from CSV")
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")

    # Display prompt and model count
    if prompts and selected_models:
        total_runs = len(prompts) * len(selected_models)
        st.info(f"Ready to process {len(prompts)} prompt(s) × {len(selected_models)} model(s) = {total_runs} total runs")

    # Run button
    if st.button("▶️ Run Batch Analysis", type="primary", disabled=len(prompts) == 0 or len(selected_models) == 0):
        st.session_state.batch_results = []

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Get API keys
        api_keys = Config.get_api_keys()

        # Calculate total runs
        total_runs = len(prompts) * len(selected_models)
        current_run = 0

        # Process each prompt with each model
        for prompt_idx, prompt in enumerate(prompts):
            for model_label, provider_name, model_name in selected_models:
                current_run += 1
                status_text.text(f"Processing run {current_run}/{total_runs}: {model_label} - Prompt {prompt_idx + 1}/{len(prompts)}")

                try:
                    # Check data collection mode and route accordingly
                    if st.session_state.data_collection_mode == 'network_log':
                        # Use network log capture
                        from src.network_capture.chatgpt_capturer import ChatGPTCapturer

                        # Only ChatGPT is supported for network logs currently
                        if provider_name != 'openai':
                            raise Exception(f"Network log mode only supports OpenAI/ChatGPT. Skipping {provider_name}")

                        # Check if ChatGPT credentials are configured
                        if not Config.CHATGPT_EMAIL or not Config.CHATGPT_PASSWORD:
                            raise Exception("ChatGPT credentials not found. Please add CHATGPT_EMAIL and CHATGPT_PASSWORD to your .env file.")

                        # Initialize and use capturer
                        # Note: headless=False to avoid Cloudflare CAPTCHA
                        capturer = ChatGPTCapturer()
                        capturer.start_browser(headless=False)

                        try:
                            # Authenticate with credentials from Config
                            # Session persistence will restore saved sessions automatically
                            if not capturer.authenticate(
                                email=Config.CHATGPT_EMAIL,
                                password=Config.CHATGPT_PASSWORD
                            ):
                                raise Exception("Failed to authenticate with ChatGPT")

                            # Send prompt and capture
                            # Always use 'chatgpt-free' for network capture (free accounts don't have model selection)
                            response = capturer.send_prompt(prompt, 'chatgpt-free')

                        finally:
                            # Always cleanup browser
                            capturer.stop_browser()

                    else:
                        # Use API-based provider (default)
                        provider = ProviderFactory.create_provider(provider_name, api_keys[provider_name])

                        # Send prompt
                        response = provider.send_prompt(prompt, model_name)

                    # Save to database (works for both modes)
                    try:
                        model_to_save = normalize_model_id(getattr(response, "model", None) or model_name)
                        st.session_state.db.save_interaction(
                            provider_name=provider_name,
                            model=model_to_save,
                            prompt=prompt,
                            response_text=response.response_text,
                            search_queries=response.search_queries,
                            sources=response.sources,
                            citations=response.citations,
                            response_time_ms=response.response_time_ms,
                            raw_response=response.raw_response,
                            data_source=st.session_state.data_collection_mode,
                            extra_links_count=getattr(response, "extra_links_count", 0)
                        )
                    except Exception as db_error:
                        st.warning(f"Database error for {model_label} prompt {prompt_idx + 1}: {str(db_error)}")

                    # Calculate average rank
                    citations_with_rank = [c for c in response.citations if c.rank]
                    avg_rank = sum(c.rank for c in citations_with_rank) / len(citations_with_rank) if citations_with_rank else None

                    # Store result
                    st.session_state.batch_results.append({
                        'prompt': prompt,
                        'model': model_label,
                        'searches': len(response.search_queries),
                        'sources': len(response.sources),
                        'sources_used': len(response.citations),
                        'avg_rank': avg_rank,
                        'response_time_s': response.response_time_ms / 1000
                    })

                except Exception as e:
                    st.session_state.batch_results.append({
                        'prompt': prompt,
                        'model': model_label,
                        'error': str(e)
                    })

                # Update progress
                progress_bar.progress(current_run / total_runs)

        status_text.text("✅ Batch processing complete!")

    # Display results
    if st.session_state.batch_results:
        st.divider()
        st.markdown("### 📊 Batch Results")

        # Summary stats
        successful = [r for r in st.session_state.batch_results if 'error' not in r]
        failed = [r for r in st.session_state.batch_results if 'error' in r]

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Runs", len(st.session_state.batch_results))
        with col2:
            st.metric("Successful", len(successful))
        with col3:
            if successful:
                avg_sources = sum(r['sources'] for r in successful) / len(successful)
                st.metric("Avg Sources", f"{avg_sources:.1f}")
        with col4:
            if successful:
                avg_sources_used = sum(r['sources_used'] for r in successful) / len(successful)
                st.metric("Avg Sources Used", f"{avg_sources_used:.1f}")
        with col5:
            if successful:
                ranks = [r['avg_rank'] for r in successful if r['avg_rank'] is not None]
                if ranks:
                    overall_avg_rank = sum(ranks) / len(ranks)
                    st.metric("Avg Rank", f"{overall_avg_rank:.1f}")
                else:
                    st.metric("Avg Rank", "N/A")

        # Results table
        st.markdown("#### Detailed Results")
        df_results = pd.DataFrame(st.session_state.batch_results)

        # Format the display columns
        if not df_results.empty and 'error' not in df_results.columns:
            # Format avg_rank for display
            df_results['avg_rank_display'] = df_results['avg_rank'].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
            )

            # Format response_time for display
            df_results['response_time_display'] = df_results['response_time_s'].apply(
                lambda x: f"{x:.1f}s" if pd.notna(x) else "N/A"
            )

            # Select and rename columns for display
            display_df = df_results[['prompt', 'model', 'searches', 'sources', 'sources_used',
                                     'avg_rank_display', 'response_time_display']]
            display_df.columns = ['Prompt', 'Model', 'Searches', 'Sources Found', 'Sources Used',
                                 'Avg. Rank', 'Response Time']

            st.dataframe(display_df, use_container_width=True)
        else:
            st.dataframe(df_results, use_container_width=True)

        # Export button
        csv = df_results.to_csv(index=False)
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        # Show errors if any
        if failed:
            st.warning(f"⚠️ {len(failed)} prompts failed")
            with st.expander("View Errors"):
                for idx, result in enumerate(failed, 1):
                    st.error(f"{idx}. {result['prompt'][:50]}...\n Error: {result['error']}")

def tab_history():
    """Tab 3: Query History."""
    st.markdown("### 📜 Query History")
    # Get recent interactions
    try:
        interactions = st.session_state.db.get_recent_interactions(limit=100)

        if not interactions:
            st.info("No interactions recorded yet. Start by submitting prompts in the Interactive tab!")
            return

        # Convert to DataFrame
        df = pd.DataFrame(interactions)

        # Sort by timestamp desc, then format
        df['_ts_dt'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values(by='_ts_dt', ascending=False)
        df['timestamp'] = df['_ts_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df = df.drop(columns=['_ts_dt'])

        # Truncate prompt for display
        df['prompt_preview'] = df['prompt'].str[:80] + df['prompt'].apply(lambda x: '...' if len(x) > 80 else '')

        # Ensure extra_links column exists for older rows
        if 'extra_links' not in df.columns:
            df['extra_links'] = 0

        # Friendly label for analysis type
        df['analysis_type'] = df['data_source'].apply(lambda x: 'Network Logs' if x == 'network_log' else 'API')

        # Format average rank for display
        df['avg_rank_display'] = df['avg_rank'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")

        # Filters and sorting layout
        col_search, col_analysis, col_provider, col_model = st.columns([1.2, 1, 1, 1])

        with col_search:
            search_query = st.text_input("🔍 Search prompts", placeholder="Enter keywords to filter...")

        with col_analysis:
            analysis_options = sorted(df['analysis_type'].dropna().unique().tolist())
            selected_analysis = st.multiselect(
                "Analysis type",
                options=analysis_options,
                default=analysis_options,
            ) if analysis_options else []

        with col_provider:
            provider_options = sorted(df['provider'].dropna().unique().tolist())
            selected_providers = st.multiselect(
                "Provider",
                options=provider_options,
                default=provider_options,
            ) if provider_options else []

        with col_model:
            model_options = sorted(df['model'].dropna().unique().tolist())
            selected_models = st.multiselect(
                "Model",
                options=model_options,
                default=model_options,
            ) if model_options else []

        # Apply filters
        if search_query:
            df = df[df['prompt'].str.contains(search_query, case=False, na=False)]
        if selected_analysis:
            df = df[df['analysis_type'].isin(selected_analysis)]
        if selected_providers:
            df = df[df['provider'].isin(selected_providers)]
        if selected_models:
            df = df[df['model'].isin(selected_models)]

        # Default sort (newest first); users can re-sort via table headers
        df = df.sort_values(by="timestamp", ascending=False, na_position="last")

        display_df = df[['id', 'timestamp', 'analysis_type', 'prompt_preview', 'provider', 'model', 'searches', 'sources', 'citations', 'avg_rank_display', 'extra_links']]
        display_df.columns = ['ID', 'Timestamp', 'Analysis Type', 'Prompt', 'Provider', 'Model', 'Searches', 'Sources Found', 'Sources Used', 'Avg. Rank', 'Extra Links']

        # Configure column widths and alignment
        # Let Streamlit autosize columns; avoid fixed widths
        column_config = {
            "ID": st.column_config.NumberColumn("ID"),
            "Timestamp": st.column_config.TextColumn("Timestamp"),
            "Analysis Type": st.column_config.TextColumn("Analysis Type"),
            "Prompt": st.column_config.TextColumn("Prompt"),
            "Provider": st.column_config.TextColumn("Provider"),
            "Model": st.column_config.TextColumn("Model"),
            "Searches": st.column_config.NumberColumn("Searches"),
            "Sources Found": st.column_config.NumberColumn("Sources Found"),
            "Sources Used": st.column_config.NumberColumn("Sources Used"),
            "Avg. Rank": st.column_config.TextColumn("Avg. Rank"),
            "Extra Links": st.column_config.NumberColumn("Extra Links"),
        }

        st.dataframe(
            display_df,
            use_container_width=True,
            height=400,
            hide_index=True,
            column_config=column_config,
        )

        # Export button (aligned width with action buttons)
        csv = display_df.to_csv(index=False)
        export_col, _export_spacer = st.columns([1, 4])
        with export_col:
            st.download_button(
                label="📥 Export History as CSV",
                data=csv,
                file_name=f"query_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.divider()

        # View details
        st.markdown("### 🧾 View Interaction Details")
        selected_id = st.selectbox(
            "Select an interaction to view details",
            options=df['id'].tolist(),
            format_func=lambda x: f"ID {x}: {df[df['id'] == x]['prompt_preview'].values[0]}"
        )

        if selected_id:
            details = st.session_state.db.get_interaction_details(selected_id)
            if details:
                # Download interaction as markdown (placed directly after selector)
                md_export = build_interaction_markdown(details, selected_id)
                btn_wrap, _ = st.columns([1, 4])
                with btn_wrap:
                    btn_col1, btn_col2 = st.columns(2, gap="small")
                    with btn_col1:
                        st.download_button(
                            label="📥 Download as Markdown",
                            data=md_export,
                            file_name=f"interaction_{selected_id}.md",
                            mime="text/markdown",
                            use_container_width=True,
                        )
                    with btn_col2:
                        if st.button("🗑️ Delete Interaction", type="secondary", use_container_width=True):
                            try:
                                deleted = st.session_state.db.delete_interaction(selected_id)
                                if deleted:
                                    st.success(f"Interaction ID {selected_id} deleted.")
                                    try:
                                        # Streamlit >=1.22 uses st.rerun
                                        rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
                                        if rerun:
                                            rerun()
                                    except Exception:
                                        pass
                                else:
                                    st.warning("Interaction not found.")
                            except Exception as del_err:
                                st.error(f"Failed to delete interaction: {del_err}")

                st.divider()
                # Prompt header
                st.markdown(f"### 🗣️ *\"{details['prompt']}\"*")

                # Calculate metrics
                num_searches = len(details['search_queries'])
                # For network logs, sources are in all_sources; for API, they're in query.sources
                if details.get('data_source') == 'network_log':
                    num_sources = len(details.get('all_sources', []))
                else:
                    num_sources = sum(len(query['sources']) for query in details['search_queries'])
                # Count only citations with ranks (from search results)
                citations_with_rank = [c for c in details['citations'] if c.get('rank') is not None]
                num_sources_used = len(citations_with_rank)
                avg_rank_display = f"{sum(c['rank'] for c in citations_with_rank) / len(citations_with_rank):.1f}" if citations_with_rank else "N/A"
                response_time_s = f"{details['response_time_ms'] / 1000:.1f}s"
                # Extra links from stored value; fallback to citations without rank
                extra_links_count = details.get('extra_links', len([c for c in details['citations'] if not c.get('rank')]))
                # Response metadata
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.5, 2, 1, 1, 1, 1, 1, 1])

                # Provider display names
                provider_names = {
                    'openai': 'OpenAI',
                    'google': 'Google',
                    'anthropic': 'Anthropic'
                }

                # Model display names
                model_names = {
                    'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
                    'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
                    'claude-opus-4-1-20250805': 'Claude Opus 4.1',
                    'gpt-5.1': 'GPT-5.1',
                    'gpt-5-1': 'GPT-5.1',
                    'gpt-5-mini': 'GPT-5 Mini',
                    'gpt-5-nano': 'GPT-5 Nano',
                    'gemini-3-pro-preview': 'Gemini 3 Pro (Preview)',
                    'gemini-2.5-flash': 'Gemini 2.5 Flash',
                    'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
                    'ChatGPT (Free)': 'ChatGPT (Free)',
                    'chatgpt-free': 'ChatGPT (Free)',
                }

                with col1:
                    st.metric("Provider", provider_names.get(details['provider'].lower(), details['provider']))
                with col2:
                    st.metric("Model", model_names.get(details['model'], details['model']))
                with col3:
                    st.metric("Response Time", response_time_s)
                with col4:
                    st.metric("Search Queries", num_searches)
                with col5:
                    st.metric("Sources Found", num_sources)
                with col6:
                    st.metric("Sources Used", num_sources_used)
                with col7:
                    st.metric("Avg. Rank", avg_rank_display)
                with col8:
                    st.metric("Extra Links", extra_links_count)

                st.divider()

                st.markdown(f"### 💬 Response ({response_time_s}):")
                # Format response text (convert citation references to inline links)
                formatted_detail_response = format_response_text(details['response_text'], details.get('citations', []))
                formatted_detail_response, extracted_images = extract_images_from_response(formatted_detail_response)

                if extracted_images:
                    # Render images inline with minimal gaps
                    img_html = "".join([f'<img src="{url}" style="width:210px;height:135px;object-fit:cover;margin:4px 6px 4px 0;vertical-align:top;"/>' for url in extracted_images])
                    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;'>{img_html}</div>", unsafe_allow_html=True)

                # Render markdown with indented container styling
                # Use newlines around content to ensure markdown processing works inside the div
                st.markdown(
                    f'<div class="response-container">\n\n{formatted_detail_response}\n\n</div>',
                    unsafe_allow_html=True
                )

                st.divider()

                if details['search_queries']:
                    st.markdown(f"### 🔍 Search Queries ({len(details['search_queries'])}):")
                    for i, query in enumerate(details['search_queries'], 1):
                        # Display query with same styling as interactive tab
                        st.markdown(f"""
                        <div class="search-query">
                            <strong>Query {i}:</strong> {query['query']}
                        </div>
                        """, unsafe_allow_html=True)

                    st.divider()

                    # Display sources differently for API vs Network Log
                    data_source = details.get('data_source', 'api')
                    if data_source == 'api':
                        # API: Sources are associated with queries
                        st.markdown(f"### 📚 Sources (by Query):")
                        for i, query in enumerate(details['search_queries'], 1):
                            query_sources = query.get('sources', [])
                            if query_sources:
                                with st.expander(f"Query {i} ({len(query_sources)} sources)", expanded=False):
                                    for j, src in enumerate(query_sources, 1):
                                        domain_link = f"[{urlparse(src['url']).netloc or 'Open source'}]({src['url']})" if src.get('url') else (src.get('domain') or 'Unknown domain')
                                        snippet = src.get('title') or domain_link
                                        st.markdown(f"{j}. {snippet} — {domain_link}")
                    else:
                        # Network Log: Sources aren't associated with specific queries
                        all_sources = details.get('all_sources', [])
                        if all_sources:
                            st.markdown(f"### 📚 Sources Found ({len(all_sources)}):")
                            st.caption("_Note: Network logs don't provide reliable query-to-source mapping._")
                            with st.expander(f"View all {len(all_sources)} sources", expanded=False):
                                for j, src in enumerate(all_sources, 1):
                                    url_display = src.get('url') or 'No URL'
                                    # Use domain as title fallback when title is missing
                                    display_title = src.get('title') or src.get('domain') or 'Unknown source'
                                    snippet = src.get('snippet')
                                    pub_date = src.get('pub_date')
                                    snippet_display = snippet if snippet else "N/A"
                                    pub_date_fmt = format_pub_date(pub_date) if pub_date else "N/A"
                                    snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet_display}</em></div>"
                                    pub_date_block = f"<small><strong>Published:</strong> {pub_date_fmt}</small>"
                                    domain_link = f'<a href="{url_display}" target="_blank">{src.get("domain") or "Open source"}</a>'
                                    st.markdown(f"""
                                    <div class="source-item">
                                        <strong>{j}. {display_title}</strong><br/>
                                        <small>{domain_link}</small>
                                        {snippet_block}
                                        {pub_date_block}
                                    </div>
                                    """, unsafe_allow_html=True)

                # Sources used (from web search) - only citations with ranks
                citations_with_rank = [c for c in details['citations'] if c.get('rank')]
                if citations_with_rank:
                    st.divider()
                    st.markdown(f"### 📝 Sources Used ({len(citations_with_rank)}):")
                    st.caption("Sources the model consulted via web search")

                    # Build URL -> source lookup for metadata fallback
                    all_sources = details.get('all_sources', [])
                    url_to_source = {src['url']: src for src in all_sources if src.get('url')}

                    for i, citation in enumerate(citations_with_rank, 1):
                        with st.container():
                            url_display = citation.get('url') or 'No URL'
                            domain_link = f'<a href="{url_display}" target="_blank">{urlparse(url_display).netloc or url_display}</a>'

                            # Extract rank and display in parentheses
                            rank = citation.get('rank')
                            rank_display = f" (Rank {rank})" if rank else ""

                            # Extract domain from URL for fallback
                            domain = urlparse(url_display).netloc if url_display != 'No URL' else 'Unknown domain'
                            display_title = citation.get('title') or domain or 'Unknown source'

                            # Get snippet and pub_date from citation metadata or source fallback
                            snippet = citation.get('snippet')
                            pub_date_val = citation.get('pub_date')

                            # Fallback to source data if available
                            if not snippet or not pub_date_val:
                                source_fallback = url_to_source.get(url_display)
                                if source_fallback:
                                    snippet = snippet or source_fallback.get('snippet')
                                    pub_date_val = pub_date_val or source_fallback.get('pub_date')

                            snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet or 'N/A'}</em></div>"
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
                extra_links = [c for c in details['citations'] if not c.get('rank')]
                if extra_links:
                    st.divider()
                    st.markdown(f"### 🔗 Extra Links ({len(extra_links)}):")
                    st.caption("Links mentioned in the response that weren't from search results")

                    for i, citation in enumerate(extra_links, 1):
                        with st.container():
                            url_display = citation.get('url') or 'No URL'
                            domain_link = f'<a href="{url_display}" target="_blank">{urlparse(url_display).netloc or url_display}</a>'
                            domain = urlparse(url_display).netloc if url_display != 'No URL' else 'Unknown domain'
                            display_title = citation.get('title') or domain or 'Unknown source'

                            # Get snippet if available
                            snippet = citation.get('snippet')
                            snippet_block = f"<div style='margin-top:4px; font-size:0.95rem;'><strong>Snippet:</strong> <em>{snippet or 'N/A'}</em></div>" if snippet else ""

                            st.markdown(f"""
                            <div class="citation-item">
                                <strong>{i}. {display_title}</strong><br/>
                                {domain_link}
                                {snippet_block}
                            </div>
                            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error loading history: {str(e)}")

def sidebar_info():
    """Sidebar information."""
    st.sidebar.title("⚙️ Configuration")

    # Data collection mode
    st.sidebar.markdown("### 📡 Data Collection Mode")
    mode_options = ["API (Recommended)", "Network Logs (Experimental)"]
    selected_mode = st.sidebar.radio(
        "Choose data collection method:",
        mode_options,
        index=0 if st.session_state.data_collection_mode == 'api' else 1,
        help="API mode uses official provider APIs. Network Log mode captures browser traffic for deeper insights.",
        label_visibility="collapsed"
    )

    # Update session state based on selection
    st.session_state.data_collection_mode = 'api' if selected_mode == mode_options[0] else 'network_log'

    # Show info for network log mode
    if st.session_state.data_collection_mode == 'network_log':
        st.sidebar.info("""
        **🌐 Experimental: Browser Network Capture**

        Uses browser automation to capture network data for deeper insights.

        **How it works:**
        - Opens a Chrome browser window
        - Navigates to ChatGPT automatically
        - Submits your prompt
        - Captures network traffic with metadata
        - Closes browser when done

        **Features:**
        - Session persistence (stays logged in)
        - Captures internal ranking scores
        - Records query reformulations
        - Headless mode available (may hit CAPTCHA)

        **Additional Metadata:**
        Network logs provide internal scores, snippet text, and query reformulation data not available via API.

        **Status:** ✅ Working
        """)

    st.sidebar.divider()

    # Info section
    with st.sidebar.expander("ℹ️ About", expanded=False):
        st.markdown("""
        This tool analyzes how different LLM providers:
        - Formulate search queries
        - Fetch web sources
        - Cite information in responses

        **Providers:**
        - OpenAI (Responses API)
        - Google Gemini (Search Grounding)
        - Anthropic Claude (Web Search Tool)
        """)

    # Understanding Metrics section
    with st.sidebar.expander("📊 Understanding Metrics", expanded=False):
        st.markdown("""
        **Key Metrics Explained:**

        **Sources Found**
        - Total sources retrieved from web search
        - Represents the model's search results

        **Sources Used**
        - Citations from search results (have rank numbers)
        - Only sources actually from the web search
        - Used to calculate Average Rank

        **Extra Links**
        - Citations NOT from search results
        - URLs mentioned from model's training data
        - No rank number (weren't in search results)
        - Counted separately from Sources Used

        **Average Rank**
        - Mean position of cited sources in search results
        - Lower = model prefers higher-ranked sources
        - Only calculated from Sources Used

        **Important:**
        The model can cite URLs from two places:
        1. Web search results → counted as "Sources Used"
        2. Training knowledge → counted as "Extra Links"

        **For Google:**
        Sources Used may show 0 as Google's API doesn't separate citations from search results.
        """)

def main():
    """Main application logic."""
    initialize_session_state()

    # Header
    st.markdown('<div class="main-header">🔍 LLM Search Analysis</div>', unsafe_allow_html=True)

    # Sidebar
    sidebar_info()

    # Main tabs
    tab1, tab2, tab3 = st.tabs(["🎯 Interactive", "📦 Batch Analysis", "📜 History"])

    with tab1:
        tab_interactive()

    with tab2:
        tab_batch()

    with tab3:
        tab_history()

if __name__ == "__main__":
    main()
