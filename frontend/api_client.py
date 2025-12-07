"""
API Client for LLM Search Analysis Backend.

This module provides a client library for interacting with the FastAPI backend.
"""

import time
from typing import Dict, List, Optional, Any
import httpx


class APIClientError(Exception):
  """Base exception for API client errors."""
  pass


class APITimeoutError(APIClientError):
  """Exception raised when API request times out."""
  pass


class APIConnectionError(APIClientError):
  """Exception raised when connection to API fails."""
  pass


class APIValidationError(APIClientError):
  """Exception raised when request validation fails."""
  pass


class APINotFoundError(APIClientError):
  """Exception raised when resource is not found."""
  pass


class APIServerError(APIClientError):
  """Exception raised when server encounters an error."""
  pass


class APIClient:
  """
  Client for interacting with the LLM Search Analysis FastAPI backend.

  Features:
  - Connection pooling for efficient HTTP requests
  - Automatic retry with exponential backoff for transient failures
  - Configurable timeouts per operation type
  - User-friendly error messages

  Example:
    >>> client = APIClient(base_url="http://localhost:8000")
    >>> providers = client.get_providers()
    >>> response = client.send_prompt(
    ...     prompt="What is AI?",
    ...     provider="openai",
    ...     model="gpt-5.1"
    ... )
  """

  def __init__(
    self,
    base_url: str = "http://localhost:8000",
    timeout_default: float = 30.0,
    timeout_send_prompt: float = 120.0,
    max_retries: int = 3,
    pool_connections: int = 10,
    pool_maxsize: int = 20,
  ):
    """
    Initialize API client.

    Args:
      base_url: Base URL of the FastAPI backend (default: http://localhost:8000)
      timeout_default: Default timeout for API requests in seconds (default: 30.0)
      timeout_send_prompt: Timeout for send_prompt requests in seconds (default: 120.0)
      max_retries: Maximum number of retry attempts for transient failures (default: 3)
      pool_connections: Number of connection pools to cache (default: 10)
      pool_maxsize: Maximum number of connections to save in the pool (default: 20)
    """
    self.base_url = base_url.rstrip("/")
    self.timeout_default = timeout_default
    self.timeout_send_prompt = timeout_send_prompt
    self.max_retries = max_retries
    self.pool_connections = pool_connections
    self.pool_maxsize = pool_maxsize
    self._backoff_min = 1
    self._backoff_max = 10

    self.client = self._build_client()

  def __del__(self):
    """Clean up HTTP client on deletion."""
    if hasattr(self, 'client'):
      self.client.close()

  def close(self):
    """Explicitly close the HTTP client."""
    self.client.close()

  def _build_client(self) -> httpx.Client:
    """Create a configured httpx client instance."""
    limits = httpx.Limits(
      max_connections=self.pool_maxsize,
      max_keepalive_connections=self.pool_connections
    )
    timeout = httpx.Timeout(self.timeout_default)
    return httpx.Client(
      base_url=self.base_url,
      limits=limits,
      timeout=timeout
    )

  def _reset_client(self):
    """Reset the underlying HTTP client (used after connection errors)."""
    try:
      if hasattr(self, "client"):
        self.client.close()
    finally:
      self.client = self._build_client()

  def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
    """
    Handle HTTP response and raise appropriate exceptions.

    Args:
      response: httpx Response object

    Returns:
      Parsed JSON response, or empty dict for 204 No Content

    Raises:
      APIValidationError: For 422 validation errors
      APINotFoundError: For 404 not found errors
      APIServerError: For 500+ server errors
      APIClientError: For other error responses
    """
    try:
      response.raise_for_status()
      # Handle 204 No Content responses
      if response.status_code == 204:
        return {}
      return response.json()
    except httpx.HTTPStatusError as e:
      status_code = e.response.status_code

      try:
        error_data = e.response.json()
        error_message = error_data.get("detail", str(e))
        if isinstance(error_message, list):
          # Validation errors return a list
          error_message = "; ".join([f"{err.get('loc', '')}: {err.get('msg', '')}" for err in error_message])
      except Exception:
        error_message = str(e)

      if status_code == 422:
        raise APIValidationError(f"Validation error: {error_message}")
      elif status_code == 404:
        raise APINotFoundError(f"Resource not found: {error_message}")
      elif status_code >= 500:
        raise APIServerError(f"Server error: {error_message}")
      else:
        raise APIClientError(f"API error ({status_code}): {error_message}")

  def _request(
    self,
    method: str,
    path: str,
    timeout: Optional[float] = None,
    **kwargs
  ) -> Dict[str, Any]:
    """
    Make HTTP request with retry logic.

    Args:
      method: HTTP method (GET, POST, DELETE, etc.)
      path: API endpoint path (e.g., "/api/v1/providers")
      timeout: Optional timeout override
      **kwargs: Additional arguments for httpx request

    Returns:
      Parsed JSON response

    Raises:
      APITimeoutError: If request times out
      APIConnectionError: If connection fails
      Various APIClientError subclasses for other errors
    """
    backoff = self._backoff_min
    attempts = 0

    while attempts < self.max_retries:
      try:
        # Use custom timeout if provided, otherwise use default from client
        if timeout is not None:
          kwargs['timeout'] = timeout

        response = self.client.request(method, path, **kwargs)
        return self._handle_response(response)

      except httpx.TimeoutException as e:
        attempts += 1
        if attempts >= self.max_retries:
          raise APITimeoutError(f"Request timed out: {str(e)}")
        time.sleep(min(backoff, self._backoff_max))
        backoff *= 2
        continue

      except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
        attempts += 1
        self._reset_client()
        if attempts >= self.max_retries:
          raise APIConnectionError(f"Failed to connect to API: {str(e)}")
        time.sleep(min(backoff, self._backoff_max))
        backoff *= 2
        continue

      except (APIClientError, APIValidationError, APINotFoundError, APIServerError):
        # Re-raise our custom exceptions
        raise
      except Exception as e:
        raise APIClientError(f"Unexpected error: {str(e)}")

  def send_prompt(
    self,
    prompt: str,
    provider: str,
    model: str,
    data_mode: str = "api",
    headless: bool = True
  ) -> Dict[str, Any]:
    """
    Send a prompt to an LLM provider and get the response.

    Args:
      prompt: The prompt text to send (1-10000 characters)
      provider: Provider name (openai, google, anthropic, chatgpt)
      model: Model identifier (e.g., "gpt-5.1", "gemini-2.5-flash")
      data_mode: Data collection mode - "api" or "network_log" (default: "api")
      headless: Run browser in headless mode for network_log mode (default: True)

    Returns:
      Dictionary containing:
        - interaction_id: ID of saved interaction
        - response_text: LLM response text
        - search_queries: List of search queries made
        - citations: List of citations in response
        - provider: Provider used
        - model: Model used
        - response_time_ms: Response time in milliseconds
        - created_at: Timestamp of interaction
        - And more...

    Raises:
      APIValidationError: If prompt/provider/model is invalid
      APIServerError: If backend or LLM API fails
      APITimeoutError: If request takes longer than timeout

    Example:
      >>> response = client.send_prompt(
      ...     prompt="What is quantum computing?",
      ...     provider="openai",
      ...     model="gpt-5.1"
      ... )
      >>> print(response["response_text"])
    """
    payload = {
      "prompt": prompt,
      "provider": provider,
      "model": model,
      "data_mode": data_mode,
      "headless": headless
    }

    return self._request(
      "POST",
      "/api/v1/interactions/send",
      json=payload,
      timeout=self.timeout_send_prompt
    )

  def save_network_log(
    self,
    provider: str,
    model: str,
    prompt: str,
    response_text: str,
    search_queries: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
    citations: List[Dict[str, Any]],
    response_time_ms: int,
    raw_response: Optional[Dict[str, Any]] = None,
    extra_links_count: int = 0,
  ) -> Dict[str, Any]:
    """
    Save network_log mode data captured by frontend.

    This method is used when the frontend captures LLM interaction data via
    browser automation (network_log mode). The captured data is sent to the
    backend for database persistence.

    Args:
      provider: Provider name (openai, google, anthropic)
      model: Model name used
      prompt: The prompt text
      response_text: The response text from the LLM
      search_queries: List of search query dictionaries
      sources: List of source dictionaries (for network_log mode)
      citations: List of citation dictionaries
      response_time_ms: Response time in milliseconds
      raw_response: Optional raw response data
      extra_links_count: Number of extra links (citations not from search)

    Returns:
      Dictionary containing saved interaction data including interaction_id

    Raises:
      APIValidationError: If data is invalid
      APIServerError: If backend fails
      APITimeoutError: If request times out

    Example:
      >>> response = client.save_network_log(
      ...     provider="openai",
      ...     model="chatgpt-free",
      ...     prompt="What is AI?",
      ...     response_text="AI stands for...",
      ...     search_queries=[{"query": "AI definition", "sources": []}],
      ...     sources=[{"url": "https://example.com", "title": "Example"}],
      ...     citations=[],
      ...     response_time_ms=5000
      ... )
      >>> print(response["interaction_id"])
    """
    payload = {
      "provider": provider,
      "model": model,
      "prompt": prompt,
      "response_text": response_text,
      "search_queries": search_queries,
      "sources": sources,
      "citations": citations,
      "response_time_ms": response_time_ms,
      "raw_response": raw_response,
      "extra_links_count": extra_links_count,
    }

    return self._request(
      "POST",
      "/api/v1/interactions/save-network-log",
      json=payload,
      timeout=self.timeout_send_prompt
    )

  def get_recent_interactions(
    self,
    page: int = 1,
    page_size: int = 20,
    data_source: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
  ) -> Dict[str, Any]:
    """
    Get recent interactions with pagination and optional filtering.

    Args:
      page: Page number (1-indexed, default: 1)
      page_size: Number of items per page (1-100, default: 20)
      data_source: Optional filter by data source ("api" or "network_log")
      provider: Optional filter by provider name (e.g., "openai")
      model: Optional filter by model name (e.g., "gpt-5.1")
      date_from: Optional filter by created_at >= date_from (ISO 8601 format)
      date_to: Optional filter by created_at <= date_to (ISO 8601 format)

    Returns:
      Dict containing:
        - items: List of interaction summaries, each containing:
          - interaction_id: Unique interaction ID
          - prompt: The prompt text
          - provider: Provider used
          - model: Model used
          - response_time_ms: Response time
          - data_source: Data source (api/network_log)
          - created_at: Timestamp
          - search_query_count: Number of search queries
          - source_count: Number of sources
          - citation_count: Number of citations
          - extra_links_count: Number of extra links
          - average_rank: Average rank of sources
        - pagination: Pagination metadata containing:
          - page: Current page number
          - page_size: Items per page
          - total_items: Total number of items
          - total_pages: Total number of pages
          - has_next: Whether there is a next page
          - has_prev: Whether there is a previous page

    Raises:
      APIServerError: If backend fails

    Example:
      >>> result = client.get_recent_interactions(page=1, page_size=10, provider="openai")
      >>> for interaction in result["items"]:
      ...     print(f"{interaction['model']}: {interaction['prompt'][:50]}")
      >>> print(f"Page {result['pagination']['page']} of {result['pagination']['total_pages']}")
    """
    params = {"page": page, "page_size": page_size}
    if data_source:
      params["data_source"] = data_source
    if provider:
      params["provider"] = provider
    if model:
      params["model"] = model
    if date_from:
      params["date_from"] = date_from
    if date_to:
      params["date_to"] = date_to

    return self._request("GET", "/api/v1/interactions/recent", params=params)

  def get_interaction(self, interaction_id: int) -> Dict[str, Any]:
    """
    Get full details of a specific interaction.

    Args:
      interaction_id: The interaction ID

    Returns:
      Full interaction details including:
        - All fields from get_recent_interactions()
        - response_text: Full LLM response
        - search_queries: Detailed search query data with sources
        - citations: Detailed citation data
        - raw_response: Raw API response (if available)

    Raises:
      APINotFoundError: If interaction doesn't exist
      APIServerError: If backend fails

    Example:
      >>> interaction = client.get_interaction(123)
      >>> print(interaction["response_text"])
      >>> for query in interaction["search_queries"]:
      ...     print(f"Query: {query['query']}")
      ...     for source in query["sources"]:
      ...         print(f"  - {source['title']}: {source['url']}")
    """
    return self._request("GET", f"/api/v1/interactions/{interaction_id}")

  def delete_interaction(self, interaction_id: int) -> bool:
    """
    Delete an interaction and all associated data.

    Args:
      interaction_id: The interaction ID to delete

    Returns:
      True if deletion was successful

    Raises:
      APINotFoundError: If interaction doesn't exist
      APIServerError: If backend fails

    Example:
      >>> success = client.delete_interaction(123)
      >>> if success:
      ...     print("Interaction deleted successfully")
    """
    try:
      self._request("DELETE", f"/api/v1/interactions/{interaction_id}")
      return True
    except APINotFoundError:
      raise
    except Exception as e:
      raise APIServerError(f"Failed to delete interaction: {str(e)}")

  def get_providers(self) -> List[Dict[str, Any]]:
    """
    Get list of available LLM providers with their supported models.

    Returns:
      List of provider information, each containing:
        - name: Provider internal name (openai, google, anthropic)
        - display_name: Human-readable provider name
        - is_active: Whether provider is currently active (has API key)
        - supported_models: List of model identifiers

    Raises:
      APIServerError: If backend fails

    Example:
      >>> providers = client.get_providers()
      >>> for provider in providers:
      ...     print(f"{provider['display_name']}:")
      ...     for model in provider['supported_models']:
      ...         print(f"  - {model}")
    """
    return self._request("GET", "/api/v1/providers")

  def get_models(self) -> List[str]:
    """
    Get list of all available models across all providers.

    Returns:
      List of model identifiers

    Raises:
      APIServerError: If backend fails

    Example:
      >>> models = client.get_models()
      >>> print(f"Available models: {', '.join(models)}")
    """
    return self._request("GET", "/api/v1/providers/models")

  def export_interaction_markdown(self, interaction_id: int) -> str:
    """
    Export an interaction as formatted Markdown.

    Args:
      interaction_id: The interaction ID to export

    Returns:
      Markdown formatted string with full interaction details

    Raises:
      APINotFoundError: If interaction doesn't exist
      APIServerError: If backend fails

    Example:
      >>> markdown = client.export_interaction_markdown(123)
      >>> with open("interaction_123.md", "w") as f:
      ...     f.write(markdown)
    """
    try:
      # Make request directly to get text response (not JSON)
      response = self.client.get(
        f"/api/v1/interactions/{interaction_id}/export/markdown",
        timeout=self.timeout_default
      )
      response.raise_for_status()
      return response.text
    except httpx.HTTPStatusError as e:
      status_code = e.response.status_code
      if status_code == 404:
        raise APINotFoundError(f"Interaction {interaction_id} not found")
      elif status_code >= 500:
        raise APIServerError(f"Server error exporting interaction: {str(e)}")
      else:
        raise APIClientError(f"Failed to export interaction: {str(e)}")
    except httpx.TimeoutException as e:
      raise APITimeoutError(f"Export request timed out: {str(e)}")
    except httpx.ConnectError as e:
      raise APIConnectionError(f"Failed to connect to API: {str(e)}")
    except Exception as e:
      raise APIClientError(f"Unexpected error exporting interaction: {str(e)}")

  def health_check(self) -> Dict[str, Any]:
    """
    Check API health and database connectivity.

    Returns:
      Health status containing:
        - status: "healthy" or "unhealthy"
        - version: API version
        - database: "connected" or "error"

    Raises:
      APIConnectionError: If cannot connect to API

    Example:
      >>> health = client.health_check()
      >>> if health["status"] == "healthy":
      ...     print("API is operational")
    """
    return self._request("GET", "/health")
