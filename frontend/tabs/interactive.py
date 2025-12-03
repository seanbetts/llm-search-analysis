"""Interactive tab for single prompt testing."""

import streamlit as st
from types import SimpleNamespace
from src.config import Config
from frontend.components.models import get_all_models
from frontend.components.response import display_response
from frontend.api_client import APINotFoundError, APIClientError


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
