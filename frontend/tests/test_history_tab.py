"""Tests for logic helpers in the history tab."""

from __future__ import annotations

from types import SimpleNamespace

from frontend import api_client
from frontend.tabs import history


def test_prepare_history_dataframe_derives_expected_fields():
  """Interactions should be normalized with previews and human-readable fields."""
  interactions = [
    {
      "interaction_id": 2,
      "created_at": "2024-02-01T10:00:00Z",
      "prompt": "Tell me something interesting about AI advancements in 2024.",
      "provider": "openai",
      "model": "gpt-5.1",
      "model_display_name": "GPT-5.1",
      "search_query_count": 2,
      "source_count": 4,
      "citation_count": 2,
      "average_rank": 3.25,
      "response_time_ms": 1234,
      "extra_links_count": 1,
      "data_source": "api",
    },
    {
      "interaction_id": 1,
      "created_at": "2024-01-31T09:00:00Z",
      "prompt": "Short prompt",
      "provider": "anthropic",
      "model": "claude-sonnet-4-5-20250929",
      "search_query_count": 0,
      "source_count": 0,
      "citation_count": 0,
      "average_rank": None,
      "response_time_ms": None,
      "data_source": "network_log",
    },
  ]

  df = history._prepare_history_dataframe(interactions)
  assert list(df["id"]) == [2, 1]  # sorted by timestamp desc
  assert df.loc[df["id"] == 2, "analysis_type"].item() == "API"
  assert df.loc[df["id"] == 1, "analysis_type"].item() == "Web"
  assert df.loc[df["id"] == 2, "prompt_preview"].item().startswith("Tell me something")
  assert df.loc[df["id"] == 1, "prompt_preview"].item() == "Short prompt"
  assert df.loc[df["id"] == 2, "avg_rank_display"].item() == "3.2"
  assert df.loc[df["id"] == 2, "response_time_display"].item() == "1.2s"
  assert df.loc[df["id"] == 1, "response_time_display"].item() == "N/A"
  assert df.loc[df["id"] == 1, "model_display"].item() == "claude-sonnet-4-5-20250929"
  assert df.loc[df["id"] == 2, "model_display"].item() == "GPT-5.1"


def test_prepare_history_dataframe_handles_empty_input():
  """Empty interaction lists should yield a DataFrame with known columns."""
  df = history._prepare_history_dataframe([])
  assert list(df.columns) == [
    'id', 'timestamp', 'analysis_type', 'prompt', 'prompt_preview', 'provider',
    'model', 'model_display', 'searches', 'sources', 'citations', 'avg_rank',
    'avg_rank_display', 'response_time_ms', 'response_time_display',
    'extra_links', 'data_source'
  ]
  assert df.empty


def test_fetch_all_interactions_iterates_through_pages(monkeypatch):
  """Helper should gather all pages and merge stats."""
  responses = [
    {
      "items": [{"interaction_id": 1}],
      "stats": {"analyses": 2},
      "pagination": {"has_next": True},
    },
    {
      "items": [{"interaction_id": 2}],
      "stats": {"analyses": 2},
      "pagination": {"has_next": False},
    },
  ]

  class DummyClient:
    """API client stub returning predefined pages."""

    def __init__(self, base_url):
      self.base_url = base_url
      self.calls = 0

    def get_recent_interactions(self, page, page_size, data_source=None):
      """Return the next response payload."""
      assert page == self.calls + 1
      self.calls += 1
      return responses[self.calls - 1]

  dummy = DummyClient("http://fake")
  monkeypatch.setattr(api_client, "APIClient", lambda base_url: dummy)

  aggregated = history._fetch_all_interactions("http://fake", page_size=1)
  assert aggregated["items"] == [{"interaction_id": 1}, {"interaction_id": 2}]
  assert aggregated["stats"] == {"analyses": 2}
  assert dummy.calls == 2


def test_tab_history_does_not_pass_widget_defaults_when_using_session_state(monkeypatch):
  """Avoid Streamlit warnings by not passing `default=` when `key` is bound to session_state."""

  class _SessionState(dict):
    """Session state mapping that supports attribute access."""

    def __getattr__(self, item):
      """Return an item from the mapping."""
      return self.get(item)

    def __setattr__(self, key, value):
      """Set an item on the mapping."""
      self[key] = value

  class _Column:
    """Context manager stub returned by `st.columns()`."""

    def __enter__(self):
      """Enter the column context."""
      return self

    def __exit__(self, exc_type, exc, tb):
      """Exit the column context."""
      return False

    def metric(self, *_args, **_kwargs):
      """Stub for `st.metric()`."""
      return None

  class _StreamlitStub:
    """Streamlit stub that asserts widgets avoid `default=` when bound to session state."""

    def __init__(self):
      """Initialise stubbed Streamlit session state."""
      self.session_state = _SessionState({
        "api_client": SimpleNamespace(base_url="http://fake"),
        "history_page": 1,
        "history_page_size": 10,
        "history_full_export": None,
        "history_search_query": "",
        "history_provider_filter": None,
        "history_model_filter": None,
        "history_filter_signature": None,
        "history_analysis_filter": ["API", "Web"],
        "history_last_filter": ("API", "Web"),
      })

    def markdown(self, *_args, **_kwargs):
      """Stub for `st.markdown()`."""
      return None

    def info(self, *_args, **_kwargs):
      """Stub for `st.info()`."""
      return None

    def warning(self, *_args, **_kwargs):
      """Stub for `st.warning()`."""
      return None

    def error(self, *_args, **_kwargs):
      """Stub for `st.error()`."""
      return None

    def caption(self, *_args, **_kwargs):
      """Stub for `st.caption()`."""
      return None

    def divider(self, *_args, **_kwargs):
      """Stub for `st.divider()`."""
      return None

    def columns(self, spec, **_kwargs):
      """Return a list of column stubs."""
      ncols = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
      return [_Column() for _ in range(ncols)]

    def text_input(self, *_args, **kwargs):
      """Return the current session state value for a text input."""
      # Ensure key is present; Streamlit handles binding automatically.
      key = kwargs.get("key")
      if key and hasattr(self.session_state, key) is False:
        setattr(self.session_state, key, "")
      return getattr(self.session_state, key, "")

    def multiselect(self, *_args, **kwargs):
      """Return the current session state selection for a multiselect."""
      assert "default" not in kwargs
      key = kwargs.get("key")
      if key is None:
        return []
      return getattr(self.session_state, key, [])

    def dataframe(self, *_args, **_kwargs):
      """Stub for `st.dataframe()`."""
      return None

    def selectbox(self, *_args, **_kwargs):
      """Stub for `st.selectbox()`."""
      return 0

    def download_button(self, *_args, **_kwargs):
      """Stub for `st.download_button()`."""
      return None

    def button(self, *_args, **_kwargs):
      """Stub for `st.button()`."""
      return False

    def rerun(self):
      """Fail fast if code attempts to rerun during the test."""
      raise RuntimeError("rerun should not be triggered in this test")

    def cache_data(self, *args, **kwargs):  # pragma: no cover
      """Stub decorator for `st.cache_data()`."""
      # Not used directly here (decorator already applied), but keep parity.
      def decorator(fn):
        """Return the original function unchanged."""
        return fn

      return decorator

  st_stub = _StreamlitStub()

  monkeypatch.setattr(history, "st", st_stub)

  def fake_safe_api_call(func, *args, **kwargs):
    """Return deterministic responses for History tab calls."""
    if func is history._fetch_all_interactions:
      return (
        {
          "items": [
            {
              "interaction_id": 1,
              "created_at": "2024-01-01T00:00:00Z",
              "prompt": "Hello",
              "provider": "openai",
              "model": "gpt-5.1",
              "model_display_name": "GPT-5.1",
              "search_query_count": 0,
              "source_count": 0,
              "citation_count": 0,
              "average_rank": None,
              "response_time_ms": None,
              "extra_links_count": 0,
              "data_source": "api",
            }
          ],
          "stats": {"analyses": 1},
        },
        None,
      )
    raise AssertionError(f"Unexpected safe_api_call target: {func}")

  monkeypatch.setattr(history, "safe_api_call", fake_safe_api_call)

  history.tab_history()
