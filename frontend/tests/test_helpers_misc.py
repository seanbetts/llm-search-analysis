"""Tests for helper utilities."""

import types

import pytest

from frontend.helpers.error_handling import (
  APIClientError,
  APIConnectionError,
  APINotFoundError,
  APIServerError,
  APITimeoutError,
  APIValidationError,
  safe_api_call,
)
from frontend.helpers.serialization import namespace_to_dict
from frontend.tabs.batch import summarize_batch_results
from frontend.utils import format_pub_date


class DummySpinner:
  """Context manager stub to simulate spinner."""

  def __enter__(self):
    """Enter context."""
    return None

  def __exit__(self, exc_type, exc, tb):
    """Exit context."""
    return False


class DummyStreamlit:
  """Minimal Streamlit shim for tests."""

  def __init__(self):
    """Initialize shim with empty call tracking."""
    self.spinner_calls = []
    self.success_messages = []

  def spinner(self, text):
    self.spinner_calls.append(text)
    return DummySpinner()

  def success(self, message):
    self.success_messages.append(message)


@pytest.fixture
def stub_streamlit(monkeypatch):
  dummy = DummyStreamlit()
  monkeypatch.setattr("frontend.helpers.error_handling.st", dummy)
  return dummy


def test_safe_api_call_success(stub_streamlit):
  """safe_api_call returns result and emits success message when provided."""
  def do_work(x, y):
    return x + y

  result, error = safe_api_call(do_work, 2, 3, success_message="Done!", spinner_text="Working...")
  assert result == 5
  assert error is None
  assert stub_streamlit.spinner_calls == ["Working..."]
  assert stub_streamlit.success_messages == ["Done!"]


@pytest.mark.parametrize(
  "exception, expected",
  [
    (APINotFoundError("missing"), "Resource not found"),
    (APITimeoutError("timeout"), "Request timed out"),
    (APIConnectionError("connection failed"), "Cannot connect"),
    (APIValidationError("bad request"), "Invalid request"),
    (APIServerError("boom"), "Server error"),
    (APIClientError("generic"), "API error"),
    (RuntimeError("unexpected"), "Unexpected error"),
  ]
)
def test_safe_api_call_error_paths(exception, expected, stub_streamlit):
  """Each API client exception should map to a friendly error message."""
  def do_fail():
    raise exception

  _, error = safe_api_call(do_fail, show_spinner=False)
  assert error is not None
  assert expected.split()[0].lower() in error.lower()


def test_namespace_to_dict_recursively_converts_namespaces():
  """SimpleNamespace instances should convert to nested dict/list structures."""
  nested = types.SimpleNamespace(
    name="outer",
    inner=types.SimpleNamespace(value=42),
    items=[types.SimpleNamespace(id=1), {"raw": True}]
  )
  converted = namespace_to_dict(nested)
  assert converted == {
    "name": "outer",
    "inner": {"value": 42},
    "items": [{"id": 1}, {"raw": True}]
  }


def test_format_pub_date_handles_iso_and_invalid():
  """Utility should format ISO strings and fall back gracefully."""
  formatted = format_pub_date("2024-01-15T10:30:00")
  assert formatted == "Mon, Jan 15, 2024 10:30 UTC"
  assert format_pub_date("") == ""
  assert format_pub_date("invalid-date") == "invalid-date"


def test_summarize_batch_results_handles_success_and_failures():
  """Summaries should separate successes from errors and compute averages."""
  sample = [
    {'prompt': 'one', 'model': 'A', 'sources': 2, 'sources_used': 1, 'avg_rank': 3.0},
    {'prompt': 'two', 'model': 'B', 'sources': 4, 'sources_used': 2, 'avg_rank': 5.0},
    {'prompt': 'three', 'model': 'C', 'error': 'boom'},
  ]
  summary = summarize_batch_results(sample)
  assert summary['total_runs'] == 3
  assert summary['successful'] == 2
  assert len(summary['failed']) == 1
  assert summary['avg_sources'] == pytest.approx(3.0)
  assert summary['avg_sources_used'] == pytest.approx(1.5)
  assert summary['avg_rank'] == pytest.approx(4.0)


def test_summarize_batch_results_handles_empty():
  """Empty inputs should return zero counts and None averages."""
  summary = summarize_batch_results([])
  assert summary['total_runs'] == 0
  assert summary['successful'] == 0
  assert summary['failed'] == []
  assert summary['avg_sources'] is None
  assert summary['avg_sources_used'] is None
  assert summary['avg_rank'] is None
