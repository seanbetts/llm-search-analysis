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

def get_provider_models():
    """Get available providers and their models."""
    try:
        api_keys = Config.get_api_keys()
        providers = {}

        for provider_name in ['openai', 'google', 'anthropic']:
            if api_keys.get(provider_name):
                provider = ProviderFactory.create_provider(provider_name, api_keys[provider_name])
                providers[provider_name] = provider.get_supported_models()

        return providers
    except Exception as e:
        st.error(f"Error loading providers: {str(e)}")
        return {}

def display_response(response):
    """Display the LLM response with search metadata."""

    # Response metadata
    st.markdown("### 📊 Response Metadata")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Provider", response.provider.upper())
    with col2:
        st.metric("Model", response.model)
    with col3:
        st.metric("Response Time", f"{response.response_time_ms}ms" if response.response_time_ms else "N/A")
    with col4:
        st.metric("Search Queries", len(response.search_queries))

    st.divider()

    # Search queries
    if response.search_queries:
        st.markdown("### 🔍 Search Queries")
        for i, query in enumerate(response.search_queries, 1):
            st.markdown(f"""
            <div class="search-query">
                <strong>Query {i}:</strong> {query.query}
            </div>
            """, unsafe_allow_html=True)
        st.divider()

    # Response text
    st.markdown("### 💬 Response")
    st.markdown(response.response_text)
    st.divider()

    # Sources
    if response.sources:
        st.markdown(f"### 📚 Sources Fetched ({len(response.sources)})")
        st.caption("All sources retrieved during the search process")

        for i, source in enumerate(response.sources, 1):
            with st.container():
                st.markdown(f"""
                <div class="source-item">
                    <strong>{i}. {source.title or 'Untitled'}</strong><br/>
                    <small>{source.domain or 'Unknown domain'}</small><br/>
                    <a href="{source.url}" target="_blank">{source.url[:80]}{'...' if len(source.url) > 80 else ''}</a>
                </div>
                """, unsafe_allow_html=True)
        st.divider()

    # Citations
    if response.citations:
        st.markdown(f"### 📝 Citations Used ({len(response.citations)})")
        st.caption("Sources actually cited in the response")

        for i, citation in enumerate(response.citations, 1):
            with st.container():
                st.markdown(f"""
                <div class="citation-item">
                    <strong>{i}. {citation.title or 'Untitled'}</strong><br/>
                    <a href="{citation.url}" target="_blank">{citation.url[:80]}{'...' if len(citation.url) > 80 else ''}</a>
                </div>
                """, unsafe_allow_html=True)

def main():
    """Main application logic."""
    initialize_session_state()

    # Header
    st.markdown('<div class="main-header">🔍 LLM Search Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Compare search capabilities across OpenAI, Google Gemini, and Anthropic Claude</div>', unsafe_allow_html=True)

    # Sidebar - Provider and Model Selection
    st.sidebar.title("⚙️ Configuration")

    # Load providers and models
    providers = get_provider_models()

    if not providers:
        st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
        st.stop()

    # Provider selection
    provider_names = list(providers.keys())
    provider_labels = {
        'openai': '🟢 OpenAI',
        'google': '🔵 Google Gemini',
        'anthropic': '🟣 Anthropic Claude'
    }

    selected_provider = st.sidebar.selectbox(
        "Select Provider",
        provider_names,
        format_func=lambda x: provider_labels.get(x, x)
    )

    # Model selection
    available_models = providers[selected_provider]
    selected_model = st.sidebar.selectbox(
        "Select Model",
        available_models
    )

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
        "Ask a question that requires current information",
        placeholder="What are the latest developments in artificial intelligence this week?",
        height=100,
        help="The model will search the web to answer your question"
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
