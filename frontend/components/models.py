"""Model selection and display utilities.

This module fetches model information from the backend API to ensure
consistency with the centralized model registry.
"""

import streamlit as st
from frontend.helpers.metrics import get_model_display_name, is_known_model_id


def get_all_models():
  """Get all available models with provider labels.

  Fetches models from the backend API which uses the centralized model registry.
  No more hardcoded model names - everything comes from the single source of truth!

  Returns:
    Dict mapping display labels to (provider_name, model_id) tuples
    Example: {"🟢 OpenAI - GPT-5.1": ("openai", "gpt-5.1")}
  """
  try:
    # Get providers from API
    api_client = st.session_state.api_client
    providers = api_client.get_providers()

    models = {}

    provider_labels = {
      'openai': '🟢 OpenAI',
      'google': '🔵 Google',
      'anthropic': '🟣 Anthropic'
    }

    for provider in providers:
      if provider['is_active']:
        provider_name = provider['name']
        for model_id in provider['supported_models']:
          # Keep unknown/custom model ids verbatim so users can identify them.
          display_name = get_model_display_name(model_id) if is_known_model_id(model_id) else model_id
          # Create label: "🟢 OpenAI - GPT-5.1"
          label = f"{provider_labels[provider_name]} - {display_name}"
          models[label] = (provider_name, model_id)

    return models
  except Exception as e:
    st.error(f"Error loading models: {str(e)}")
    return {}
