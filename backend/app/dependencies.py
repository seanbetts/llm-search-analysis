from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

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
