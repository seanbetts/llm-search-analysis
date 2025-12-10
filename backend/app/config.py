"""Application configuration settings.

This module defines the application's configuration using Pydantic Settings,
which loads values from environment variables and .env files with type validation.

The Settings class manages:
- Database connection (SQLite/PostgreSQL URLs)
- LLM provider API keys (OpenAI, Google, Anthropic)
- ChatGPT network capture configuration (session file, browser settings)
- CORS origins for frontend integration
- Server configuration (host, port, debug mode)
- Logging levels

Configuration Priority:
1. Environment variables (highest priority)
2. .env file in project root
3. Default values defined in this module

Example:
    from app.config import settings

    # Access configuration values
    print(settings.DATABASE_URL)
    print(settings.OPENAI_API_KEY)

Database URL Normalization:
    The DATABASE_URL validator handles legacy path formats and ensures
    compatibility between Docker environments (/app/data) and local
    development (backend/data relative paths).
"""

from typing import Dict, List
import logging
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_URL = "sqlite:////app/data/llm_search.db"
BACKEND_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "llm_search.db"
BACKEND_FALLBACK_URL = f"sqlite:///{BACKEND_FALLBACK_PATH.as_posix()}"


class Settings(BaseSettings):
  """Application configuration settings using Pydantic Settings.

  This class defines all configurable settings for the LLM Search Analysis API.
  Values are loaded from environment variables and .env files with automatic
  type validation and conversion.

  Attributes:
    APP_NAME: Application name
    VERSION: API version
    DEBUG: Enable debug mode
    HOST: Server bind address
    PORT: Server port number
    CORS_ORIGINS: Allowed CORS origins for frontend access
    DATABASE_URL: SQLite or PostgreSQL connection URL
    OPENAI_API_KEY: OpenAI API key for GPT models
    GOOGLE_API_KEY: Google API key for Gemini models
    ANTHROPIC_API_KEY: Anthropic API key for Claude models
    CHATGPT_SESSION_FILE: Path to ChatGPT session file for network capture
    NETWORK_LOGS_DIR: Directory for storing network capture logs
    BROWSER_HEADLESS: Run browser in headless mode for network capture
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  """

  # Application settings
  APP_NAME: str = "LLM Search Analysis API"
  VERSION: str = "1.0.0"
  DEBUG: bool = False

  # Server settings
  HOST: str = "0.0.0.0"
  PORT: int = 8000

  # CORS settings
  CORS_ORIGINS: List[str] = Field(
    default=["http://localhost:8501", "http://localhost:3000"],
    description="Allowed CORS origins (Streamlit and React)"
  )

  # Database settings
  DATABASE_URL: str = Field(
    default=DEFAULT_DB_URL,
    description="SQLite database URL (stored in /app/data/llm_search.db)"
  )

  # API Keys for LLM providers
  OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
  GOOGLE_API_KEY: str = Field(default="", description="Google API key")
  ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")

  # ChatGPT session configuration (for network capture)
  CHATGPT_SESSION_FILE: str = Field(
    default="./data/chatgpt_session.json",
    description="Path to ChatGPT session file"
  )

  # Network capture settings
  NETWORK_LOGS_DIR: str = Field(
    default="./data/network_logs",
    description="Directory for network capture logs"
  )
  BROWSER_HEADLESS: bool = Field(
    default=True,
    description="Run browser in headless mode for network capture"
  )

  # Logging
  LOG_LEVEL: str = Field(
    default="INFO",
    description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
  )

  # Batch processing settings
  BATCH_MAX_CONCURRENCY: int = Field(
    default=6,
    description="Maximum number of concurrent provider requests for batch jobs"
  )
  BATCH_PER_PROVIDER_CONCURRENCY: int = Field(
    default=2,
    description="Default concurrency per provider for batch jobs"
  )
  BATCH_MAX_CONCURRENCY_OPENAI: int = Field(
    default=0,
    description="Override concurrency limit for OpenAI (0 = use default)"
  )
  BATCH_MAX_CONCURRENCY_GOOGLE: int = Field(
    default=0,
    description="Override concurrency limit for Google (0 = use default)"
  )
  BATCH_MAX_CONCURRENCY_ANTHROPIC: int = Field(
    default=0,
    description="Override concurrency limit for Anthropic (0 = use default)"
  )

  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=True,
    extra="ignore",
  )

  @field_validator("DATABASE_URL", mode="before")
  @classmethod
  def normalize_database_url(cls, value: str) -> str:
    """Ensure old ../data paths are normalized to backend/data.

    Older configs pointed at sqlite:///../data/llm_search.db which
    resolves to the removed root-level data directory. This guard keeps
    deployments pointed at backend/data even if the env var wasn't updated.
    """
    logger = logging.getLogger(__name__)

    legacy_paths = {
      "sqlite:///../data/llm_search.db",
      "sqlite:///./data/llm_search.db",
      "sqlite:///./backend/data/llm_search.db",
      "sqlite:////app/data/llm_search.db",
    }

    if isinstance(value, str) and value in legacy_paths:
      logger.warning(
        "DATABASE_URL=%s detected; normalizing to %s so backend and frontend share the same database location",
        value,
        DEFAULT_DB_URL,
      )
      return DEFAULT_DB_URL

    app_path = Path("/app/data/llm_search.db")
    if isinstance(value, str) and value == DEFAULT_DB_URL and not app_path.exists():
      logger.info(
        "/app/data/llm_search.db not found; falling back to %s",
        BACKEND_FALLBACK_URL,
      )
      return BACKEND_FALLBACK_URL
    return value

  def get_batch_provider_limits(self) -> Dict[str, int]:
    """Return per-provider concurrency limits, applying overrides when set."""
    base = self.BATCH_PER_PROVIDER_CONCURRENCY
    return {
      "openai": self.BATCH_MAX_CONCURRENCY_OPENAI or base,
      "google": self.BATCH_MAX_CONCURRENCY_GOOGLE or base,
      "anthropic": self.BATCH_MAX_CONCURRENCY_ANTHROPIC or base,
    }


# Create global settings instance
settings = Settings()
