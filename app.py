"""Streamlit UI for the LLM Search Analysis app."""

import os

import streamlit as st

from frontend.api_client import APIClient
from frontend.styles import load_styles
from frontend.tabs import tab_batch, tab_history, tab_interactive

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
        help=(
            "API mode uses official provider APIs. "
            "Network Log mode captures browser traffic for deeper insights."
        ),
        label_visibility="collapsed"
    )

    # Update session state based on selection
    st.session_state.data_collection_mode = (
        'api' if selected_mode == mode_options[0] else 'network_log'
    )

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
        Network logs provide internal scores, snippet text, and query reformulation
        data not available via API.

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
