"""Tests for automatic account rotation and quota tracking."""

from pathlib import Path

import pytest

from frontend.network_capture.account_pool import (
  AccountQuotaExceededError,
  load_chatgpt_accounts_from_env,
  select_chatgpt_account,
)


def test_load_chatgpt_accounts_from_env_supports_default_password(monkeypatch):
  """Pool loader should allow per-account passwords to be omitted when a default is provided."""
  monkeypatch.delenv("CHATGPT_ACCOUNTS_FILE", raising=False)
  monkeypatch.setenv(
    "CHATGPT_ACCOUNTS_JSON",
    '{"default_password":"shared","accounts":[{"email":"a@example.com"},{"email":"b@example.com"}]}',
  )
  accounts = load_chatgpt_accounts_from_env()
  assert len(accounts) == 2
  assert accounts[0].password == "shared"
  assert accounts[1].password == "shared"


def test_select_chatgpt_account_rotates_and_enforces_quota(tmp_path: Path, monkeypatch):
  """Selector should rotate across accounts and stop when all are exhausted."""
  monkeypatch.delenv("CHATGPT_ACCOUNTS_FILE", raising=False)
  monkeypatch.setenv(
    "CHATGPT_ACCOUNTS_JSON",
    '{"accounts":[{"email":"a@example.com","password":"p"},{"email":"b@example.com","password":"p"}]}',
  )
  monkeypatch.setenv("CHATGPT_USAGE_DB_PATH", str(tmp_path / "usage.sqlite"))
  monkeypatch.setenv("CHATGPT_DAILY_LIMIT", "1")
  monkeypatch.setenv("CHATGPT_WINDOW_HOURS", "24")
  monkeypatch.setenv("CHATGPT_SESSIONS_DIR", str(tmp_path / "sessions"))

  first, first_path = select_chatgpt_account(now_ts=1000)
  second, second_path = select_chatgpt_account(now_ts=1000)
  assert first.email != second.email
  assert first_path != second_path

  with pytest.raises(AccountQuotaExceededError) as excinfo:
    select_chatgpt_account(now_ts=1000)
  assert excinfo.value.next_available_in_seconds == 24 * 3600


def test_select_chatgpt_account_is_sticky_until_exhausted(tmp_path: Path, monkeypatch):
  """Selector should keep using the same account until its quota is exhausted."""
  monkeypatch.delenv("CHATGPT_ACCOUNTS_FILE", raising=False)
  monkeypatch.setenv(
    "CHATGPT_ACCOUNTS_JSON",
    '{"accounts":[{"email":"a@example.com","password":"p"},{"email":"b@example.com","password":"p"}]}',
  )
  monkeypatch.setenv("CHATGPT_USAGE_DB_PATH", str(tmp_path / "usage.sqlite"))
  monkeypatch.setenv("CHATGPT_DAILY_LIMIT", "10")
  monkeypatch.setenv("CHATGPT_WINDOW_HOURS", "24")
  monkeypatch.setenv("CHATGPT_SESSIONS_DIR", str(tmp_path / "sessions"))

  first, _ = select_chatgpt_account(now_ts=1000)
  second, _ = select_chatgpt_account(now_ts=1001)
  assert first.email == second.email
