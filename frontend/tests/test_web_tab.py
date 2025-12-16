"""Tests for the Web tab UI logic."""

from types import SimpleNamespace

import frontend.tabs.web as web_tab


def test_tab_web_does_not_pass_widget_defaults_when_using_session_state(monkeypatch):
  """Avoid Streamlit warnings by not passing `value=` when `key` is bound to session_state."""

  class _SessionState(dict):
    """Session state mapping that supports attribute access."""

    def __getattr__(self, item):
      """Return an item from the mapping."""
      return self.get(item)

    def __setattr__(self, key, value):
      """Set an item on the mapping."""
      self[key] = value

  class _StreamlitStub:
    """Minimal Streamlit stub for `tab_web()`."""

    def __init__(self):
      """Initialise stub state and captured widget args."""
      self.session_state = _SessionState({"api_client": SimpleNamespace()})
      self.checkbox_calls = []
      self.selectbox_calls = []

    def markdown(self, *_args, **_kwargs):
      """Stub for `st.markdown()`."""
      return None

    def checkbox(self, *_args, **kwargs):
      """Capture checkbox kwargs and return the current session state value."""
      self.checkbox_calls.append(kwargs)
      assert "value" not in kwargs
      key = kwargs.get("key")
      if key and key not in self.session_state:
        self.session_state[key] = False
      return bool(self.session_state.get(key, False))

    def selectbox(self, *_args, **kwargs):
      """Capture selectbox kwargs and return the current session state value."""
      self.selectbox_calls.append(kwargs)
      key = kwargs.get("key")
      options = kwargs.get("options") or []
      if key and key not in self.session_state:
        self.session_state[key] = options[0] if options else None
      return self.session_state.get(key)

    def chat_input(self, *_args, **_kwargs):
      """Return None so the tab does not trigger capture or API calls."""
      return None

  st_stub = _StreamlitStub()
  monkeypatch.setattr(web_tab, "st", st_stub)

  web_tab.tab_web()

  keys = {call.get("key") for call in st_stub.checkbox_calls}
  assert "network_show_browser" in keys
  assert web_tab.TAGGING_KEY in keys

  selectbox_keys = {call.get("key") for call in st_stub.selectbox_calls}
  assert web_tab.WEB_PROVIDER_KEY in selectbox_keys
