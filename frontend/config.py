"""
Frontend configuration management.

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

  # API Base URL for backend calls
  API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
