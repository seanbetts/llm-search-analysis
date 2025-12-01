"""Interactions API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.schemas.requests import SendPromptRequest
from app.api.v1.schemas.responses import (
  SendPromptResponse,
  InteractionSummary,
)
from app.services.interaction_service import InteractionService
from app.services.provider_service import ProviderService
from app.dependencies import get_interaction_service, get_provider_service

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post(
  "/send",
  response_model=SendPromptResponse,
  status_code=status.HTTP_200_OK,
  summary="Send prompt to LLM provider",
  description="Send a prompt to an LLM provider and get response with search data. "
  "The interaction is saved to the database for history tracking.",
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
    # Model not supported or API key missing
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=str(e)
    )
  except Exception as e:
    # Provider API error or other unexpected error
    if "API error" in str(e):
      raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Provider API error: {str(e)}"
      )
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Internal server error: {str(e)}"
    )


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
  try:
    interactions = interaction_service.get_recent_interactions(
      limit=limit,
      data_source=data_source
    )
    return interactions
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Error retrieving interactions: {str(e)}"
    )


@router.get(
  "/{interaction_id}",
  response_model=SendPromptResponse,
  status_code=status.HTTP_200_OK,
  summary="Get interaction details",
  description="Get full details of a specific interaction including all search queries, sources, and citations.",
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
  try:
    interaction = interaction_service.get_interaction_details(interaction_id)
    if not interaction:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Interaction {interaction_id} not found"
      )
    return interaction
  except HTTPException:
    raise
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Error retrieving interaction: {str(e)}"
    )


@router.delete(
  "/{interaction_id}",
  status_code=status.HTTP_204_NO_CONTENT,
  summary="Delete interaction",
  description="Delete an interaction and all associated data (search queries, sources, citations).",
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
  try:
    deleted = interaction_service.delete_interaction(interaction_id)
    if not deleted:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Interaction {interaction_id} not found"
      )
    return None
  except HTTPException:
    raise
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Error deleting interaction: {str(e)}"
    )
