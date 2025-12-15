"""Interactions API endpoints."""

import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import PlainTextResponse

from app.api.v1.schemas.requests import BatchRequest, SaveNetworkLogRequest, SendPromptRequest
from app.api.v1.schemas.responses import (
  BatchStatus,
  PaginatedInteractionList,
  PaginationMeta,
  SendPromptResponse,
)
from app.core.exceptions import (
  APIKeyMissingError,
  InteractionNotFoundError,
  InvalidRequestError,
  ModelNotSupportedError,
  ProviderError,
)
from app.dependencies import (
  get_batch_service,
  get_export_service,
  get_interaction_service,
  get_provider_service,
)
from app.services.batch_service import BatchService
from app.services.citation_tagging_jobs import enqueue_web_citation_tagging
from app.services.export_service import ExportService
from app.services.interaction_service import InteractionService
from app.services.provider_service import ProviderService

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post(
  "/batch",
  response_model=BatchStatus,
  status_code=status.HTTP_202_ACCEPTED,
  summary="Start backend-managed batch processing",
  description="Submit prompts and models for asynchronous batch execution. "
  "Use GET /interactions/batch/{batch_id} to poll status as results complete.",
)
async def start_batch(
  request: BatchRequest,
  batch_service: BatchService = Depends(get_batch_service),
):
  """Start a backend-managed batch job."""
  try:
    return await batch_service.start_batch(request)
  except ValueError as exc:
    raise InvalidRequestError(str(exc))


@router.get(
  "/batch/{batch_id}",
  response_model=BatchStatus,
  status_code=status.HTTP_200_OK,
  summary="Get batch processing status",
  description="Returns current progress and completed results for a batch job.",
)
async def get_batch_status(
  batch_id: str,
  batch_service: BatchService = Depends(get_batch_service),
):
  """Return current status/results for a batch job."""
  try:
    return batch_service.get_status(batch_id)
  except ValueError:
    raise InteractionNotFoundError(batch_id)


@router.post(
  "/batch/{batch_id}/cancel",
  response_model=BatchStatus,
  status_code=status.HTTP_200_OK,
  summary="Cancel a batch job",
  description="Request cancellation of an in-flight batch job.",
)
async def cancel_batch(
  batch_id: str,
  batch_service: BatchService = Depends(get_batch_service),
):
  """Cancel a backend-managed batch job."""
  try:
    return batch_service.cancel_batch(batch_id)
  except ValueError:
    raise InteractionNotFoundError(batch_id)


@router.post(
  "/send",
  response_model=SendPromptResponse,
  status_code=status.HTTP_200_OK,
  summary="Send prompt to LLM provider",
  description="Send a prompt to an LLM provider and get response with search data. "
  "The interaction is saved to the database for history tracking.",
  responses={
    400: {
      "description": "Invalid request (unsupported model or missing API key)",
      "content": {
        "application/json": {
          "examples": {
            "model_not_supported": {
              "summary": "Model not supported",
              "value": {
                "error": {
                  "message": "Model 'invalid-model' is not supported",
                  "code": "INVALID_REQUEST",
                  "details": {"model": "invalid-model"}
                }
              }
            },
            "api_key_missing": {
              "summary": "API key missing",
              "value": {
                "error": {
                  "message": "API key for openai is not configured",
                  "code": "INVALID_REQUEST",
                  "details": {
                    "provider": "openai",
                    "solution": "Add the API key to your .env file"
                  }
                }
              }
            }
          }
        }
      }
    },
    422: {
      "description": "Validation error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "Request validation failed",
              "code": "VALIDATION_ERROR",
              "details": {
                "errors": [
                  {
                    "field": "body -> prompt",
                    "message": "Field required",
                    "type": "missing"
                  }
                ]
              }
            }
          }
        }
      }
    },
    500: {
      "description": "Internal server error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "An unexpected error occurred",
              "code": "INTERNAL_SERVER_ERROR"
            }
          }
        }
      }
    },
    502: {
      "description": "Provider API error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "openai provider error: API rate limit exceeded",
              "code": "EXTERNAL_SERVICE_ERROR",
              "details": {"service": "openai provider"}
            }
          }
        }
      }
    }
  }
)
async def send_prompt(
  request: SendPromptRequest,
  provider_service: ProviderService = Depends(get_provider_service),
):
  """Send a prompt to an LLM provider.

  Args:
    request: SendPromptRequest with prompt, provider, model, and options
    provider_service: ProviderService dependency

  Returns:
    SendPromptResponse with full interaction data including search queries and citations

  Raises:
    400: Invalid request (unsupported model, missing API key)
    500: Internal server error
    502: Provider API error
  """
  try:
    response = provider_service.send_prompt(
      prompt=request.prompt,
      model=request.model,
      save_to_db=True
    )
    return response
  except ValueError as e:
    # Parse ValueError to determine specific error type
    error_msg = str(e).lower()
    if "not supported" in error_msg or "invalid model" in error_msg:
      raise ModelNotSupportedError(request.model)
    elif "api key" in error_msg or "missing" in error_msg:
      # Extract provider name from error message if possible
      raise APIKeyMissingError(request.model.split('-')[0] if request.model else "unknown")
    else:
      # Generic invalid request
      from app.core.exceptions import InvalidRequestError
      raise InvalidRequestError(str(e))
  except Exception as exc:
    # Check if it's a provider API error
    if "API error" in str(exc) or "provider" in str(exc).lower():
      provider_name = request.model.split('-')[0] if request.model else "unknown"
      raise ProviderError(provider_name, str(exc))
    # Otherwise, let global handler catch it
    raise


@router.post(
  "/save-network-log",
  response_model=SendPromptResponse,
  status_code=status.HTTP_201_CREATED,
  summary="Save web capture data",
  description="Save interaction data captured via the web capture mode (formerly called network log mode). "
  "This endpoint accepts pre-captured data and saves it to the database.",
  responses={
    400: {
      "description": "Invalid request",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "Invalid provider",
              "code": "INVALID_REQUEST"
            }
          }
        }
      }
    },
    500: {
      "description": "Internal server error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "Database error occurred",
              "code": "INTERNAL_SERVER_ERROR"
            }
          }
        }
      }
    }
  }
)
async def save_network_log_data(
  request: SaveNetworkLogRequest,
  background_tasks: BackgroundTasks,
  interaction_service: InteractionService = Depends(get_interaction_service),
):
  """Save web capture data captured by frontend.

  This endpoint is used when the frontend captures LLM interaction data via
  browser automation (formerly referred to as network log mode). The frontend sends the captured data
  to this endpoint for database persistence.

  Args:
    request: SaveNetworkLogRequest with all interaction data
    background_tasks: Schedules post-save work without blocking the response
    interaction_service: InteractionService dependency

  Returns:
    SendPromptResponse with saved interaction data including interaction_id

  Raises:
    400: Invalid request
    500: Internal server error
  """
  try:
    # Save the web capture data to database
    response = interaction_service.save_network_log_interaction(
      provider=request.provider,
      model=request.model,
      prompt=request.prompt,
      response_text=request.response_text,
      search_queries=[q.model_dump(exclude_none=True) for q in request.search_queries],
      sources=[s.model_dump(exclude_none=True) for s in request.sources],
      citations=[c.model_dump(exclude_none=True) for c in request.citations],
      response_time_ms=request.response_time_ms,
      raw_response=request.raw_response,
      extra_links_count=request.extra_links_count,
      enable_citation_tagging=request.enable_citation_tagging,
    )

    try:
      status_value = None
      if isinstance(getattr(response, "metadata", None), dict):
        status_value = (response.metadata or {}).get("citation_tagging_status")
      if status_value == "queued":
        response_id = getattr(response, "interaction_id", None)
        if not isinstance(response_id, int):
          return response
        # Run in a background thread to avoid blocking the request.
        background_tasks.add_task(
          enqueue_web_citation_tagging,
          response_id,
          request.prompt,
          request.response_text,
        )
    except Exception:
      # Tagging should never block persistence.
      import logging
      logging.getLogger(__name__).exception("Failed to enqueue citation tagging job")

    return response
  except ValueError as e:
    from app.core.exceptions import InvalidRequestError
    raise InvalidRequestError(str(e))
  except Exception:
    # Let global handler catch it
    raise


@router.get(
  "/recent",
  response_model=PaginatedInteractionList,
  status_code=status.HTTP_200_OK,
  summary="Get recent interactions",
  description="Get a paginated list of recent interactions with summary information. "
  "Supports filtering by data source, provider, model, and date range.",
)
async def get_recent_interactions(
  page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
  page_size: int = Query(
    default=10,
    ge=1,
    le=100,
    description="Items per page (max 100)"
  ),
  data_source: Optional[str] = Query(
    default=None,
    description="Filter by data source (api or web). Legacy 'network_log' values are also accepted."
  ),
  provider: Optional[str] = Query(
    default=None,
    description="Filter by provider name (e.g., openai)"
  ),
  model: Optional[str] = Query(
    default=None,
    description="Filter by model name (e.g., gpt-4o)"
  ),
  date_from: Optional[datetime] = Query(
    default=None,
    description="Filter by created_at >= date_from (ISO 8601)"
  ),
  date_to: Optional[datetime] = Query(
    default=None,
    description="Filter by created_at <= date_to (ISO 8601)"
  ),
  interaction_service: InteractionService = Depends(get_interaction_service),
):
  """Get recent interactions with pagination and filtering.

  Args:
    page: Page number (1-indexed, default 1)
    page_size: Items per page (1-100, default 20)
    data_source: Optional filter by data source
    provider: Optional filter by provider name
    model: Optional filter by model name
    date_from: Optional filter by created_at >= date_from
    date_to: Optional filter by created_at <= date_to
    interaction_service: InteractionService dependency

  Returns:
    PaginatedInteractionList with items and pagination metadata

  Raises:
    500: Internal server error
  """
  normalized_source = None
  if data_source:
    lower = data_source.lower()
    if lower not in ("api", "web", "network_log"):
      from app.core.exceptions import InvalidRequestError
      raise InvalidRequestError("data_source must be one of: api, web")
    normalized_source = "web" if lower == "network_log" else lower

  interactions, total_count, stats = interaction_service.get_recent_interactions(
    page=page,
    page_size=page_size,
    data_source=normalized_source,
    provider=provider,
    model=model,
    date_from=date_from,
    date_to=date_to
  )

  # Calculate pagination metadata
  total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
  has_next = page < total_pages
  has_prev = page > 1

  pagination = PaginationMeta(
    page=page,
    page_size=page_size,
    total_items=total_count,
    total_pages=total_pages,
    has_next=has_next,
    has_prev=has_prev
  )

  return PaginatedInteractionList(
    items=interactions,
    pagination=pagination,
    stats=stats
  )


@router.get(
  "/{interaction_id}",
  response_model=SendPromptResponse,
  status_code=status.HTTP_200_OK,
  summary="Get interaction details",
  description=(
    "Get full details of a specific interaction including all search queries, "
    "sources, and citations."
  ),
  responses={
    404: {
      "description": "Interaction not found",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "Interaction with ID 999 not found",
              "code": "RESOURCE_NOT_FOUND",
              "details": {
                "resource_type": "Interaction",
                "resource_id": "999"
              }
            }
          }
        }
      }
    },
    500: {
      "description": "Internal server error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "An unexpected error occurred",
              "code": "INTERNAL_SERVER_ERROR"
            }
          }
        }
      }
    }
  }
)
async def get_interaction_details(
  interaction_id: int,
  interaction_service: InteractionService = Depends(get_interaction_service),
):
  """Get interaction details by ID.

  Args:
    interaction_id: The interaction ID
    interaction_service: InteractionService dependency

  Returns:
    SendPromptResponse with full interaction details

  Raises:
    404: Interaction not found
    500: Internal server error
  """
  interaction = interaction_service.get_interaction_details(interaction_id)
  if not interaction:
    raise InteractionNotFoundError(interaction_id)
  return interaction


@router.get(
  "/{interaction_id}/export/markdown",
  response_class=PlainTextResponse,
  status_code=status.HTTP_200_OK,
  summary="Export interaction as Markdown",
  description=(
    "Export an interaction as formatted Markdown with all details, "
    "sources, and citations."
  ),
  responses={
    404: {
      "description": "Interaction not found",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "Interaction with ID 999 not found",
              "code": "RESOURCE_NOT_FOUND",
              "details": {
                "resource_type": "Interaction",
                "resource_id": "999"
              }
            }
          }
        }
      }
    },
    500: {
      "description": "Internal server error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "An unexpected error occurred",
              "code": "INTERNAL_SERVER_ERROR"
            }
          }
        }
      }
    }
  }
)
async def export_interaction_markdown(
  interaction_id: int,
  export_service: ExportService = Depends(get_export_service),
):
  """Export interaction as Markdown.

  Args:
    interaction_id: The interaction ID to export
    export_service: ExportService dependency

  Returns:
    Plain text Markdown document

  Raises:
    404: Interaction not found
    500: Internal server error
  """
  markdown = export_service.build_markdown(interaction_id)
  if not markdown:
    raise InteractionNotFoundError(interaction_id)
  return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.delete(
  "/{interaction_id}",
  status_code=status.HTTP_204_NO_CONTENT,
  summary="Delete interaction",
  description="Delete an interaction and all associated data (search queries, sources, citations).",
  responses={
    404: {
      "description": "Interaction not found",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "Interaction with ID 999 not found",
              "code": "RESOURCE_NOT_FOUND",
              "details": {
                "resource_type": "Interaction",
                "resource_id": "999"
              }
            }
          }
        }
      }
    },
    500: {
      "description": "Internal server error",
      "content": {
        "application/json": {
          "example": {
            "error": {
              "message": "An unexpected error occurred",
              "code": "INTERNAL_SERVER_ERROR"
            }
          }
        }
      }
    }
  }
)
async def delete_interaction(
  interaction_id: int,
  interaction_service: InteractionService = Depends(get_interaction_service),
):
  """Delete an interaction.

  Args:
    interaction_id: The interaction ID
    interaction_service: InteractionService dependency

  Returns:
    204 No Content on success

  Raises:
    404: Interaction not found
    500: Internal server error
  """
  deleted = interaction_service.delete_interaction(interaction_id)
  if not deleted:
    raise InteractionNotFoundError(interaction_id)
  return None
