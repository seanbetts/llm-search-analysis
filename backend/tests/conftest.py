"""Pytest configuration for loading environment variables from .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv


def pytest_configure(config):
  """
  Load environment variables from .env file before running tests.

  This ensures E2E tests have access to API keys defined in the root .env file.
  The .env file is located in the project root, not the backend directory.
  """
  # Find the root .env file (two levels up from backend/tests)
  root_dir = Path(__file__).resolve().parent.parent.parent
  env_file = root_dir / ".env"

  if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ Loaded environment variables from {env_file}")
  else:
    print(f"⚠ Warning: .env file not found at {env_file}")
