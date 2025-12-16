"""Web (network log) interactive tab."""

import time

import streamlit as st

from frontend.components.response import display_response
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.interactive import build_api_response, build_web_response
from frontend.helpers.markdown_export import render_markdown_download_button
from frontend.helpers.serialization import namespace_to_dict
from frontend.network_capture.account_pool import AccountPoolError, AccountQuotaExceededError, select_chatgpt_account
from frontend.network_capture.chatgpt_capturer import ChatGPTCapturer
from frontend.network_capture.google_aimode_capturer import GoogleAIModeCapturer

RESPONSE_KEY = "web_response"
ERROR_KEY = "web_error"
PROMPT_KEY = "web_prompt"
TAGGING_KEY = "web_enable_citation_tagging"
WEB_PROVIDER_KEY = "web_provider"
GOOGLE_SESSION_KEY = "google_aimode_session_path"


def tab_web():
  """Render the web capture interactive tab."""
  st.session_state.setdefault(RESPONSE_KEY, None)
  st.session_state.setdefault(ERROR_KEY, None)
  st.session_state.setdefault(PROMPT_KEY, None)
  st.session_state.setdefault('network_show_browser', False)
  st.session_state.setdefault(TAGGING_KEY, True)
  st.session_state.setdefault(WEB_PROVIDER_KEY, "ChatGPT")
  st.session_state.setdefault(GOOGLE_SESSION_KEY, "./data/google_aimode_session.json")

  st.markdown("### 🌐 Web Testing")

  st.selectbox(
    "Web provider",
    options=["ChatGPT", "Google AI Mode"],
    key=WEB_PROVIDER_KEY,
    help="ChatGPT uses account rotation; Google AI Mode requires no login.",
  )

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

            provider_choice = st.session_state.get(WEB_PROVIDER_KEY, "ChatGPT")
            headless = not st.session_state.network_show_browser

            if provider_choice == "Google AI Mode":
              capturer = GoogleAIModeCapturer(
                storage_state_path=st.session_state.get(GOOGLE_SESSION_KEY),
                status_callback=update_status,
              )
              try:
                capturer.start_browser(headless=headless)
                capturer.authenticate()
                provider_response = capturer.send_prompt(trimmed_prompt, "google-aimode")
              finally:
                try:
                  capturer.stop_browser()
                except Exception:
                  pass
            else:
              try:
                account, storage_state_path = select_chatgpt_account()
              except AccountQuotaExceededError as exc:
                wait_hint = ""
                if exc.next_available_in_seconds is not None:
                  minutes = max(1, int(exc.next_available_in_seconds / 60))
                  wait_hint = f" Next slot available in ~{minutes} min."
                raise Exception(f"{exc}.{wait_hint}") from exc
              except AccountPoolError as exc:
                raise Exception(str(exc)) from exc

              capturer = ChatGPTCapturer(storage_state_path=storage_state_path, status_callback=update_status)
              try:
                capturer.start_browser(headless=headless)
                capturer.authenticate(
                  email=account.email,
                  password=account.password,
                )
                provider_response = capturer.send_prompt(trimmed_prompt, "chatgpt-free")
              finally:
                try:
                  capturer.stop_browser()
                except Exception:
                  pass

            status_container.write("Processing captured response...")
            response_ns = build_web_response(provider_response)

            status_container.write("Saving capture...")
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
              interaction_id = saved_payload.get("interaction_id") if isinstance(saved_payload, dict) else None
              metadata = saved_payload.get("metadata") or {} if isinstance(saved_payload, dict) else {}
              citation_status = metadata.get("citation_tagging_status")

              should_wait = (
                bool(st.session_state.get(TAGGING_KEY, True))
                and citation_status in {"queued", "running"}
                and isinstance(interaction_id, int)
              )

              timed_out_waiting = False
              if should_wait:
                status.update(label="Web analysis: citation tagging in progress…", state="running")
                status_container.write("Waiting for citation tagging to finish (up to 3 minutes)...")
                started = time.time()
                while True:
                  elapsed = int(time.time() - started)
                  refreshed, err = safe_api_call(
                    st.session_state.api_client.get_interaction,
                    interaction_id=interaction_id,
                    show_spinner=False,
                  )
                  if err:
                    status_container.write(f"⚠️ Error refreshing tagging status: {err}")
                    break
                  refreshed_meta = (refreshed or {}).get("metadata") or {}
                  refreshed_status = refreshed_meta.get("citation_tagging_status")
                  if refreshed_status in {"completed", "failed", "disabled", "skipped"}:
                    saved_payload = refreshed
                    break
                  if elapsed >= 180:
                    timed_out_waiting = True
                    status_container.write("⚠️ Timed out waiting for citation tagging; check History for results.")
                    break
                  # Keep the status indicator alive while we poll.
                  status.update(
                    label=f"Web analysis: citation tagging in progress… ({elapsed}s)",
                    state="running",
                  )
                  time.sleep(2)

              # Report final tagging status (after waiting when applicable).
              annotations = None
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
                  if citation_status == "completed":
                    status_container.write(f"✅ Citation annotations saved: {annotated}/{total} citations annotated.")
                  elif citation_status == "failed":
                    status_container.write("⚠️ Citation tagging failed (see History for details).")
                  elif citation_status == "disabled":
                    status_container.write("ℹ️ Citation tagging is disabled.")
                  elif citation_status == "skipped":
                    status_container.write("ℹ️ Citation tagging skipped.")
                  else:
                    status_container.write(f"ℹ️ Citation tagging status: {citation_status or 'unknown'}")
              if citation_error:
                status_container.write(f"⚠️ Citation tagging error: {citation_error}")

              if timed_out_waiting:
                status.update(label="Web analysis complete (citation tagging pending)", state="complete")
              else:
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
    interaction_id = getattr(st.session_state[RESPONSE_KEY], "interaction_id", None)
    if interaction_id:
      st.divider()
      btn_wrap, _ = st.columns([1, 4])
      with btn_wrap:
        render_markdown_download_button(
          base_url=st.session_state.api_client.base_url,
          interaction_id=interaction_id,
          key=f"web-md-{interaction_id}",
        )
