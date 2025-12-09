"""Providers API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.schemas.responses import ProviderInfo
from app.services.provider_service import ProviderService
from app.dependencies import get_provider_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get(
  "",
  response_model=List[ProviderInfo],
  status_code=status.HTTP_200_OK,
  summary="Get available providers",
  description="Get list of all configured LLM providers with their supported models. "
  "Only providers with configured API keys are returned.",
)
async def get_providers(
  provider_service: ProviderService = Depends(get_provider_service),
):
  """Get list of available providers.

  Args:
    provider_service: ProviderService dependency

  Returns:
    List of ProviderInfo objects with provider details and supported models

  Raises:
    500: Internal server error
  """
  try:
    providers = provider_service.get_available_providers()
    return providers
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Error retrieving providers: {str(e)}"
    )


@router.get(
  "/models",
  response_model=List[str],
  status_code=status.HTTP_200_OK,
  summary="Get all available models",
  description="Get list of all available models across all configured providers.",
)
async def get_all_models(
  provider_service: ProviderService = Depends(get_provider_service),
):
  """Get list of all available models.

  Args:
    provider_service: ProviderService dependency

  Returns:
    List of model identifiers

  Raises:
    500: Internal server error
  """
  try:
    models = provider_service.get_available_models()
    return models
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=f"Error retrieving models: {str(e)}"
    )
