"""Account pool and quota-aware selector for web-capture providers.

This module centralizes credential loading (from Docker secrets) and
quota-aware account selection so that web capture can rotate accounts in the
background without Streamlit UI toggles.

The design is provider-agnostic: ChatGPT is the first consumer, but the same
interfaces can be reused for other platforms (Google, Anthropic) when we add
web-capture equivalents.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class AccountPoolError(RuntimeError):
  """Raised when an account pool cannot be loaded or used."""


class AccountQuotaExceededError(RuntimeError):
  """Raised when no accounts are currently available within the quota window."""

  def __init__(self, message: str, next_available_in_seconds: Optional[int] = None):
    super().__init__(message)
    self.next_available_in_seconds = next_available_in_seconds


@dataclass(frozen=True, slots=True)
class WebAccount:
  """A single web-capture login account."""

  account_id: str
  email: str
  password: str


def _stable_account_id(email: str) -> str:
  """Derive a stable, non-reversible account id from an email address."""
  digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
  return digest[:12]


def _load_accounts_payload(accounts_file: Optional[str], accounts_json: Optional[str]) -> Dict[str, Any]:
  if accounts_file:
    path = Path(accounts_file)
    if not path.exists():
      raise AccountPoolError(f"Accounts file not found: {accounts_file}")
    raw = path.read_text(encoding="utf-8")
    try:
      payload = json.loads(raw)
    except json.JSONDecodeError as exc:
      raise AccountPoolError(f"Accounts file is not valid JSON: {accounts_file}") from exc
    if not isinstance(payload, (dict, list)):
      raise AccountPoolError("Accounts JSON must be an object or list")
    return payload if isinstance(payload, dict) else {"accounts": payload}

  if accounts_json:
    try:
      payload = json.loads(accounts_json)
    except json.JSONDecodeError as exc:
      raise AccountPoolError("CHATGPT_ACCOUNTS_JSON is not valid JSON") from exc
    if not isinstance(payload, (dict, list)):
      raise AccountPoolError("Accounts JSON must be an object or list")
    return payload if isinstance(payload, dict) else {"accounts": payload}

  raise AccountPoolError("No accounts configured")


def load_chatgpt_accounts_from_env() -> List[WebAccount]:
  """Load the ChatGPT account pool from env / Docker secrets.

  Supported configuration (in priority order):
  1) `CHATGPT_ACCOUNTS_FILE` pointing to a JSON secret file.
  2) `CHATGPT_ACCOUNTS_JSON` containing the JSON payload directly.
  3) Legacy single-account variables: `CHATGPT_EMAIL` + `CHATGPT_PASSWORD`.

  JSON schema (object form) supports future extension:
    {
      "default_password": "...",   # optional
      "accounts": [
        {"email": "...", "password": "...", "id": "optional-stable-id"},
        {"email": "..."}  # uses default_password or CHATGPT_PASSWORD
      ]
    }

  Returns:
    List of WebAccount objects.
  """
  legacy_email = os.getenv("CHATGPT_EMAIL")
  legacy_password = os.getenv("CHATGPT_PASSWORD")

  accounts_file = os.getenv("CHATGPT_ACCOUNTS_FILE")
  accounts_json = os.getenv("CHATGPT_ACCOUNTS_JSON")

  if not accounts_file and not accounts_json:
    if legacy_email and legacy_password:
      return [WebAccount(account_id=_stable_account_id(legacy_email), email=legacy_email, password=legacy_password)]
    raise AccountPoolError(
      "ChatGPT accounts are not configured. Set CHATGPT_ACCOUNTS_FILE/CHATGPT_ACCOUNTS_JSON "
      "or legacy CHATGPT_EMAIL/CHATGPT_PASSWORD."
    )

  payload = _load_accounts_payload(accounts_file, accounts_json)
  default_password = payload.get("default_password")
  if not isinstance(default_password, str) or not default_password:
    default_password = legacy_password

  raw_accounts = payload.get("accounts")
  if not isinstance(raw_accounts, list) or not raw_accounts:
    raise AccountPoolError("Accounts JSON must include a non-empty 'accounts' list")

  accounts: List[WebAccount] = []
  seen_emails: set[str] = set()
  for idx, item in enumerate(raw_accounts):
    if not isinstance(item, dict):
      raise AccountPoolError(f"Account entry at index {idx} must be an object")
    email = item.get("email")
    if not isinstance(email, str) or not email.strip():
      raise AccountPoolError(f"Account entry at index {idx} is missing a valid 'email'")
    email = email.strip()
    email_key = email.lower()
    if email_key in seen_emails:
      raise AccountPoolError(f"Duplicate account email in pool: {email}")
    seen_emails.add(email_key)

    password = item.get("password")
    if not isinstance(password, str) or not password.strip():
      password = default_password
    if not isinstance(password, str) or not password.strip():
      raise AccountPoolError(f"No password provided for {email} and no default_password/CHATGPT_PASSWORD set")

    account_id = item.get("id")
    if not isinstance(account_id, str) or not account_id.strip():
      account_id = _stable_account_id(email)
    account_id = account_id.strip()

    accounts.append(WebAccount(account_id=account_id, email=email, password=password.strip()))

  return accounts


class QuotaUsageStore:
  """SQLite-backed store for rolling-window usage events."""

  def __init__(self, db_path: Path):
    """Create a usage store.

    Args:
      db_path: Path to the SQLite database file (should live on a persistent volume).
    """
    self.db_path = db_path
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self._init_schema()

  def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

  def _init_schema(self) -> None:
    with self._connect() as conn:
      conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_events (
          account_id TEXT NOT NULL,
          ts INTEGER NOT NULL
        )
        """
      )
      conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_events_account_ts ON usage_events(account_id, ts)")

  def _prune(self, conn: sqlite3.Connection, window_start_ts: int) -> None:
    conn.execute("DELETE FROM usage_events WHERE ts < ?", (window_start_ts,))

  def select_and_record(
    self,
    accounts: Sequence[WebAccount],
    *,
    limit: int,
    window_seconds: int,
    now_ts: Optional[int] = None,
  ) -> WebAccount:
    """Select an account within quota and immediately record a usage event.

    Selection strategy is deterministic and quota-aware:
    - Prefer lowest usage count in the window.
    - Tie-break by least-recently-used.
    - Final tie-break by account_id for stable ordering.
    """
    if not accounts:
      raise AccountPoolError("No accounts available to select from")
    if limit <= 0:
      raise ValueError("limit must be positive")
    if window_seconds <= 0:
      raise ValueError("window_seconds must be positive")

    now = int(time.time()) if now_ts is None else int(now_ts)
    window_start = now - window_seconds

    with self._connect() as conn:
      conn.execute("BEGIN IMMEDIATE")
      self._prune(conn, window_start)

      placeholders = ",".join("?" for _ in accounts)
      account_ids = [acct.account_id for acct in accounts]

      rows = conn.execute(
        f"""
        SELECT account_id, COUNT(*) as cnt, MAX(ts) as last_ts
        FROM usage_events
        WHERE account_id IN ({placeholders})
        GROUP BY account_id
        """,
        tuple(account_ids),
      ).fetchall()

      by_id: Dict[str, Tuple[int, Optional[int]]] = {row[0]: (int(row[1]), row[2]) for row in rows}

      candidates: List[Tuple[int, int, str, WebAccount]] = []
      for acct in accounts:
        count, last_ts = by_id.get(acct.account_id, (0, None))
        if count >= limit:
          continue
        last_val = int(last_ts) if isinstance(last_ts, int) else 0
        candidates.append((count, last_val, acct.account_id, acct))

      if not candidates:
        next_in = self._seconds_until_next_available(conn, account_ids, window_seconds, now)
        raise AccountQuotaExceededError(
          "All ChatGPT accounts have reached the rolling quota; try again later.",
          next_available_in_seconds=next_in,
        )

      # Sort by (count asc, last_used asc) => least-used, least-recently-used.
      candidates.sort(key=lambda item: (item[0], item[1], item[2]))
      chosen = candidates[0][3]

      conn.execute("INSERT INTO usage_events(account_id, ts) VALUES (?, ?)", (chosen.account_id, now))
      conn.commit()
      return chosen

  def _seconds_until_next_available(
    self,
    conn: sqlite3.Connection,
    account_ids: Sequence[str],
    window_seconds: int,
    now: int,
  ) -> Optional[int]:
    placeholders = ",".join("?" for _ in account_ids)
    row = conn.execute(
      f"SELECT MIN(ts) FROM usage_events WHERE account_id IN ({placeholders})",
      tuple(account_ids),
    ).fetchone()
    min_ts = row[0] if row else None
    if not isinstance(min_ts, int):
      return None
    next_ts = min_ts + window_seconds
    return max(0, int(next_ts - now))


def chatgpt_usage_store_from_env() -> QuotaUsageStore:
  """Build a QuotaUsageStore from environment configuration."""
  default_path = Path("./data/account_usage.sqlite")
  db_path = Path(os.getenv("CHATGPT_USAGE_DB_PATH", str(default_path)))
  return QuotaUsageStore(db_path=db_path)


def chatgpt_session_path_for_account(account: WebAccount) -> str:
  """Return the per-account storageState path for ChatGPT."""
  base_dir = Path(os.getenv("CHATGPT_SESSIONS_DIR", "./data/chatgpt_sessions"))
  base_dir.mkdir(parents=True, exist_ok=True)
  return str(base_dir / f"{account.account_id}.json")


def select_chatgpt_account(now_ts: Optional[int] = None) -> Tuple[WebAccount, str]:
  """Select the next ChatGPT account and return (account, storage_state_path)."""
  accounts = load_chatgpt_accounts_from_env()
  limit = int(os.getenv("CHATGPT_DAILY_LIMIT", "10"))
  window_hours = int(os.getenv("CHATGPT_WINDOW_HOURS", "24"))
  window_seconds = window_hours * 3600

  store = chatgpt_usage_store_from_env()
  chosen = store.select_and_record(accounts, limit=limit, window_seconds=window_seconds, now_ts=now_ts)
  return chosen, chatgpt_session_path_for_account(chosen)

