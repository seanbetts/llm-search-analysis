"""Frontend configuration management.

Loads environment variables needed by the Streamlit frontend.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
  """Frontend configuration."""

  # ChatGPT Account Credentials (for network capture mode)
  # These are needed because network capture runs client-side in the frontend
  CHATGPT_EMAIL = os.getenv("CHATGPT_EMAIL")
  CHATGPT_PASSWORD = os.getenv("CHATGPT_PASSWORD")

  # ChatGPT account pool (Docker/cloud friendly).
  # Prefer mounting JSON via Docker secrets and pointing CHATGPT_ACCOUNTS_FILE at it.
  CHATGPT_ACCOUNTS_FILE = os.getenv("CHATGPT_ACCOUNTS_FILE")
  CHATGPT_ACCOUNTS_JSON = os.getenv("CHATGPT_ACCOUNTS_JSON")
  CHATGPT_DAILY_LIMIT = int(os.getenv("CHATGPT_DAILY_LIMIT", "10"))
  CHATGPT_WINDOW_HOURS = int(os.getenv("CHATGPT_WINDOW_HOURS", "24"))
  CHATGPT_USAGE_DB_PATH = os.getenv("CHATGPT_USAGE_DB_PATH", "./data/account_usage.sqlite")
  CHATGPT_SESSIONS_DIR = os.getenv("CHATGPT_SESSIONS_DIR", "./data/chatgpt_sessions")

  # API Base URL for backend calls
  API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
