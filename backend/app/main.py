from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

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
    # TODO: Add database connectivity check when repository layer is ready
    return {
      "status": "healthy",
      "version": "1.0.0",
      "database": "not_connected",  # Will update when DB is connected
    }
  except Exception as e:
    return JSONResponse(
      status_code=503,
      content={
        "status": "unhealthy",
        "error": str(e),
      },
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
  """Global exception handler for unhandled errors"""
  return JSONResponse(
    status_code=500,
    content={
      "status": "error",
      "message": "Internal server error",
      "detail": str(exc) if settings.DEBUG else "An error occurred",
    },
  )
