"""Interactions API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.v1.schemas.requests import SendPromptRequest
from app.api.v1.schemas.responses import (
  SendPromptResponse,
  InteractionSummary,
)
from app.services.interaction_service import InteractionService
from app.services.provider_service import ProviderService
from app.dependencies import get_interaction_service, get_provider_service
from app.core.exceptions import (
  ProviderError,
  ModelNotSupportedError,
  APIKeyMissingError,
  InteractionNotFoundError,
  InternalServerError,
)

router = APIRouter(prefix="/interactions", tags=["interactions"])


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
  """
  Send a prompt to an LLM provider.

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
  except Exception as e:
    # Check if it's a provider API error
    if "API error" in str(e) or "provider" in str(e).lower():
      provider_name = request.model.split('-')[0] if request.model else "unknown"
      raise ProviderError(provider_name, str(e))
    # Otherwise, let global handler catch it
    raise


@router.get(
  "/recent",
  response_model=List[InteractionSummary],
  status_code=status.HTTP_200_OK,
  summary="Get recent interactions",
  description="Get a list of recent interactions with summary information. "
  "Supports filtering by data source and limiting results.",
)
async def get_recent_interactions(
  limit: int = Query(default=50, ge=1, le=1000, description="Maximum number of results"),
  data_source: Optional[str] = Query(default=None, description="Filter by data source (api or network_log)"),
  interaction_service: InteractionService = Depends(get_interaction_service),
):
  """
  Get recent interactions.

  Args:
    limit: Maximum number of results (1-1000, default 50)
    data_source: Optional filter by data source
    interaction_service: InteractionService dependency

  Returns:
    List of InteractionSummary objects

  Raises:
    500: Internal server error
  """
  interactions = interaction_service.get_recent_interactions(
    limit=limit,
    data_source=data_source
  )
  return interactions


@router.get(
  "/{interaction_id}",
  response_model=SendPromptResponse,
  status_code=status.HTTP_200_OK,
  summary="Get interaction details",
  description="Get full details of a specific interaction including all search queries, sources, and citations.",
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
  """
  Get interaction details by ID.

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
  """
  Delete an interaction.

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
