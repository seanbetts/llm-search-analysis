"""Web (network log) interactive tab."""

import streamlit as st

from frontend.components.response import display_response
from frontend.config import Config
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.interactive import build_web_response
from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer
from frontend.helpers.serialization import namespace_to_dict

RESPONSE_KEY = "web_response"
ERROR_KEY = "web_error"
PROMPT_KEY = "web_prompt"


def tab_web():
  """Render the web capture interactive tab."""
  st.session_state.setdefault(RESPONSE_KEY, None)
  st.session_state.setdefault(ERROR_KEY, None)
  st.session_state.setdefault(PROMPT_KEY, None)
  st.session_state.setdefault('network_show_browser', False)

  st.markdown("### 🌐 Web Testing")

  st.checkbox(
    "Show browser window",
    value=st.session_state.network_show_browser,
    key="network_show_browser",
    help="Uncheck to run headless for faster captures."
  )

  prompt = st.chat_input("Prompt (Enter to send, Shift+Enter for new line)", key="web_prompt_input")
  if prompt is not None:
    trimmed_prompt = prompt.strip()
    if not trimmed_prompt:
      st.warning("Please enter a prompt")
    else:
      status_placeholder = st.empty()

      try:
        with status_placeholder.container():
          with st.status("Analyzing with web capture...", expanded=True):
            status_container = st.empty()

            def update_status(message: str):
              status_container.write(message)

            capturer = ChatGPTCapturer(status_callback=update_status)
            try:
              headless = not st.session_state.network_show_browser
              capturer.start_browser(headless=headless)
              capturer.authenticate(
                email=Config.CHATGPT_EMAIL if Config.CHATGPT_EMAIL else None,
                password=Config.CHATGPT_PASSWORD if Config.CHATGPT_PASSWORD else None
              )
              provider_response = capturer.send_prompt(trimmed_prompt, "chatgpt-free")
            finally:
              try:
                capturer.stop_browser()
              except Exception:
                pass

        response_ns = build_web_response(provider_response)

        _, save_error = safe_api_call(
          st.session_state.api_client.save_network_log,
          provider=response_ns.provider,
          model=response_ns.model,
          prompt=trimmed_prompt,
          response_text=response_ns.response_text,
          search_queries=namespace_to_dict(response_ns.search_queries),
          sources=namespace_to_dict(response_ns.all_sources),
          citations=namespace_to_dict(response_ns.citations),
          response_time_ms=response_ns.response_time_ms,
          raw_response=response_ns.raw_response,
          extra_links_count=response_ns.extra_links_count,
          show_spinner=False
        )

        if save_error:
          st.warning(f"Response captured but failed to save: {save_error}")

        st.session_state[RESPONSE_KEY] = response_ns
        st.session_state[PROMPT_KEY] = trimmed_prompt
        st.session_state[ERROR_KEY] = None

      except Exception as exc:
        st.session_state[ERROR_KEY] = f"Unexpected error: {exc}"
        st.session_state[RESPONSE_KEY] = None
      finally:
        status_placeholder.empty()

  if st.session_state[ERROR_KEY]:
    st.error(f"Error: {st.session_state[ERROR_KEY]}")

  if st.session_state[RESPONSE_KEY]:
    display_response(
      st.session_state[RESPONSE_KEY],
      st.session_state.get(PROMPT_KEY),
    )
