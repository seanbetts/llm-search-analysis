"""Model selection and display utilities."""

import streamlit as st


def get_all_models():
  """Get all available models with provider labels.

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

    # Model display names
    model_names = {
      # Anthropic
      'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
      'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
      'claude-opus-4-1-20250805': 'Claude Opus 4.1',
      # OpenAI
      'gpt-5.1': 'GPT-5.1',
      'gpt-5-mini': 'GPT-5 Mini',
      'gpt-5-nano': 'GPT-5 Nano',
      # Google
      'gemini-3-pro-preview': 'Gemini 3 Pro (Preview)',
      'gemini-2.5-flash': 'Gemini 2.5 Flash',
      'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
      # Network capture
      'ChatGPT (Free)': 'ChatGPT (Free)',
      'chatgpt-free': 'ChatGPT (Free)',
    }

    for provider in providers:
      if provider['is_active']:
        provider_name = provider['name']
        for model in provider['supported_models']:
          # Get formatted model name
          formatted_model = model_names.get(model, model)
          # Create label: "🟢 OpenAI - GPT-5.1"
          label = f"{provider_labels[provider_name]} - {formatted_model}"
          models[label] = (provider_name, model)

    return models
  except Exception as e:
    st.error(f"Error loading models: {str(e)}")
    return {}
