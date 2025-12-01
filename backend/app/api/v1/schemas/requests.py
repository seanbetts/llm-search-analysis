from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class SendPromptRequest(BaseModel):
  """Request schema for sending a prompt to an LLM provider."""

  prompt: str = Field(
    ...,
    min_length=1,
    max_length=10000,
    description="The prompt text to send to the LLM",
    examples=["What are the latest developments in AI?"]
  )

  provider: str = Field(
    ...,
    description="LLM provider name (openai, google, anthropic, chatgpt)",
    examples=["openai"]
  )

  model: str = Field(
    ...,
    description="Model name to use",
    examples=["gpt-4o", "gemini-2.0-flash-exp", "claude-3-7-sonnet-20250219"]
  )

  data_mode: str = Field(
    default="api",
    description="Data collection mode: 'api' or 'network_log'",
    examples=["api", "network_log"]
  )

  headless: bool = Field(
    default=True,
    description="Run browser in headless mode (for network_log mode only)"
  )

  @field_validator("prompt")
  @classmethod
  def validate_prompt(cls, v: str) -> str:
    """Validate prompt for XSS and basic security."""
    # Remove leading/trailing whitespace
    v = v.strip()

    # Check for empty prompt after stripping
    if not v:
      raise ValueError("Prompt cannot be empty or whitespace only")

    # Basic XSS prevention - check for script tags
    if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
      raise ValueError("Prompt contains disallowed script tags")

    # Check for other potentially dangerous HTML tags
    dangerous_tags = ["iframe", "object", "embed", "link", "style"]
    for tag in dangerous_tags:
      if re.search(rf"<{tag}.*?>", v, re.IGNORECASE):
        raise ValueError(f"Prompt contains disallowed tag: {tag}")

    return v

  @field_validator("provider")
  @classmethod
  def validate_provider(cls, v: str) -> str:
    """Validate provider name."""
    valid_providers = ["openai", "google", "anthropic", "chatgpt"]
    v_lower = v.lower()
    if v_lower not in valid_providers:
      raise ValueError(
        f"Invalid provider '{v}'. Must be one of: {', '.join(valid_providers)}"
      )
    return v_lower

  @field_validator("data_mode")
  @classmethod
  def validate_data_mode(cls, v: str) -> str:
    """Validate data collection mode."""
    valid_modes = ["api", "network_log"]
    v_lower = v.lower()
    if v_lower not in valid_modes:
      raise ValueError(
        f"Invalid data_mode '{v}'. Must be one of: {', '.join(valid_modes)}"
      )
    return v_lower

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "prompt": "What are the latest developments in quantum computing?",
          "provider": "openai",
          "model": "gpt-4o",
          "data_mode": "api",
          "headless": True
        }
      ]
    }
  }


class BatchRequest(BaseModel):
  """Request schema for batch processing multiple prompts."""

  prompts: List[str] = Field(
    ...,
    min_length=1,
    max_length=100,
    description="List of prompts to process",
    examples=[["What is AI?", "What is ML?"]]
  )

  provider: str = Field(
    ...,
    description="LLM provider name (openai, google, anthropic, chatgpt)",
    examples=["openai"]
  )

  models: List[str] = Field(
    ...,
    min_length=1,
    description="List of models to test against",
    examples=[["gpt-4o", "gpt-4o-mini"]]
  )

  data_mode: str = Field(
    default="api",
    description="Data collection mode: 'api' or 'network_log'",
    examples=["api"]
  )

  headless: bool = Field(
    default=True,
    description="Run browser in headless mode (for network_log mode only)"
  )

  @field_validator("prompts")
  @classmethod
  def validate_prompts(cls, v: List[str]) -> List[str]:
    """Validate each prompt in the list."""
    if not v:
      raise ValueError("Prompts list cannot be empty")

    # Validate each prompt
    validated_prompts = []
    for i, prompt in enumerate(v):
      prompt = prompt.strip()
      if not prompt:
        raise ValueError(f"Prompt at index {i} is empty or whitespace only")
      if len(prompt) > 10000:
        raise ValueError(f"Prompt at index {i} exceeds maximum length of 10000 characters")
      validated_prompts.append(prompt)

    return validated_prompts

  @field_validator("provider")
  @classmethod
  def validate_provider(cls, v: str) -> str:
    """Validate provider name."""
    valid_providers = ["openai", "google", "anthropic", "chatgpt"]
    v_lower = v.lower()
    if v_lower not in valid_providers:
      raise ValueError(
        f"Invalid provider '{v}'. Must be one of: {', '.join(valid_providers)}"
      )
    return v_lower

  @field_validator("models")
  @classmethod
  def validate_models(cls, v: List[str]) -> List[str]:
    """Validate models list."""
    if not v:
      raise ValueError("Models list cannot be empty")
    return v

  @field_validator("data_mode")
  @classmethod
  def validate_data_mode(cls, v: str) -> str:
    """Validate data collection mode."""
    valid_modes = ["api", "network_log"]
    v_lower = v.lower()
    if v_lower not in valid_modes:
      raise ValueError(
        f"Invalid data_mode '{v}'. Must be one of: {', '.join(valid_modes)}"
      )
    return v_lower

  model_config = {
    "json_schema_extra": {
      "examples": [
        {
          "prompts": [
            "What is artificial intelligence?",
            "Explain machine learning"
          ],
          "provider": "openai",
          "models": ["gpt-4o", "gpt-4o-mini"],
          "data_mode": "api",
          "headless": True
        }
      ]
    }
  }
