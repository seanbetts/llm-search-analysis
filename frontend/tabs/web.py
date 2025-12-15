"""Web (network log) interactive tab."""

import streamlit as st

from frontend.components.response import display_response
from frontend.config import Config
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.interactive import build_api_response, build_web_response
from frontend.helpers.serialization import namespace_to_dict
from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer

RESPONSE_KEY = "web_response"
ERROR_KEY = "web_error"
PROMPT_KEY = "web_prompt"
TAGGING_KEY = "web_enable_citation_tagging"


def tab_web():
  """Render the web capture interactive tab."""
  st.session_state.setdefault(RESPONSE_KEY, None)
  st.session_state.setdefault(ERROR_KEY, None)
  st.session_state.setdefault(PROMPT_KEY, None)
  st.session_state.setdefault('network_show_browser', False)
  st.session_state.setdefault(TAGGING_KEY, True)

  st.markdown("### 🌐 Web Testing")

  st.checkbox(
    "Show browser window",
    key="network_show_browser",
    help="Uncheck to run headless for faster captures."
  )

  st.checkbox(
    "Enable citation tagging",
    key=TAGGING_KEY,
    help="Runs in the background after saving (adds tags and influence summaries)."
  )

  prompt = st.chat_input("Prompt (Enter to send, Shift+Enter for new line)", key="web_prompt_input")
  if prompt is not None:
    trimmed_prompt = prompt.strip()
    if not trimmed_prompt:
      st.warning("Please enter a prompt")
    else:
      status_placeholder = st.empty()
      saved_payload = None
      save_error = None
      response_ns = None

      try:
        with status_placeholder.container():
          with st.status("Analyzing with web capture...", expanded=True) as status:
            status_container = st.empty()

            def update_status(message: str):
              """Write browser status updates to the status container."""
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

            status_container.write("Processing captured response...")
            response_ns = build_web_response(provider_response)

            status_container.write("Saving capture (citation tagging will run in the background)...")
            saved_payload, save_error = safe_api_call(
              st.session_state.api_client.save_network_log,
              provider=response_ns.provider,
              model=response_ns.model,
              prompt=trimmed_prompt,
              response_text=response_ns.response_text,
              search_queries=namespace_to_dict(response_ns.search_queries),
              sources=namespace_to_dict(response_ns.all_sources),
              citations=namespace_to_dict(response_ns.citations),
              response_time_ms=response_ns.response_time_ms,
              enable_citation_tagging=st.session_state.get(TAGGING_KEY, True),
              raw_response=response_ns.raw_response,
              extra_links_count=response_ns.extra_links_count,
              show_spinner=False
            )

            if save_error:
              status.update(label="Web analysis complete (save failed)", state="error")
            else:
              annotations = None
              citation_status = None
              citation_error = None
              if isinstance(saved_payload, dict):
                metadata = saved_payload.get("metadata") or {}
                annotations = metadata.get("citation_annotations")
                citation_status = metadata.get("citation_tagging_status")
                citation_error = metadata.get("citation_tagging_error")
              if isinstance(annotations, dict):
                annotated = annotations.get("annotated_citations")
                total = annotations.get("total_citations")
                if annotated is not None and total is not None:
                  if citation_status == "queued":
                    status_container.write(f"⏳ Citation tagging queued: {annotated}/{total} annotated so far.")
                  elif citation_status == "completed":
                    status_container.write(f"✅ Citation annotations saved: {annotated}/{total} citations annotated.")
                  elif citation_status == "failed":
                    status_container.write("⚠️ Citation tagging failed (see History for details).")
                  elif citation_status == "disabled":
                    status_container.write("ℹ️ Citation tagging is disabled.")
                  else:
                    status_container.write(f"ℹ️ Citation tagging status: {citation_status or 'unknown'}")
              if citation_error:
                status_container.write(f"⚠️ Citation tagging error: {citation_error}")
              status.update(label="Web analysis complete", state="complete")

        if save_error:
          st.warning(f"Response captured but failed to save: {save_error}")
        elif saved_payload and response_ns is not None:
          response_ns = build_api_response(saved_payload)

        if response_ns is not None:
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
