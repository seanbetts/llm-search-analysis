"""Interactive tab for single prompt testing."""

import streamlit as st
from types import SimpleNamespace
from frontend.config import Config
from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer
from frontend.components.models import get_all_models
from frontend.components.response import display_response
from frontend.api_client import APINotFoundError, APIClientError
from frontend.helpers.metrics import compute_metrics, get_model_display_name
from frontend.helpers.serialization import namespace_to_dict


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
        if st.session_state.data_collection_mode == 'network_log':
          # NETWORK_LOG MODE: Use ChatGPTCapturer directly (runs on host machine)
          # Initialize capturer
          capturer = ChatGPTCapturer()

          try:
            # Start browser
            headless = not st.session_state.network_show_browser
            capturer.start_browser(headless=headless)

            # Authenticate (anonymous mode if no credentials)
            capturer.authenticate(
              email=Config.CHATGPT_EMAIL if Config.CHATGPT_EMAIL else None,
              password=Config.CHATGPT_PASSWORD if Config.CHATGPT_PASSWORD else None
            )

            # Send prompt and get response
            provider_response = capturer.send_prompt(prompt, selected_model)

          finally:
            # Always stop browser
            try:
              capturer.stop_browser()
            except:
              pass

          # Convert ProviderResponse to display format
          search_queries = []
          for query in provider_response.search_queries:
            sources = [SimpleNamespace(
              url=s.url,
              title=s.title,
              domain=s.domain,
              rank=s.rank,
              pub_date=s.pub_date,
              snippet_text=s.snippet_text,
              internal_score=s.internal_score,
              metadata=s.metadata
            ) for s in query.sources]

            search_queries.append(SimpleNamespace(
              query=query.query,
              sources=sources,
              timestamp=query.timestamp,
              order_index=query.order_index
            ))

          citations = [SimpleNamespace(
            url=c.url,
            title=c.title,
            rank=c.rank,
            snippet_used=c.snippet_used,
            citation_confidence=c.citation_confidence,
            metadata=c.metadata
          ) for c in provider_response.citations]

          all_sources = [SimpleNamespace(
            url=s.url,
            title=s.title,
            domain=s.domain,
            rank=s.rank,
            pub_date=s.pub_date,
            snippet_text=s.snippet_text,
            internal_score=s.internal_score,
            metadata=s.metadata
          ) for s in provider_response.sources]

          # Compute metrics using shared helper
          metrics = compute_metrics(search_queries, citations, all_sources)

          # Create response object with computed metrics
          response = SimpleNamespace(
            provider=provider_response.provider,
            model=provider_response.model,
            model_display_name=get_model_display_name(provider_response.model),
            response_text=provider_response.response_text,
            search_queries=search_queries,
            all_sources=all_sources,
            citations=citations,
            response_time_ms=provider_response.response_time_ms,
            data_source='network_log',
            sources_found=metrics['sources_found'],
            sources_used=metrics['sources_used'],
            avg_rank=metrics['avg_rank'],
            extra_links_count=metrics['extra_links_count'],
            raw_response=provider_response.raw_response
          )

          # Save to database via backend API
          # Convert SimpleNamespace objects to dicts for JSON serialization
          st.session_state.api_client.save_network_log(
            provider=provider_response.provider,
            model=provider_response.model,
            prompt=prompt,
            response_text=provider_response.response_text,
            search_queries=namespace_to_dict(search_queries),
            sources=namespace_to_dict(all_sources),
            citations=namespace_to_dict(citations),
            response_time_ms=provider_response.response_time_ms,
            raw_response=provider_response.raw_response,
            extra_links_count=metrics['extra_links_count']
          )

        else:
          # API MODE: Use backend API (returns all computed metrics)
          response_data = st.session_state.api_client.send_prompt(
            prompt=prompt,
            provider=selected_provider,
            model=selected_model
          )

          # Convert API response dict to object for display_response function
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

          # Convert sources
          all_sources = [SimpleNamespace(**src) for src in response_data.get('all_sources', [])]

          # Create response object with all backend fields
          response = SimpleNamespace(
            provider=response_data.get('provider'),
            model=response_data.get('model'),
            model_display_name=response_data.get('model_display_name'),
            response_text=response_data.get('response_text'),
            search_queries=search_queries,
            all_sources=all_sources,
            citations=citations,
            response_time_ms=response_data.get('response_time_ms'),
            data_source=response_data.get('data_source', 'api'),
            # Computed metrics from backend
            sources_found=response_data.get('sources_found', 0),
            sources_used=response_data.get('sources_used', 0),
            avg_rank=response_data.get('avg_rank'),
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
