"""Dependency injection for FastAPI endpoints.

This module provides FastAPI dependency functions for database sessions and
service instances. It follows the dependency injection pattern to ensure
proper resource management and testability.

Dependency Chain:
1. get_db() -> SQLAlchemy Session
2. get_interaction_repository() -> InteractionRepository (needs db)
3. get_interaction_service() -> InteractionService (needs repository)
4. get_provider_service() -> ProviderService (needs interaction_service)
5. get_export_service() -> ExportService (needs interaction_service)

The dependencies automatically handle:
- Database connection lifecycle (open/close)
- Proper resource cleanup via context managers
- Service instance creation with correct parameters

Example:
    @app.get("/interactions")
    def get_interactions(
        interaction_service: InteractionService = Depends(get_interaction_service)
    ):
        return interaction_service.get_recent_interactions()
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi import Depends

from app.config import settings
from app.repositories.interaction_repository import InteractionRepository
from app.services.interaction_service import InteractionService
from app.services.provider_service import ProviderService
from app.services.export_service import ExportService

# Create database engine
engine = create_engine(
  settings.DATABASE_URL,
  connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
  echo=settings.DEBUG,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
  """
  Database session dependency for FastAPI endpoints.

  Yields a SQLAlchemy session and ensures proper cleanup.

  Usage:
    @app.get("/items")
    def get_items(db: Session = Depends(get_db)):
        return db.query(Item).all()
  """
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


def get_interaction_repository(db: Session = Depends(get_db)) -> InteractionRepository:
  """
  Get InteractionRepository instance with database session.

  Args:
    db: Database session from get_db dependency

  Returns:
    InteractionRepository instance
  """
  return InteractionRepository(db)


def get_interaction_service(
  repository: InteractionRepository = Depends(get_interaction_repository)
) -> InteractionService:
  """
  Get InteractionService instance with repository.

  Args:
    repository: InteractionRepository from get_interaction_repository dependency

  Returns:
    InteractionService instance
  """
  return InteractionService(repository)


def get_provider_service(
  interaction_service: InteractionService = Depends(get_interaction_service)
) -> ProviderService:
  """
  Get ProviderService instance with interaction service.

  Args:
    interaction_service: InteractionService from get_interaction_service dependency

  Returns:
    ProviderService instance
  """
  return ProviderService(interaction_service)


def get_export_service(
  interaction_service: InteractionService = Depends(get_interaction_service)
) -> ExportService:
  """
  Get ExportService instance with interaction service.

  Args:
    interaction_service: InteractionService from get_interaction_service dependency

  Returns:
    ExportService instance
  """
  return ExportService(interaction_service)
