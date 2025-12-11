"""Streamlit UI for the LLM Search Analysis app."""

import os

import streamlit as st

from frontend.api_client import APIClient
from frontend.styles import load_styles
from frontend.tabs import tab_api, tab_batch, tab_history, tab_web

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
    if 'browser_session_active' not in st.session_state:
        st.session_state.browser_session_active = False
    if 'network_show_browser' not in st.session_state:
        st.session_state.network_show_browser = False  # Default: headless mode (browser hidden)



def sidebar_info():
    """Sidebar information."""

    st.sidebar.markdown('<div class="main-header">🔍 LLM Search Analysis</div>', unsafe_allow_html=True)
    st.sidebar.divider()

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
        - URLs mentioned from the model's training data
        - Counted separately from Sources Used

        **Average Rank**
        - Mean position of cited sources in search results
        - Lower = model prefers higher-ranked sources

        **Important:**
        The model can cite URLs from two places:
        1. Web search results → counted as "Sources Used"
        2. Training knowledge → counted as "Extra Links"
        """)


def main():
    """Main application logic."""
    initialize_session_state()

    # Sidebar
    sidebar_info()

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🌐 Web",
        "🎯 API",
        "📦 Batch Analysis",
        "📜 History",
    ])

    with tab1:
        tab_web()

    with tab2:
        tab_api()

    with tab3:
        tab_batch()

    with tab4:
        tab_history()

if __name__ == "__main__":
    main()
