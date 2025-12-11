"""Tests for helper utilities inside the batch tab."""

from frontend.tabs.batch import build_rows_from_batch_status


def test_build_rows_from_batch_status_summarizes_results_and_errors():
  """Helper should convert backend payloads into table rows."""
  payload = {
    "results": [
      {
        "prompt": "p1",
        "model_display_name": "Custom Display",
        "model": "gpt-5.1",
        "search_queries": ["q1", "q2"],
        "sources_found": 4,
        "sources_used": 2,
        "avg_rank": 1.5,
        "response_time_ms": 2500,
      },
      {
        "prompt": "p2",
        "model": "gemini-2.5-flash",
        "search_queries": [],
        "sources_found": 0,
        "sources_used": 0,
        "avg_rank": None,
        "response_time_ms": None,
      },
    ],
    "errors": [
      {"prompt": "p3", "model": "gpt-5-nano", "error": "boom"},
      {"prompt": "p4", "provider": "anthropic", "error": "bad"},
    ],
  }

  rows = build_rows_from_batch_status(payload)
  assert len(rows) == 4

  first = rows[0]
  assert first["prompt"] == "p1"
  assert first["model"] == "Custom Display"
  assert first["searches"] == 2
  assert first["sources"] == 4
  assert first["sources_used"] == 2
  assert first["avg_rank"] == 1.5
  assert first["response_time_s"] == 2.5

  second = rows[1]
  assert second["model"] == "Gemini 2.5 Flash"  # fallback display name
  assert second["response_time_s"] == 0

  third = rows[2]
  assert third["model"] == "GPT-5 Nano"
  assert third["error"] == "boom"

  fourth = rows[3]
  assert fourth["model"] == "anthropic"  # provider fallback
  assert fourth["error"] == "bad"
