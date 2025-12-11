"""Custom exceptions for the LLM Search Analysis API.

This module defines a hierarchy of custom exceptions with error codes and
user-friendly messages for consistent error handling across the application.
"""

from typing import Any, Dict, Optional

from fastapi import status


class APIException(Exception):
  """Base exception for all API errors.

  All custom exceptions should inherit from this class to ensure
  consistent error handling and response formatting.

  Attributes:
    message: User-friendly error message
    error_code: Machine-readable error code
    status_code: HTTP status code
    details: Additional error details (optional)
  """

  def __init__(
    self,
    message: str,
    error_code: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: Optional[Dict[str, Any]] = None,
  ):
    """Initialize base API exception with common error fields."""
    self.message = message
    self.error_code = error_code
    self.status_code = status_code
    self.details = details or {}
    super().__init__(self.message)

  def to_dict(self) -> Dict[str, Any]:
    """Convert exception to dictionary for JSON response."""
    response = {
      "error": {
        "message": self.message,
        "code": self.error_code,
      }
    }
    if self.details:
      response["error"]["details"] = self.details
    return response


# ============================================================================
# Client Errors (4xx) - User-fixable errors
# ============================================================================

class ValidationError(APIException):
  """Request validation failed (422).

  Used when Pydantic validation fails or custom validation logic
  detects invalid input data.
  """

  def __init__(self, message: str = "Validation error", details: Optional[Dict[str, Any]] = None):
    """Build validation error with optional detail payload."""
    super().__init__(
      message=message,
      error_code="VALIDATION_ERROR",
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      details=details,
    )


class ResourceNotFoundError(APIException):
  """Requested resource was not found (404).

  Used when a database query returns no results for a requested ID.
  """

  def __init__(self, resource_type: str, resource_id: Any):
    """Build not-found error including resource metadata."""
    super().__init__(
      message=f"{resource_type} with ID {resource_id} not found",
      error_code="RESOURCE_NOT_FOUND",
      status_code=status.HTTP_404_NOT_FOUND,
      details={"resource_type": resource_type, "resource_id": str(resource_id)},
    )


class InvalidRequestError(APIException):
  """Request is invalid or malformed (400).

  Used for business logic validation failures that aren't caught
  by Pydantic validation.
  """

  def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
    """Build invalid-request error with optional detail payload."""
    super().__init__(
      message=message,
      error_code="INVALID_REQUEST",
      status_code=status.HTTP_400_BAD_REQUEST,
      details=details,
    )


class AuthenticationError(APIException):
  """Authentication failed (401).

  Used when API key or credentials are missing or invalid.
  """

  def __init__(self, message: str = "Authentication required"):
    """Build authentication error with a user-friendly message."""
    super().__init__(
      message=message,
      error_code="AUTHENTICATION_ERROR",
      status_code=status.HTTP_401_UNAUTHORIZED,
    )


class AuthorizationError(APIException):
  """Authorization failed (403).

  Used when user is authenticated but lacks permission for the resource.
  """

  def __init__(self, message: str = "Insufficient permissions"):
    """Build authorization error describing the missing permission."""
    super().__init__(
      message=message,
      error_code="AUTHORIZATION_ERROR",
      status_code=status.HTTP_403_FORBIDDEN,
    )


class RateLimitError(APIException):
  """Rate limit exceeded (429).

  Used when user exceeds API rate limits.
  """

  def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
    """Build rate-limit error optionally including retry-after hint."""
    details = {"retry_after": retry_after} if retry_after else None
    super().__init__(
      message=message,
      error_code="RATE_LIMIT_EXCEEDED",
      status_code=status.HTTP_429_TOO_MANY_REQUESTS,
      details=details,
    )


class ConflictError(APIException):
  """Request conflicts with current resource state (409)."""

  def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
    """Build conflict error when operation cannot proceed."""
    super().__init__(
      message=message,
      error_code="RESOURCE_CONFLICT",
      status_code=status.HTTP_409_CONFLICT,
      details=details,
    )


# ============================================================================
# Server Errors (5xx) - System errors
# ============================================================================

class InternalServerError(APIException):
  """Internal server error (500).

  Used for unexpected errors that aren't caught by more specific handlers.
  """

  def __init__(self, message: str = "Internal server error", details: Optional[Dict[str, Any]] = None):
    """Build internal server error with optional details."""
    super().__init__(
      message=message,
      error_code="INTERNAL_SERVER_ERROR",
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      details=details,
    )


class DatabaseError(APIException):
  """Database operation failed (500).

  Used when SQLAlchemy raises an exception during database operations.
  """

  def __init__(self, message: str = "Database error occurred", details: Optional[Dict[str, Any]] = None):
    """Build database error with optional detail payload."""
    super().__init__(
      message=message,
      error_code="DATABASE_ERROR",
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      details=details,
    )


class ExternalServiceError(APIException):
  """External service call failed (502).

  Used when calls to external APIs (LLM providers) fail.
  """

  def __init__(self, service_name: str, message: str, details: Optional[Dict[str, Any]] = None):
    """Build external service error including service metadata."""
    super().__init__(
      message=f"{service_name} error: {message}",
      error_code="EXTERNAL_SERVICE_ERROR",
      status_code=status.HTTP_502_BAD_GATEWAY,
      details={**(details or {}), "service": service_name},
    )


class ServiceUnavailableError(APIException):
  """Service temporarily unavailable (503).

  Used when the service is down for maintenance or overloaded.
  """

  def __init__(self, message: str = "Service temporarily unavailable"):
    """Build service-unavailable error with optional message."""
    super().__init__(
      message=message,
      error_code="SERVICE_UNAVAILABLE",
      status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class TimeoutError(APIException):
  """Request timeout (504).

  Used when an operation takes too long to complete.
  """

  def __init__(self, operation: str, timeout_seconds: float):
    """Build timeout error with operation context."""
    super().__init__(
      message=f"{operation} timed out after {timeout_seconds} seconds",
      error_code="TIMEOUT_ERROR",
      status_code=status.HTTP_504_GATEWAY_TIMEOUT,
      details={"operation": operation, "timeout": timeout_seconds},
    )


# ============================================================================
# Domain-Specific Errors
# ============================================================================

class ProviderError(ExternalServiceError):
  """LLM provider error.

  Used when an LLM provider (OpenAI, Google, Anthropic) returns an error.
  """

  def __init__(self, provider: str, message: str, details: Optional[Dict[str, Any]] = None):
    """Build provider error with provider name and optional details."""
    super().__init__(
      service_name=f"{provider} provider",
      message=message,
      details=details,
    )


class ModelNotSupportedError(InvalidRequestError):
  """Model is not supported by any provider.

  Used when user requests a model that doesn't exist.
  """

  def __init__(self, model: str, available_models: Optional[list] = None):
    """Build unsupported-model error including available models if provided."""
    details = {"model": model}
    if available_models:
      details["available_models"] = available_models

    super().__init__(
      message=f"Model '{model}' is not supported",
      details=details,
    )


class APIKeyMissingError(InvalidRequestError):
  """API key for provider is missing.

  Used when a provider is requested but its API key isn't configured.
  """

  def __init__(self, provider: str):
    """Build API-key-missing error for a provider."""
    super().__init__(
      message=f"API key for {provider} is not configured",
      details={"provider": provider, "solution": "Add the API key to your .env file"},
    )


class InteractionNotFoundError(ResourceNotFoundError):
  """Interaction (response) not found.

  Used when querying for an interaction that doesn't exist.
  """

  def __init__(self, interaction_id: int):
    """Build not-found error for an interaction."""
    super().__init__(resource_type="Interaction", resource_id=interaction_id)


class DataSourceValidationError(ValidationError):
  """Data source parameter is invalid.

  Used when data_source query parameter has an invalid value.
  """

  def __init__(self, data_source: str):
    """Build invalid-data-source error."""
    super().__init__(
      message=f"Invalid data source: {data_source}",
      details={
        "data_source": data_source,
        "valid_values": ["api", "network_log"],
      },
    )


# ============================================================================
# Error Code Reference
# ============================================================================

ERROR_CODE_REFERENCE = {
  # Client Errors (4xx)
  "VALIDATION_ERROR": "Request validation failed - check your input data",
  "RESOURCE_NOT_FOUND": "The requested resource was not found",
  "INVALID_REQUEST": "The request is invalid or malformed",
  "AUTHENTICATION_ERROR": "Authentication is required",
  "AUTHORIZATION_ERROR": "You don't have permission for this resource",
  "RATE_LIMIT_EXCEEDED": "You've exceeded the API rate limit",

  # Server Errors (5xx)
  "INTERNAL_SERVER_ERROR": "An unexpected error occurred",
  "DATABASE_ERROR": "A database error occurred",
  "EXTERNAL_SERVICE_ERROR": "An external service call failed",
  "SERVICE_UNAVAILABLE": "The service is temporarily unavailable",
  "TIMEOUT_ERROR": "The operation timed out",
}
