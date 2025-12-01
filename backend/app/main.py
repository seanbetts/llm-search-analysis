from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.api.v1.endpoints import interactions, providers
from app.dependencies import engine

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

# Include API routers
app.include_router(interactions.router, prefix="/api/v1")
app.include_router(providers.router, prefix="/api/v1")


# Startup event to create database tables
@app.on_event("startup")
async def startup_event():
  """Create database tables on startup if they don't exist"""
  from app.models.database import Base
  Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
  """Root endpoint - API information"""
  return {
    "name": "LLM Search Analysis API",
    "version": "1.0.0",
    "status": "running",
    "docs": "/docs",
  }


@app.get("/health")
async def health_check():
  """Health check endpoint - verifies API and database connectivity"""
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
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
  """Handle Pydantic validation errors (422)"""
  return JSONResponse(
    status_code=422,
    content={
      "status": "error",
      "message": "Validation error",
      "detail": exc.errors(),
    },
  )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
  """Handle database errors (500)"""
  return JSONResponse(
    status_code=500,
    content={
      "status": "error",
      "message": "Database error",
      "detail": str(exc) if settings.DEBUG else "A database error occurred",
    },
  )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
  """Global exception handler for unhandled errors (500)"""
  return JSONResponse(
    status_code=500,
    content={
      "status": "error",
      "message": "Internal server error",
      "detail": str(exc) if settings.DEBUG else "An error occurred",
    },
  )
