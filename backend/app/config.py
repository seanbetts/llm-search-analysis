from typing import List
import logging
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB_URL = "sqlite:////backend/data/llm_search.db"
BACKEND_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "llm_search.db"
BACKEND_FALLBACK_URL = f"sqlite:///{BACKEND_FALLBACK_PATH.as_posix()}"


class Settings(BaseSettings):
  """Application configuration settings using Pydantic Settings"""

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
    description="SQLite database URL (stored in /backend/data/llm_search.db)"
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

  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=True,
    extra="ignore",
  )

  @field_validator("DATABASE_URL", mode="before")
  @classmethod
  def normalize_database_url(cls, value: str) -> str:
    """
    Ensure old ../data paths are normalized to backend/data.

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

    backend_path = Path("/backend/data/llm_search.db")
    if isinstance(value, str) and value == DEFAULT_DB_URL and not backend_path.exists():
      logger.info(
        "/backend/data/llm_search.db not found; falling back to %s",
        BACKEND_FALLBACK_URL,
      )
      return BACKEND_FALLBACK_URL
    return value


# Create global settings instance
settings = Settings()
