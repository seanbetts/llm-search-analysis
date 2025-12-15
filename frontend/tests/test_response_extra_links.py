"""Tests for extra link rendering in the response component."""

from types import SimpleNamespace

import frontend.components.response as response_module


def test_extra_links_use_na_description_when_missing_metadata_snippet(monkeypatch):
  """Extra links should not reuse snippet_cited as the description."""

  class _Column:
    """Stub column returned by `st.columns()`."""

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
    """Streamlit stub that captures markdown calls."""

    def __init__(self):
      """Initialise capture buffers."""
      self.markdown_calls = []

    def columns(self, spec, **_kwargs):
      """Return the requested number of columns."""
      ncols = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
      return [_Column() for _ in range(ncols)]

    def metric(self, *_args, **_kwargs):
      """Stub for `st.metric()`."""
      return None

    def markdown(self, body, **_kwargs):
      """Capture markdown output."""
      self.markdown_calls.append(str(body))
      return None

    def divider(self, *_args, **_kwargs):
      """Stub for `st.divider()`."""
      return None

    def caption(self, *_args, **_kwargs):
      """Stub for `st.caption()`."""
      return None

    def container(self):
      """Return a context manager for `with st.container()`."""
      return _Column()

  st_stub = _StreamlitStub()
  monkeypatch.setattr(response_module, "st", st_stub)

  response = SimpleNamespace(
    provider="OpenAI",
    model="chatgpt-free",
    model_display_name="ChatGPT (Free)",
    response_text="Answer.\n\n[1]: https://example.com \"Example\"",
    response_time_ms=1000,
    search_queries=[],
    all_sources=[],
    sources_found=0,
    sources_used=0,
    avg_rank=None,
    extra_links_count=1,
    data_source="web",
    raw_response={},
    citations=[
      SimpleNamespace(
        url="https://example.com",
        title="Example",
        rank=None,
        metadata={"citation_number": 1, "is_extra_link": True},
        snippet_cited="CITED SNIPPET",
        snippet_used=None,
        function_tags=["evidence"],
        stance_tags=["supports"],
        provenance_tags=["news"],
        influence_summary="Used as context.",
        published_at=None,
        text_snippet=None,
      ),
    ],
  )

  response_module.display_response(response, prompt="Prompt")

  html = "\n".join(st_stub.markdown_calls)
  assert "### 🔗 Extra Links" in html
  assert "Description:</strong> <em>N/A</em>" in html
  assert "Snippet Cited:</strong> <em>CITED SNIPPET</em>" in html
  assert "Influence Summary:</strong>" in html
