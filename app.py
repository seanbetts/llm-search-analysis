"""
LLM Search Analysis - Streamlit UI

Interactive web interface for testing and analyzing LLM search capabilities
across OpenAI, Google Gemini, and Anthropic Claude models.
"""

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
        background-color: #e8f4f8;
        padding: 0.5rem 1rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
    .source-item {
        background-color: #f9f9f9;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
        border: 1px solid #e0e0e0;
    }
    .citation-item {
        background-color: #fff8e1;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
        border: 1px solid #ffd54f;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables."""
    if 'response' not in st.session_state:
        st.session_state.response = None
    if 'error' not in st.session_state:
        st.session_state.error = None
    if 'db' not in st.session_state:
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

def display_response(response):
    """Display the LLM response with search metadata."""

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
        'gpt-5-mini': 'GPT-5 Mini',
        'gpt-5-nano': 'GPT-5 Nano',
        # Google
        'gemini-3-pro-preview': 'Gemini 3 Pro (Preview)',
        'gemini-2.5-flash': 'Gemini 2.5 Flash',
        'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
    }

    # Data source indicator (if available from database)
    data_source = getattr(response, 'data_source', 'api')
    if data_source == 'network_log':
        st.info("📡 This response was captured from network logs (experimental mode)")

    # Response metadata
    st.markdown("### 📊 Response Metadata")
    col1, col2, col3, col4, col5, col6, col7 = st.columns([1.5, 2, 1, 1, 1, 1, 1])

    with col1:
        st.metric("Provider", provider_names.get(response.provider, response.provider.capitalize()))
    with col2:
        st.metric("Model", model_names.get(response.model, response.model))
    with col3:
        response_time = f"{response.response_time_ms / 1000:.1f}s" if response.response_time_ms else "N/A"
        st.metric("Response Time", response_time)
    with col4:
        st.metric("Search Queries", len(response.search_queries))
    with col5:
        st.metric("Sources Fetched", len(response.sources))
    with col6:
        st.metric("Sources Used", len(response.citations))
    with col7:
        # Calculate average rank from sources used (citations)
        sources_with_rank = [c for c in response.citations if c.rank]
        if sources_with_rank:
            avg_rank = sum(c.rank for c in sources_with_rank) / len(sources_with_rank)
            st.metric("Avg. Rank", f"{avg_rank:.1f}")
        else:
            st.metric("Avg. Rank", "N/A")

    st.divider()

    # Response text
    st.markdown("### 💬 Response")
    st.markdown(response.response_text)
    st.divider()

    # Search queries with their sources
    if response.search_queries:
        st.markdown("### 🔍 Search Queries & Sources")
        for i, query in enumerate(response.search_queries, 1):
            # Display query
            st.markdown(f"""
            <div class="search-query">
                <strong>Query {i}:</strong> {query.query}
            </div>
            """, unsafe_allow_html=True)

            # Display sources for this query in collapsible section
            if query.sources:
                with st.expander(f"📚 Sources from Query {i} ({len(query.sources)} sources)", expanded=False):
                    for j, source in enumerate(query.sources, 1):
                        url_display = source.url or 'No URL'
                        url_truncated = url_display[:80] + ('...' if len(url_display) > 80 else '')
                        # Use domain as title fallback when title is missing
                        display_title = source.title or source.domain or 'Unknown source'
                        st.markdown(f"""
                        <div class="source-item">
                            <strong>{j}. {display_title}</strong><br/>
                            <small>{source.domain or 'Unknown domain'}</small><br/>
                            <a href="{url_display}" target="_blank">{url_truncated}</a>
                        </div>
                        """, unsafe_allow_html=True)
        st.divider()

    # Sources used (from web search)
    if response.citations:
        st.markdown(f"### 📝 Sources Used ({len(response.citations)})")
        st.caption("Sources the model consulted via web search")

        for i, citation in enumerate(response.citations, 1):
            with st.container():
                url_display = citation.url or 'No URL'
                url_truncated = url_display[:80] + ('...' if len(url_display) > 80 else '')
                rank_display = f" (Rank {citation.rank})" if citation.rank else ""
                # Extract domain from URL for fallback
                domain = urlparse(citation.url).netloc if citation.url else 'Unknown domain'
                display_title = citation.title or domain or 'Unknown source'
                st.markdown(f"""
                <div class="citation-item">
                    <strong>{i}. {display_title}{rank_display}</strong><br/>
                    <a href="{url_display}" target="_blank">{url_truncated}</a>
                </div>
                """, unsafe_allow_html=True)

def tab_interactive():
    """Tab 1: Interactive Prompting."""
    st.markdown("### 💭 Enter Your Prompt")

    # Data collection mode toggle
    st.markdown("#### 📡 Data Collection Mode")
    mode_options = ["API (Recommended)", "Network Logs (Experimental)"]
    selected_mode = st.radio(
        "Choose data collection method:",
        mode_options,
        index=0 if st.session_state.data_collection_mode == 'api' else 1,
        help="API mode uses official provider APIs. Network Log mode captures browser traffic for deeper insights.",
        horizontal=True,
        label_visibility="collapsed"
    )

    # Update session state based on selection
    st.session_state.data_collection_mode = 'api' if selected_mode == mode_options[0] else 'network_log'

    # Show warning for network log mode
    if st.session_state.data_collection_mode == 'network_log':
        st.warning("""
        ⚠️ **Experimental Feature**

        Network Log mode operates in a legal gray area and is intended for personal research use only.
        This mode will launch a browser window and intercept traffic from your own account.

        **Note:** Currently only ChatGPT network capture is in development. Other providers coming soon.
        """)

        # Browser session management (placeholder for future implementation)
        st.info("🚧 Network log capture is not yet fully implemented. This mode will become functional in a future update.")

    st.divider()

    # Load all available models
    models = get_all_models()

    if not models:
        st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
        return

    # Model selection
    model_labels = list(models.keys())
    selected_label = st.selectbox(
        "Select Model",
        model_labels,
        help="Choose a model from any available provider"
    )

    # Extract provider and model from selection
    selected_provider, selected_model = models[selected_label]

    # Prompt input
    prompt = st.text_area(
        "Prompt",
        placeholder="What are the latest developments in artificial intelligence this week?",
        height=100,
        label_visibility="collapsed"
    )

    # Submit button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        submit_button = st.button("🚀 Submit Query", type="primary", use_container_width=True)

    # Handle submission
    if submit_button:
        if not prompt:
            st.warning("Please enter a prompt")
            return

        # Show loading state
        # Extract formatted model name from selected_label (format: "🟢 Provider - Model Name")
        formatted_model = selected_label.split(' - ', 1)[1] if ' - ' in selected_label else selected_model
        with st.spinner(f"Querying {formatted_model}..."):
            try:
                # Get API keys and create provider
                api_keys = Config.get_api_keys()
                provider = ProviderFactory.create_provider(selected_provider, api_keys[selected_provider])

                # Send prompt
                response = provider.send_prompt(prompt, selected_model)

                # Save to database
                try:
                    st.session_state.db.save_interaction(
                        provider_name=selected_provider,
                        model=selected_model,
                        prompt=prompt,
                        response_text=response.response_text,
                        search_queries=response.search_queries,
                        sources=response.sources,
                        citations=response.citations,
                        response_time_ms=response.response_time_ms,
                        raw_response=response.raw_response
                    )
                except Exception as db_error:
                    st.warning(f"Response saved but database error occurred: {str(db_error)}")

                # Store in session state
                st.session_state.response = response
                st.session_state.error = None

            except Exception as e:
                st.session_state.error = str(e)
                st.session_state.response = None

    # Display results
    if st.session_state.error:
        st.error(f"Error: {st.session_state.error}")

    if st.session_state.response:
        st.divider()
        display_response(st.session_state.response)

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
                    # Create provider for this model
                    provider = ProviderFactory.create_provider(provider_name, api_keys[provider_name])

                    # Send prompt
                    response = provider.send_prompt(prompt, model_name)

                    # Save to database
                    try:
                        st.session_state.db.save_interaction(
                            provider_name=provider_name,
                            model=model_name,
                            prompt=prompt,
                            response_text=response.response_text,
                            search_queries=response.search_queries,
                            sources=response.sources,
                            citations=response.citations,
                            response_time_ms=response.response_time_ms,
                            raw_response=response.raw_response
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
            display_df.columns = ['Prompt', 'Model', 'Searches', 'Sources', 'Sources Used',
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
    st.caption("View and search past interactions")

    # Get recent interactions
    try:
        interactions = st.session_state.db.get_recent_interactions(limit=100)

        if not interactions:
            st.info("No interactions recorded yet. Start by submitting prompts in the Interactive tab!")
            return

        # Convert to DataFrame
        df = pd.DataFrame(interactions)

        # Format timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # Truncate prompt for display
        df['prompt_preview'] = df['prompt'].str[:80] + df['prompt'].apply(lambda x: '...' if len(x) > 80 else '')

        # Search filter
        search_query = st.text_input("🔍 Search prompts", placeholder="Enter keywords to filter...")

        if search_query:
            df = df[df['prompt'].str.contains(search_query, case=False, na=False)]
            st.caption(f"Showing {len(df)} matching results")

        # Format average rank for display
        df['avg_rank_display'] = df['avg_rank'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")

        # Display table
        display_df = df[['timestamp', 'prompt_preview', 'provider', 'model', 'searches', 'sources', 'citations', 'avg_rank_display']]
        display_df.columns = ['Timestamp', 'Prompt', 'Provider', 'Model', 'Searches', 'Sources', 'Sources Used', 'Avg. Rank']

        st.dataframe(display_df, use_container_width=True, height=400)

        # Export button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Export History as CSV",
            data=csv,
            file_name=f"query_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        # View details
        st.markdown("#### View Interaction Details")
        selected_id = st.selectbox(
            "Select an interaction to view details",
            options=df['id'].tolist(),
            format_func=lambda x: f"ID {x}: {df[df['id'] == x]['prompt_preview'].values[0]}"
        )

        if selected_id:
            details = st.session_state.db.get_interaction_details(selected_id)
            if details:
                st.divider()
                st.markdown(f"**Prompt:** {details['prompt']}")

                # Calculate metrics
                num_searches = len(details['search_queries'])
                num_sources = sum(len(query['sources']) for query in details['search_queries'])
                num_sources_used = len(details['citations'])

                citations_with_rank = [c for c in details['citations'] if c.get('rank') is not None]
                avg_rank_display = f"{sum(c['rank'] for c in citations_with_rank) / len(citations_with_rank):.1f}" if citations_with_rank else "N/A"

                # Convert response time to seconds
                response_time_s = f"{details['response_time_ms'] / 1000:.1f}s"

                st.markdown(f"**Provider:** {details['provider']} | **Model:** {details['model']} | **Time:** {response_time_s}")
                st.markdown(f"**Searches:** {num_searches} | **Sources:** {num_sources} | **Sources Used:** {num_sources_used} | **Avg. Rank:** {avg_rank_display}")

                st.markdown("**Response:**")
                st.markdown(details['response_text'])

                if details['search_queries']:
                    st.markdown(f"**Search Queries ({len(details['search_queries'])}):**")
                    for i, query in enumerate(details['search_queries'], 1):
                        st.markdown(f"{i}. {query['query']} ({len(query['sources'])} sources)")

                if details['citations']:
                    st.markdown(f"**Sources Used ({len(details['citations'])}):**")
                    for i, citation in enumerate(details['citations'], 1):
                        rank_display = f" (Rank {citation['rank']})" if citation.get('rank') else ""
                        # Extract domain from URL for fallback
                        domain = urlparse(citation['url']).netloc if citation.get('url') else 'Unknown domain'
                        display_title = citation.get('title') or domain or 'Unknown source'
                        st.markdown(f"{i}. [{display_title}]({citation['url']}){rank_display}")

    except Exception as e:
        st.error(f"Error loading history: {str(e)}")

def sidebar_info():
    """Sidebar information."""
    st.sidebar.title("⚙️ Configuration")

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

    # Understanding Sources Used section
    with st.sidebar.expander("📚 Understanding Sources Used", expanded=False):
        st.markdown("""
        **Important Nuances:**

        **"Sources Used"** tracks sources the model actually searched for via web search APIs, not all URLs in the response.

        **Three scenarios you may see:**

        1. **Source used + URL in response**
           - Normal case: model searched and cited

        2. **Source used + No URL in response**
           - Model used search but didn't show URL in text
           - Still counted as source used

        3. **No source used + URL in response**
           - Model mentioned URL from training knowledge
           - Not counted (didn't actually search for it)

        **For Google:**
        - Sources Used = 0 (cannot distinguish from Sources Fetched)
        - Google's API doesn't separate them

        This means "Sources Used" measures **sources consulted via search**, not **URLs mentioned in text**.
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
