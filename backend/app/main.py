"""LLM Search Analysis API - Main application entry point.

This module configures and initializes the FastAPI application for comparing
how different LLM providers (OpenAI, Google Gemini, Anthropic Claude, ChatGPT)
perform live web search.

The application provides:
- RESTful API endpoints for sending prompts and retrieving interactions
- Multi-provider support with normalized response schemas
- Search metrics tracking (queries, sources, citations, rankings)
- Database persistence with SQLite/PostgreSQL support
- CORS middleware for future React frontend integration
- Structured logging with correlation IDs for request tracing
- Comprehensive error handling with custom exception hierarchy

API Documentation:
- OpenAPI/Swagger UI: /docs
- ReDoc: /redoc
- Health check: /health

Environment Configuration:
- Configured via settings in app.config module
- Database URL, API keys, CORS origins, and log level are configurable
- See .env.example for required environment variables
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.endpoints import interactions, providers
from app.config import settings
from app.core.exceptions import APIException, DatabaseError
from app.core.middleware import LoggingMiddleware, get_correlation_id
from app.dependencies import engine


class CorrelationIdFilter(logging.Filter):
  """Add default correlation_id to all log records."""

  def filter(self, record):
    """Add correlation_id to log record if not present."""
    if not hasattr(record, 'correlation_id'):
      record.correlation_id = 'no-correlation-id'
    return True


# Configure logging with more detailed format
logging.basicConfig(
  level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
  format='%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s',
  datefmt='%Y-%m-%d %H:%M:%S'
)

# Add correlation ID filter to all handlers
for handler in logging.root.handlers:
  handler.addFilter(CorrelationIdFilter())

logger = logging.getLogger(__name__)

app = FastAPI(
  title="LLM Search Analysis API",
  description="API for analyzing LLM search capabilities across different providers",
  version="1.0.0",
  docs_url="/docs",
  redoc_url="/redoc",
)

# CORS middleware configuration for future React frontend
app.add_middleware(
  CORSMiddleware,
  allow_origins=settings.CORS_ORIGINS,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Add logging middleware for request/response tracking and correlation IDs
app.add_middleware(LoggingMiddleware)

# Include API routers
app.include_router(interactions.router, prefix="/api/v1")
app.include_router(providers.router, prefix="/api/v1")


@app.get("/")
async def root():
  """Root endpoint - API information."""
  return {
    "name": "LLM Search Analysis API",
    "version": "1.0.0",
    "status": "running",
    "docs": "/docs",
  }


@app.get("/health")
async def health_check():
  """Health check endpoint - verifies API and database connectivity."""
  try:
    # Test database connectivity
    with engine.connect() as conn:
      conn.execute(text("SELECT 1"))

    return {
      "status": "healthy",
      "version": "1.0.0",
      "database": "connected",
    }
  except Exception as e:
    return JSONResponse(
      status_code=503,
      content={
        "status": "unhealthy",
        "database": "error",
        "error": str(e),
      },
    )


# Exception handlers for consistent error responses

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
  """Handle custom API exceptions with error codes.

  This handler catches all custom APIException instances and returns
  a consistent JSON response with error code, message, and details.
  """
  logger.error(
    f"API Exception: {exc.error_code} - {exc.message}",
    extra={
      "correlation_id": get_correlation_id(request),
      "error_code": exc.error_code,
      "status_code": exc.status_code,
      "path": request.url.path,
      "method": request.method,
      "details": exc.details,
    }
  )

  return JSONResponse(
    status_code=exc.status_code,
    content=exc.to_dict(),
  )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
  """Handle Pydantic validation errors (422).

  Converts Pydantic validation errors into user-friendly format
  with field-level error details.
  """
  # Extract field errors
  errors = []
  for error in exc.errors():
    field_path = " -> ".join(str(loc) for loc in error["loc"])
    errors.append({
      "field": field_path,
      "message": error["msg"],
      "type": error["type"],
    })

  logger.warning(
    f"Validation error on {request.url.path}",
    extra={
      "correlation_id": get_correlation_id(request),
      "path": request.url.path,
      "method": request.method,
      "errors": errors,
    }
  )

  return JSONResponse(
    status_code=422,
    content={
      "error": {
        "message": "Request validation failed",
        "code": "VALIDATION_ERROR",
        "details": {
          "errors": errors,
        },
      }
    },
  )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
  """Handle database errors (500).

  Wraps SQLAlchemy errors in our custom DatabaseError format.
  Hides sensitive database details in production.
  """
  logger.error(
    f"Database error on {request.url.path}: {str(exc)}",
    extra={
      "correlation_id": get_correlation_id(request),
      "path": request.url.path,
      "method": request.method,
      "error_type": type(exc).__name__,
    },
    exc_info=True,
  )

  db_error = DatabaseError(
    message="A database error occurred",
    details={"error_type": type(exc).__name__} if settings.DEBUG else None,
  )

  return JSONResponse(
    status_code=db_error.status_code,
    content=db_error.to_dict(),
  )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
  """Global exception handler for unhandled errors (500).

  This is the last line of defense - catches any unexpected errors
  that aren't handled by more specific handlers.
  """
  logger.exception(
    f"Unhandled exception on {request.url.path}",
    extra={
      "correlation_id": get_correlation_id(request),
      "path": request.url.path,
      "method": request.method,
      "error_type": type(exc).__name__,
    },
  )

  from app.core.exceptions import InternalServerError
  error = InternalServerError(
    message="An unexpected error occurred",
    details={"error_type": type(exc).__name__, "error": str(exc)} if settings.DEBUG else None,
  )

  return JSONResponse(
    status_code=error.status_code,
    content=error.to_dict(),
  )
