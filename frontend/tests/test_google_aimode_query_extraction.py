"""Unit tests for Google AI Mode query extraction heuristics."""

from frontend.network_capture.google_aimode_capturer import GoogleAIModeCapturer


def test_extract_search_queries_ignores_tbn_thumbnail_queries():
  """Ignore image thumbnail (`tbn:`) pseudo-queries that show up in network traffic."""
  capturer = GoogleAIModeCapturer()
  # Reach into the closure helper by calling the method with injected captured requests.
  capturer.browser_manager.intercepted_requests = [
    {"url": "https://www.google.com/search?q=tbn:ANd9GcSSjYw9h4gKoSv33mX5cYlgCo1asyqY1-4UqMrutYfA8YRw3eB0"},
    {"url": "https://www.google.com/search?q=Find%20me%20the%20latest%20information%20on%20the%20Steam%20Machine"},
  ]
  queries = capturer._extract_search_queries()
  assert [q.query for q in queries] == ["Find me the latest information on the Steam Machine"]

