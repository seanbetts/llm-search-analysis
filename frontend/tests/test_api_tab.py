"""Tests for the API tab UI logic."""

from types import SimpleNamespace

import frontend.tabs.api as api_tab


def test_tab_api_hides_gpt_5_1_option(monkeypatch):
  """Ensure GPT-5.1 is not selectable for new API analyses."""

  class _SessionState(dict):
    """Session state mapping that supports attribute access."""

    def __getattr__(self, item):
      """Return an item from the mapping."""
      return self.get(item)

    def __setattr__(self, key, value):
      """Set an item on the mapping."""
      self[key] = value

  class _StreamlitStub:
    """Minimal Streamlit stub for `tab_api()`."""

    def __init__(self):
      """Initialise stub state and captured widget options."""
      self.session_state = _SessionState(api_client=SimpleNamespace())
      self.selectbox_options = None

    def markdown(self, *_args, **_kwargs):
      """Stub for `st.markdown()`."""
      return None

    def error(self, *_args, **_kwargs):
      """Stub for `st.error()`."""
      return None

    def warning(self, *_args, **_kwargs):
      """Stub for `st.warning()`."""
      return None

    def selectbox(self, _label, options, **_kwargs):
      """Capture options passed to `st.selectbox()` and return the first item."""
      self.selectbox_options = list(options)
      return self.selectbox_options[0]

    def chat_input(self, *_args, **_kwargs):
      """Return None so the tab does not trigger API calls."""
      return None

  st_stub = _StreamlitStub()
  monkeypatch.setattr(api_tab, "st", st_stub)

  monkeypatch.setattr(
    api_tab,
    "get_all_models",
    lambda: {
      "🟢 OpenAI - GPT-5.1": ("openai", "gpt-5.1"),
      "🟢 OpenAI - GPT-5.2": ("openai", "gpt-5.2"),
      "🔵 Google - Gemini 2.5 Flash": ("google", "gemini-2.5-flash"),
    },
  )

  api_tab.tab_api()

  assert st_stub.selectbox_options is not None
  assert "🟢 OpenAI - GPT-5.1" not in st_stub.selectbox_options
  assert "🟢 OpenAI - GPT-5.2" in st_stub.selectbox_options
