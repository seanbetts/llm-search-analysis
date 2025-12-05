"""
Configuration management for the application.

Loads environment variables and provides configuration settings.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # ChatGPT Account Credentials (for network capture mode)
    CHATGPT_EMAIL = os.getenv("CHATGPT_EMAIL")
    CHATGPT_PASSWORD = os.getenv("CHATGPT_PASSWORD")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/data/llm_search.db")

    @classmethod
    def get_api_keys(cls) -> dict:
        """
        Get all API keys as a dictionary.

        Returns:
            Dictionary of provider names to API keys
        """
        return {
            "openai": cls.OPENAI_API_KEY,
            "google": cls.GOOGLE_API_KEY,
            "anthropic": cls.ANTHROPIC_API_KEY,
        }

    @classmethod
    def validate_api_keys(cls) -> dict:
        """
        Check which API keys are configured.

        Returns:
            Dictionary of provider names to boolean (True if key exists)
        """
        return {
            "openai": bool(cls.OPENAI_API_KEY),
            "google": bool(cls.GOOGLE_API_KEY),
            "anthropic": bool(cls.ANTHROPIC_API_KEY),
        }

    @classmethod
    def ensure_data_directory(cls):
        """Create data directory if it doesn't exist."""
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
