"""Streamlit tab for backend-managed live network logs."""

import json
from typing import Any, Dict, List, Optional

import streamlit as st

from frontend.api_client import APIClientError


def tab_live():
  """Render the Live Network Log tab."""
  _init_state()
  st.markdown("### 🛰️ Live Network Log")
  st.write("Start a backend-managed ChatGPT browsing session and watch events stream in real time.")

  st.text_area(
    "Prompt",
    key="live_prompt",
    height=160,
    help="Prompt sent to ChatGPT with browsing enabled.",
  )
  st.checkbox(
    "Run browser in headless mode",
    key="live_headless",
    help="Disable to view the browser window for debugging logins or CAPTCHA.",
  )

  button_cols = st.columns(2)
  start_clicked = button_cols[0].button(
    "Start Live Capture",
    use_container_width=True,
    disabled=st.session_state.live_streaming,
  )
  reconnect_clicked = button_cols[1].button(
    "Reconnect Stream",
    use_container_width=True,
    disabled=(
      not st.session_state.live_capture_id
      or st.session_state.live_streaming
    ),
  )

  if st.session_state.live_error:
    st.error(st.session_state.live_error)

  st.divider()
  feed_col, summary_col = st.columns([2, 1])
  with feed_col:
    feed_placeholder = st.empty()
  with summary_col:
    summary_placeholder = st.empty()

  if start_clicked:
    _start_live_capture(feed_placeholder, summary_placeholder)
  elif reconnect_clicked:
    _resume_live_capture(feed_placeholder, summary_placeholder)

  _render_live_feed(feed_placeholder)
  _render_live_summary(summary_placeholder)

  st.divider()
  _render_saved_captures(feed_placeholder, summary_placeholder)


def _init_state():
  defaults = {
    "live_prompt": "",
    "live_headless": True,
    "live_capture_id": None,
    "live_events": [],
    "live_metadata": None,
    "live_streaming": False,
    "live_error": None,
    "live_recent_captures": [],
    "live_recent_initialized": False,
  }
  for key, value in defaults.items():
    if key not in st.session_state:
      st.session_state[key] = value

  if not st.session_state.live_recent_initialized:
    _refresh_recent_captures()
    st.session_state.live_recent_initialized = True


def _start_live_capture(feed_placeholder, summary_placeholder):
  prompt = (st.session_state.live_prompt or "").strip()
  if not prompt:
    st.warning("Please enter a prompt to start the capture.")
    return

  client = st.session_state.api_client
  try:
    with st.spinner("Launching backend capture..."):
      response = client.start_live_capture(prompt=prompt, headless=st.session_state.live_headless)
  except APIClientError as exc:
    st.session_state.live_error = f"Failed to start capture: {exc}"
    return

  st.session_state.live_capture_id = response.get("capture_id")
  st.session_state.live_events = []
  st.session_state.live_metadata = {
    "capture_id": response.get("capture_id"),
    "status": response.get("status"),
    "headless": response.get("headless"),
    "started_at": response.get("started_at"),
  }
  st.session_state.live_streaming = True
  st.session_state.live_error = None
  _render_live_feed(feed_placeholder)
  _render_live_summary(summary_placeholder)
  _stream_capture(st.session_state.live_capture_id, feed_placeholder, summary_placeholder)


def _resume_live_capture(feed_placeholder, summary_placeholder):
  capture_id = st.session_state.live_capture_id
  if not capture_id:
    return
  st.session_state.live_events = []
  st.session_state.live_streaming = True
  st.session_state.live_error = None
  _stream_capture(capture_id, feed_placeholder, summary_placeholder)


def _stream_capture(capture_id: Optional[str], feed_placeholder, summary_placeholder):
  if not capture_id:
    return
  client = st.session_state.api_client
  try:
    with st.spinner("Streaming live events..."):
      for event in client.stream_live_capture(capture_id):
        st.session_state.live_events.append(event)
        if event.get("phase") == "capture_complete":
          st.session_state.live_metadata = event.get("data")
        _render_live_feed(feed_placeholder)
        _render_live_summary(summary_placeholder)
  except APIClientError as exc:
    st.session_state.live_error = f"Streaming error: {exc}"
  finally:
    st.session_state.live_streaming = False
    _refresh_recent_captures()


def _render_live_feed(container):
  events = st.session_state.live_events
  with container.container():
    st.markdown("#### Event Feed")
    if not events:
      if st.session_state.live_streaming:
        st.info("Waiting for events...")
      else:
        st.info("No events yet. Start a capture or load an existing session.")
      return

    for event in events[-200:]:
      phase = event.get("phase")
      timestamp = event.get("timestamp", "")
      description = _format_event(event)
      st.markdown(f"**{phase}** · `{timestamp}`")
      if description:
        st.write(description)
      st.divider()


def _format_event(event: Dict[str, Any]) -> str:
  phase = event.get("phase")
  data = event.get("data", {})
  if phase == "browser_status":
    return data.get("message", "")
  if phase == "search_query":
    query = data.get("query")
    count = data.get("source_count")
    return f"Query: {query} ({count} sources)"
  if phase == "search_result":
    title = data.get("title") or data.get("domain")
    url = data.get("url", "")
    rank = data.get("rank")
    return f"[{title}]({url}) · rank {rank}"
  if phase == "citation":
    return f"Citation: {data.get('title','')} ({data.get('url','')})"
  if phase == "assistant_delta":
    message = data.get("message", "")
    return message[:4000]
  if phase == "error":
    return data.get("message", "Unknown error")
  if phase == "capture_complete":
    status = data.get("status")
    return f"Capture finished with status: {status}"
  return json.dumps(data)


def _render_live_summary(container):
  metadata = st.session_state.live_metadata
  capture_id = st.session_state.live_capture_id
  with container.container():
    st.markdown("#### Session Summary")
    if not capture_id:
      st.info("No capture selected.")
      return

    if metadata:
      st.write(f"**Capture ID:** `{capture_id}`")
      st.write(f"**Status:** {metadata.get('status')}")
      st.write(f"**Started:** {metadata.get('started_at')}")
      if metadata.get("finished_at"):
        st.write(f"**Finished:** {metadata.get('finished_at')}")
      st.write(f"**Headless:** {'Yes' if metadata.get('headless') else 'No'}")
      if metadata.get("event_count") is not None:
        st.write(f"**Events:** {metadata.get('event_count')}")
      if metadata.get("error"):
        st.error(metadata.get("error"))
    else:
      st.info("Waiting for metadata from backend...")

    if capture_id and st.session_state.live_events and not st.session_state.live_streaming:
      payload = json.dumps({
        "metadata": metadata or {},
        "events": st.session_state.live_events,
      }, indent=2)
      st.download_button(
        "Download JSON Log",
        data=payload,
        file_name=f"{capture_id}.json",
        mime="application/json",
        use_container_width=True,
      )


def _render_saved_captures(feed_placeholder, summary_placeholder):
  st.markdown("### Saved Captures")
  controls = st.columns([3, 1])
  with controls[1]:
    if st.button("Refresh", key="live_refresh_captures"):
      _refresh_recent_captures(force=True)

  captures = st.session_state.live_recent_captures
  if not captures:
    st.info("No saved captures yet.")
    return

  capture_ids = [capture["capture_id"] for capture in captures]
  selected_id = st.selectbox(
    "Select a capture",
    capture_ids,
    format_func=lambda cid: _format_capture_label(cid, captures),
    key="live_saved_selector",
  )

  if st.button("Load Capture", use_container_width=True):
    _load_capture_details(selected_id, feed_placeholder, summary_placeholder)


def _format_capture_label(capture_id: str, captures: List[Dict[str, Any]]) -> str:
  meta = next((item for item in captures if item["capture_id"] == capture_id), None)
  if not meta:
    return capture_id
  status = meta.get("status")
  started = meta.get("started_at")
  return f"{capture_id} · {status} · {started}"


def _refresh_recent_captures(force: bool = False):
  client = st.session_state.api_client
  if not force and st.session_state.live_recent_captures:
    return
  try:
    response = client.list_live_captures()
    st.session_state.live_recent_captures = response.get("captures", [])
  except APIClientError as exc:
    st.warning(f"Failed to load saved captures: {exc}")


def _load_capture_details(capture_id: str, feed_placeholder, summary_placeholder):
  client = st.session_state.api_client
  try:
    record = client.get_live_capture(capture_id)
  except APIClientError as exc:
    st.error(f"Failed to load capture: {exc}")
    return

  st.session_state.live_capture_id = capture_id
  st.session_state.live_events = record.get("events", [])
  st.session_state.live_metadata = record.get("metadata")
  st.session_state.live_streaming = False
  st.session_state.live_error = None
  _render_live_feed(feed_placeholder)
  _render_live_summary(summary_placeholder)
