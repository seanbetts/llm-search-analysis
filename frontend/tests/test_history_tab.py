"""Tests for logic helpers in the history tab."""

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

    def get_recent_interactions(self, page, page_size):
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
