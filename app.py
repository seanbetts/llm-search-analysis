"""
LLM Search Analysis - Streamlit UI

Interactive web interface for testing and analyzing LLM search capabilities
across OpenAI, Google Gemini, and Anthropic Claude models.
"""

import os
import re
import traceback
import streamlit as st
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse
from src.config import Config
from frontend.api_client import APIClient, APIClientError, APINotFoundError
from frontend.styles import load_styles
from frontend.utils import format_pub_date
from frontend.components.response import (
  sanitize_response_markdown,
  format_response_text,
  extract_images_from_response
)
from frontend.components.models import get_all_models

# Page config
st.set_page_config(
    page_title="LLM Search Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS styles
load_styles()

def initialize_session_state():
    """Initialize session state variables."""
    if 'response' not in st.session_state:
        st.session_state.response = None
    if 'prompt' not in st.session_state:
        st.session_state.prompt = None
    if 'error' not in st.session_state:
        st.session_state.error = None
    if 'api_client' not in st.session_state:
        # Initialize API client
        # Use API_BASE_URL from environment (Docker) or default to localhost (local dev)
        api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        st.session_state.api_client = APIClient(
            base_url=api_base_url,
            timeout_send_prompt=120.0
        )
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = []
    if 'data_collection_mode' not in st.session_state:
        st.session_state.data_collection_mode = 'api'
    if 'browser_session_active' not in st.session_state:
        st.session_state.browser_session_active = False
    if 'network_show_browser' not in st.session_state:
        st.session_state.network_show_browser = False  # Default: headless mode (browser hidden)


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
            total_sources = sum(len(q.sources) for q in queries_with_sources)
            st.markdown(f"### 📚 Sources Found ({total_sources}):")
            for i, query in enumerate(queries_with_sources, 1):
                # Truncate long queries for display
                query_text = query.query if len(query.query) <= 60 else query.query[:60] + "..."
                with st.expander(f"📚 {query_text} ({len(query.sources)} sources)", expanded=False):
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
        st.checkbox("Show browser window", value=st.session_state.network_show_browser, key="network_show_browser",
                   help="Check to see the browser window (may help with CAPTCHA). Unchecked runs in headless mode (faster, hidden).")
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
                    capturer.start_browser(headless=not st.session_state.network_show_browser)

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
                    # Use API client to send prompt (handles provider call AND database save)
                    response_data = st.session_state.api_client.send_prompt(
                        prompt=prompt,
                        provider=selected_provider,
                        model=selected_model,
                        data_mode="api",
                        headless=True
                    )

                    # Convert API response dict to object for display_response function
                    from types import SimpleNamespace

                    # Convert search queries
                    search_queries = []
                    for query_data in response_data.get('search_queries', []):
                        sources = [SimpleNamespace(**src) for src in query_data.get('sources', [])]
                        search_query = SimpleNamespace(
                            query=query_data.get('query'),
                            sources=sources,
                            timestamp=query_data.get('timestamp'),
                            order_index=query_data.get('order_index')
                        )
                        search_queries.append(search_query)

                    # Convert citations
                    citations = [SimpleNamespace(**citation) for citation in response_data.get('citations', [])]

                    # Convert sources - backend now provides all_sources for both modes
                    all_sources = [SimpleNamespace(**src) for src in response_data.get('all_sources', [])]

                    # Create response object
                    response = SimpleNamespace(
                        provider=response_data.get('provider'),
                        model=response_data.get('model'),
                        response_text=response_data.get('response_text'),
                        search_queries=search_queries,
                        all_sources=all_sources,
                        citations=citations,
                        response_time_ms=response_data.get('response_time_ms'),
                        data_source=response_data.get('data_source', 'api'),
                        extra_links_count=response_data.get('extra_links_count', 0),
                        raw_response=response_data.get('raw_response', {})
                    )

                # Store in session state
                st.session_state.response = response
                st.session_state.prompt = prompt
                st.session_state.error = None

            except APINotFoundError as e:
                st.session_state.error = f"Resource not found: {str(e)}"
                st.session_state.response = None
            except APIClientError as e:
                # Handle various API client errors with user-friendly messages
                error_msg = str(e)
                if "timed out" in error_msg.lower():
                    st.session_state.error = f"Request timed out. The model may be taking too long to respond. Please try again."
                elif "connect" in error_msg.lower() or "connection" in error_msg.lower():
                    st.session_state.error = f"Cannot connect to API server. Please ensure the backend is running on http://localhost:8000"
                elif "validation" in error_msg.lower():
                    st.session_state.error = f"Invalid request: {error_msg}"
                else:
                    st.session_state.error = f"API error: {error_msg}"
                st.session_state.response = None
            except Exception as e:
                st.session_state.error = f"Unexpected error: {str(e)}"
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
                        capturer = ChatGPTCapturer()
                        capturer.start_browser(headless=not st.session_state.network_show_browser)

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
                        # Use API client to send prompt (handles provider call AND database save)
                        response_data = st.session_state.api_client.send_prompt(
                            prompt=prompt,
                            provider=provider_name,
                            model=model_name,
                            data_mode="api",
                            headless=True
                        )

                    # Store result using backend-computed metrics
                    if st.session_state.data_collection_mode == 'api':
                        # For API mode, use backend-computed metrics from response_data dict
                        st.session_state.batch_results.append({
                            'prompt': prompt,
                            'model': model_label,
                            'searches': len(response_data.get('search_queries', [])),
                            'sources': response_data.get('sources_found', 0),
                            'sources_used': response_data.get('sources_used', 0),
                            'avg_rank': response_data.get('avg_rank'),
                            'response_time_s': response_data.get('response_time_ms', 0) / 1000
                        })
                    else:
                        # For network log mode, use backend-computed metrics from response object
                        st.session_state.batch_results.append({
                            'prompt': prompt,
                            'model': model_label,
                            'searches': len(response.search_queries),
                            'sources': getattr(response, 'sources_found', 0),
                            'sources_used': getattr(response, 'sources_used', 0),
                            'avg_rank': getattr(response, 'avg_rank', None),
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
        interactions = st.session_state.api_client.get_recent_interactions(limit=100)

        if not interactions:
            st.info("No interactions recorded yet. Start by submitting prompts in the Interactive tab!")
            return

        # Convert to DataFrame
        df = pd.DataFrame(interactions)

        # Rename API response columns to match expected column names
        df = df.rename(columns={
            'interaction_id': 'id',
            'created_at': 'timestamp',
            'search_query_count': 'searches',
            'source_count': 'sources',
            'citation_count': 'citations',
            'average_rank': 'avg_rank',
            'extra_links_count': 'extra_links'
        })

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

        # Use backend-provided model_display_name (Phase 1.2)
        # Fallback to raw model name if display name not available
        df['model_display'] = df.apply(
            lambda row: row.get('model_display_name') or row['model'] if pd.notna(row.get('model')) else row.get('model'),
            axis=1
        )

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
            # Get unique display names (Phase 1.2: now from backend)
            model_display_options_df = df[['model', 'model_display']].drop_duplicates()
            # Create mapping: "Display Name" -> "raw-model-id"
            model_display_options = {
                row['model_display']: row['model']
                for _, row in model_display_options_df.iterrows()
                if pd.notna(row['model'])
            }
            model_display_options = dict(sorted(model_display_options.items()))
            selected_model_displays = st.multiselect(
                "Model",
                options=list(model_display_options.keys()),
                default=list(model_display_options.keys()),
            ) if model_display_options else []
            # Convert selected display names back to raw model IDs for filtering
            selected_models = [model_display_options[d] for d in selected_model_displays]

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

        display_df = df[['id', 'timestamp', 'analysis_type', 'prompt_preview', 'provider', 'model_display', 'searches', 'sources', 'citations', 'avg_rank_display', 'extra_links']]
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
            details = st.session_state.api_client.get_interaction(selected_id)
            if details:
                # Download interaction as markdown (placed directly after selector)
                md_export = st.session_state.api_client.export_interaction_markdown(selected_id)
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
                                deleted = st.session_state.api_client.delete_interaction(selected_id)
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
                num_searches = len(details.get('search_queries', []))
                # For network logs, sources are in all_sources; for API, they're in query.sources
                if details.get('data_source') == 'network_log':
                    num_sources = len(details.get('all_sources') or [])
                else:
                    num_sources = sum(len(query.get('sources', [])) for query in details.get('search_queries', []))
                # Count only citations with ranks (from search results)
                citations_with_rank = [c for c in details.get('citations', []) if c.get('rank') is not None]
                num_sources_used = len(citations_with_rank)
                avg_rank_display = f"{sum(c['rank'] for c in citations_with_rank) / len(citations_with_rank):.1f}" if citations_with_rank else "N/A"
                response_time_s = f"{details['response_time_ms'] / 1000:.1f}s"
                # Extra links from stored value; fallback to citations without rank
                extra_links_count = details.get('extra_links', len([c for c in details.get('citations', []) if not c.get('rank')]))
                # Response metadata
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1.5, 2, 1, 1, 1, 1, 1, 1])

                # Provider display names
                provider_names = {
                    'openai': 'OpenAI',
                    'google': 'Google',
                    'anthropic': 'Anthropic'
                }

                with col1:
                    st.metric("Provider", provider_names.get(details['provider'].lower(), details['provider']))
                with col2:
                    # Use backend-provided model_display_name (Phase 1.2)
                    model_display = details.get('model_display_name') or details['model']
                    st.metric("Model", model_display)
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

                if details.get('search_queries'):
                    st.markdown(f"### 🔍 Search Queries ({len(details.get('search_queries', []))}):")
                    for i, query in enumerate(details.get('search_queries', []), 1):
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
                        # Calculate total sources count
                        total_sources_count = sum(len(q.get('sources', [])) for q in details.get('search_queries', []))
                        st.markdown(f"### 📚 Sources Found ({total_sources_count}):")
                        for i, query in enumerate(details.get('search_queries', []), 1):
                            query_sources = query.get('sources', [])
                            if query_sources:
                                # Truncate long queries for display
                                query_text = query.get('query', '')
                                query_display = query_text if len(query_text) <= 60 else query_text[:60] + "..."
                                with st.expander(f"{query_display} ({len(query_sources)} sources)", expanded=False):
                                    for j, src in enumerate(query_sources, 1):
                                        url_display = src.get('url') or 'No URL'
                                        # Use domain as title fallback when title is missing
                                        display_title = src.get('title') or src.get('domain') or 'Unknown source'
                                        snippet = src.get('snippet_text') or src.get('snippet')
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
                    else:
                        # Network Log: Sources aren't associated with specific queries
                        all_sources = details.get('all_sources') or []
                        if all_sources:
                            st.markdown(f"### 📚 Sources Found ({len(all_sources)}):")
                            st.caption("_Note: Network logs don't provide reliable query-to-source mapping._")
                            with st.expander(f"View all {len(all_sources)} sources", expanded=False):
                                for j, src in enumerate(all_sources, 1):
                                    url_display = src.get('url') or 'No URL'
                                    # Use domain as title fallback when title is missing
                                    display_title = src.get('title') or src.get('domain') or 'Unknown source'
                                    snippet = src.get('snippet_text') or src.get('snippet')
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
                citations_with_rank = [c for c in details.get('citations', []) if c.get('rank')]
                if citations_with_rank:
                    st.divider()
                    st.markdown(f"### 📝 Sources Used ({len(citations_with_rank)}):")
                    st.caption("Sources the model consulted via web search")

                    # Build URL -> source lookup for metadata fallback
                    all_sources = details.get('all_sources') or []
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
                                    snippet = snippet or source_fallback.get('snippet_text') or source_fallback.get('snippet')
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
                extra_links = [c for c in details.get('citations', []) if not c.get('rank')]
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
        st.error(f"Traceback: {traceback.format_exc()}")

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
        - Opens a Chrome browser (hidden by default)
        - Navigates to ChatGPT automatically
        - Submits your prompt
        - Captures network traffic with metadata
        - Closes browser when done

        **Features:**
        - Runs in headless mode by default (faster)
        - Session persistence (stays logged in)
        - Captures internal ranking scores
        - Records query reformulations
        - Optional browser window display (may help with CAPTCHA)

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
