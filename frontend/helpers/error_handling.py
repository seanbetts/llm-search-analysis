"""Unified error handling for API calls.

This module provides consistent error handling across the frontend,
converting API client exceptions into user-friendly Streamlit messages.
"""

from typing import Any, Callable, Optional

import streamlit as st

from frontend.api_client import (
  APIClientError,
  APIConnectionError,
  APINotFoundError,
  APIServerError,
  APITimeoutError,
  APIValidationError,
)


def safe_api_call(
  callable_func: Callable,
  *args,
  success_message: Optional[str] = None,
  show_spinner: bool = True,
  spinner_text: str = "Processing...",
  **kwargs
) -> tuple[Any, Optional[str]]:
  """Safely execute an API call with consistent error handling.

  This wrapper function catches APIClient exceptions and displays
  appropriate Streamlit error messages. It provides a single place
  to manage error formatting and user feedback.

  Args:
    callable_func: The API client method to call
    *args: Positional arguments for the callable
    success_message: Optional success message to display on completion
    show_spinner: Whether to show a spinner during execution
    spinner_text: Text to display in spinner
    **kwargs: Keyword arguments for the callable

  Returns:
    tuple[Any, Optional[str]]: (result, error_message)
      - result: The return value from the callable (None if error occurred)
      - error_message: Error message string if error occurred, None otherwise

  Example:
    result, error = safe_api_call(
      api_client.send_prompt,
      prompt="Test",
      provider="openai",
      model="gpt-5.1",
      success_message="Prompt sent successfully!"
    )
    if error:
      st.error(f"Error: {error}")
    else:
      st.success("Success!")
      # Use result...
  """
  error_message = None
  result = None

  try:
    if show_spinner:
      with st.spinner(spinner_text):
        result = callable_func(*args, **kwargs)
    else:
      result = callable_func(*args, **kwargs)

    if success_message:
      st.success(success_message)

  except APINotFoundError as e:
    error_message = f"Resource not found: {str(e)}"

  except APITimeoutError:
    error_message = (
      "Request timed out. The model may be taking too long to respond. "
      "Please try again."
    )

  except APIConnectionError:
    error_message = (
      "Cannot connect to API server. Please ensure the backend is running "
      "on http://localhost:8000"
    )

  except APIValidationError as e:
    error_message = f"Invalid request: {str(e)}"

  except APIServerError as e:
    error_message = f"Server error: {str(e)}"

  except APIClientError as e:
    # Catch-all for other API errors
    error_message = f"API error: {str(e)}"

  except Exception as e:
    # Catch-all for unexpected errors
    error_message = f"Unexpected error: {str(e)}"

  return result, error_message
