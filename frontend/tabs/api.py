"""API-based interactive tab."""

import streamlit as st

from frontend.components.models import get_all_models
from frontend.components.response import display_response
from frontend.helpers.error_handling import safe_api_call
from frontend.helpers.interactive import build_api_response
from frontend.helpers.markdown_export import render_markdown_download_button

RESPONSE_KEY = "api_response"
ERROR_KEY = "api_error"
PROMPT_KEY = "api_prompt"


def tab_api():
  """Render API interactive tab."""
  st.session_state.setdefault(RESPONSE_KEY, None)
  st.session_state.setdefault(ERROR_KEY, None)
  st.session_state.setdefault(PROMPT_KEY, None)

  st.markdown("### 🎯 API Testing")

  models = get_all_models()
  if not models:
    st.error("No API keys configured. Please set up your .env file with at least one provider API key.")
    return

  # GPT-5.2 supersedes GPT-5.1 for new API analyses; keep GPT-5.1 in history but hide it here.
  models = {
    label: (provider, model_id)
    for label, (provider, model_id) in models.items()
    if not (provider == "openai" and model_id == "gpt-5.1")
  }
  if not models:
    st.error("No supported models available for API testing.")
    return

  model_labels = list(models.keys())
  selected_label = st.selectbox(
    "Select Model",
    model_labels,
    help="Choose a model from any available provider"
  )
  selected_provider, selected_model = models[selected_label]
  formatted_model = selected_label.split(' - ', 1)[1] if ' - ' in selected_label else selected_model

  prompt = st.chat_input("Prompt (Enter to send, Shift+Enter for new line)", key="api_prompt_input")
  if prompt is not None:
    trimmed_prompt = prompt.strip()
    if not trimmed_prompt:
      st.warning("Please enter a prompt")
    else:
      response_data, error = safe_api_call(
        st.session_state.api_client.send_prompt,
        prompt=trimmed_prompt,
        provider=selected_provider,
        model=selected_model,
        spinner_text=f"Querying {formatted_model}..."
      )

      if error:
        st.session_state[ERROR_KEY] = error
        st.session_state[RESPONSE_KEY] = None
      else:
        response_ns = build_api_response(response_data)
        st.session_state[RESPONSE_KEY] = response_ns
        st.session_state[PROMPT_KEY] = trimmed_prompt
        st.session_state[ERROR_KEY] = None

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
          key=f"api-md-{interaction_id}",
        )
