"""Middleware for request/response logging and tracking.

This module provides middleware for:
- Request/response logging with timing
- Correlation ID tracking across requests
- Request context injection
"""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
  """Middleware for logging all requests and responses with correlation IDs.

  This middleware:
  - Generates or extracts correlation IDs from requests
  - Logs request details (method, path, client, correlation ID)
  - Tracks request duration
  - Logs response details (status code, duration)
  - Adds correlation ID to response headers
  """

  async def dispatch(self, request: Request, call_next: Callable) -> Response:
    """Process request and response with logging."""
    # Generate or extract correlation ID
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
      correlation_id = str(uuid.uuid4())

    # Add correlation ID to request state for use in handlers
    request.state.correlation_id = correlation_id

    # Get client IP
    client_host = request.client.host if request.client else "unknown"

    # Start timing
    start_time = time.time()

    # Log incoming request
    logger.info(
      f"Request started: {request.method} {request.url.path}",
      extra={
        "correlation_id": correlation_id,
        "method": request.method,
        "path": request.url.path,
        "query_params": str(request.query_params),
        "client_host": client_host,
        "user_agent": request.headers.get("user-agent", "unknown"),
      }
    )

    # Process request
    try:
      response = await call_next(request)
    except Exception as e:
      # Log exception
      duration = time.time() - start_time
      logger.error(
        f"Request failed: {request.method} {request.url.path}",
        extra={
          "correlation_id": correlation_id,
          "method": request.method,
          "path": request.url.path,
          "duration_ms": round(duration * 1000, 2),
          "error": str(e),
        },
        exc_info=True,
      )
      raise

    # Calculate duration
    duration = time.time() - start_time

    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    # Log response
    log_level = logging.INFO if response.status_code < 400 else logging.WARNING
    logger.log(
      log_level,
      f"Request completed: {request.method} {request.url.path} - {response.status_code}",
      extra={
        "correlation_id": correlation_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round(duration * 1000, 2),
        "client_host": client_host,
      }
    )

    return response


class CorrelationIDMiddleware(BaseHTTPMiddleware):
  """Lightweight middleware that only adds correlation IDs.

  Use this if you want correlation IDs without full request logging.
  """

  async def dispatch(self, request: Request, call_next: Callable) -> Response:
    """Add correlation ID to request and response."""
    # Generate or extract correlation ID
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
      correlation_id = str(uuid.uuid4())

    # Add to request state
    request.state.correlation_id = correlation_id

    # Process request
    response = await call_next(request)

    # Add to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response


def get_correlation_id(request: Request) -> str:
  """Get correlation ID from request state.

  Args:
    request: FastAPI request object

  Returns:
    Correlation ID string
  """
  return getattr(request.state, "correlation_id", "no-correlation-id")
