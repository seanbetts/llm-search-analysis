"""
LLM Search Analysis - Streamlit UI

Interactive web interface for testing and analyzing LLM search capabilities
across OpenAI, Google Gemini, and Anthropic Claude models.
"""

import streamlit as st
from src.config import Config
from src.providers.provider_factory import ProviderFactory

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

        for provider_name in ['openai', 'google', 'anthropic']:
            if api_keys.get(provider_name):
                provider = ProviderFactory.create_provider(provider_name, api_keys[provider_name])
                for model in provider.get_supported_models():
                    # Create label: "🟢 OpenAI - gpt-5.1"
                    label = f"{provider_labels[provider_name]} - {model}"
                    models[label] = (provider_name, model)

        return models
    except Exception as e:
        st.error(f"Error loading models: {str(e)}")
        return {}

def display_response(response):
    """Display the LLM response with search metadata."""

    # Response metadata
    st.markdown("### 📊 Response Metadata")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Provider", response.provider.upper())
    with col2:
        st.metric("Model", response.model)
    with col3:
        response_time = f"{response.response_time_ms / 1000:.2f}s" if response.response_time_ms else "N/A"
        st.metric("Response Time", response_time)
    with col4:
        st.metric("Search Queries", len(response.search_queries))
    with col5:
        st.metric("Sources Fetched", len(response.sources))
    with col6:
        st.metric("Citations Used", len(response.citations))

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
                        st.markdown(f"""
                        <div class="source-item">
                            <strong>{j}. {source.title or 'Untitled'}</strong><br/>
                            <small>{source.domain or 'Unknown domain'}</small><br/>
                            <a href="{url_display}" target="_blank">{url_truncated}</a>
                        </div>
                        """, unsafe_allow_html=True)
        st.divider()

    # Citations
    if response.citations:
        st.markdown(f"### 📝 Citations Used ({len(response.citations)})")
        st.caption("Sources actually cited in the response")

        for i, citation in enumerate(response.citations, 1):
            with st.container():
                url_display = citation.url or 'No URL'
                url_truncated = url_display[:80] + ('...' if len(url_display) > 80 else '')
                st.markdown(f"""
                <div class="citation-item">
                    <strong>{i}. {citation.title or 'Untitled'}</strong><br/>
                    <a href="{url_display}" target="_blank">{url_truncated}</a>
                </div>
                """, unsafe_allow_html=True)

def main():
    """Main application logic."""
    initialize_session_state()

    # Header
    st.markdown('<div class="main-header">🔍 LLM Search Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Compare search capabilities across OpenAI, Google Gemini, and Anthropic Claude</div>', unsafe_allow_html=True)

    # Sidebar - Model Selection
    st.sidebar.title("⚙️ Configuration")

    # Load all available models
    models = get_all_models()

    if not models:
        st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
        st.stop()

    # Model selection with provider labels
    model_labels = list(models.keys())
    selected_label = st.sidebar.selectbox(
        "Select Model",
        model_labels,
        help="Choose a model from any available provider"
    )

    # Extract provider and model from selection
    selected_provider, selected_model = models[selected_label]

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

    # Main content - Prompt input
    st.markdown("### 💭 Enter Your Prompt")

    # Prompt input
    prompt = st.text_area(
        placeholder="What are the latest developments in artificial intelligence this week?",
        height=100
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
        with st.spinner(f"Querying {selected_model}..."):
            try:
                # Get API keys and create provider
                api_keys = Config.get_api_keys()
                provider = ProviderFactory.create_provider(selected_provider, api_keys[selected_provider])

                # Send prompt
                response = provider.send_prompt(prompt, selected_model)

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

if __name__ == "__main__":
    main()
