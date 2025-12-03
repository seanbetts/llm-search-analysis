"""
Database models using SQLAlchemy.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Provider(Base):
  """AI provider information."""
  __tablename__ = "providers"

  id = Column(Integer, primary_key=True)
  name = Column(String(50), unique=True, nullable=False)
  display_name = Column(String(100))
  is_active = Column(Boolean, default=True)
  created_at = Column(DateTime, default=datetime.utcnow)

  # Relationships
  sessions = relationship("SessionModel", back_populates="provider")


class SessionModel(Base):
  """Prompt session."""
  __tablename__ = "sessions"

  id = Column(Integer, primary_key=True)
  provider_id = Column(Integer, ForeignKey("providers.id"))
  model_used = Column(String(100))
  created_at = Column(DateTime, default=datetime.utcnow)

  # Relationships
  provider = relationship("Provider", back_populates="sessions")
  prompts = relationship("Prompt", back_populates="session")


class Prompt(Base):
  """User prompt."""
  __tablename__ = "prompts"

  id = Column(Integer, primary_key=True)
  session_id = Column(Integer, ForeignKey("sessions.id"))
  prompt_text = Column(Text, nullable=False)
  created_at = Column(DateTime, default=datetime.utcnow)

  # Relationships
  session = relationship("SessionModel", back_populates="prompts")
  response = relationship("Response", back_populates="prompt", uselist=False)


class Response(Base):
  """Model response."""
  __tablename__ = "responses"

  id = Column(Integer, primary_key=True)
  prompt_id = Column(Integer, ForeignKey("prompts.id"))
  response_text = Column(Text)
  response_time_ms = Column(Integer)
  created_at = Column(DateTime, default=datetime.utcnow)
  raw_response_json = Column(JSON)
  data_source = Column(String(20), default='api')
  extra_links_count = Column(Integer, default=0)

  # Computed metrics
  sources_found = Column(Integer, default=0)
  sources_used_count = Column(Integer, default=0)
  avg_rank = Column(Float)

  # Relationships
  prompt = relationship("Prompt", back_populates="response")
  search_queries = relationship("SearchQuery", back_populates="response")
  sources = relationship(
    "SourceModel",
    foreign_keys="[SourceModel.response_id]",
    back_populates="response"
  )
  sources_used = relationship("SourceUsed", back_populates="response")


class SearchQuery(Base):
  """Search query made during response generation."""
  __tablename__ = "search_queries"

  id = Column(Integer, primary_key=True)
  response_id = Column(Integer, ForeignKey("responses.id"))
  search_query = Column(Text)
  created_at = Column(DateTime, default=datetime.utcnow)
  order_index = Column(Integer, default=0)

  # Network log exclusive fields
  internal_ranking_scores = Column(JSON)
  query_reformulations = Column(JSON)

  # Relationships
  response = relationship("Response", back_populates="search_queries")
  sources = relationship("SourceModel", back_populates="search_query")


class SourceModel(Base):
  """Source/URL fetched during search."""
  __tablename__ = "sources"

  id = Column(Integer, primary_key=True)
  search_query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=True)
  response_id = Column(Integer, ForeignKey("responses.id"), nullable=True)
  url = Column(Text, nullable=False)
  title = Column(Text)
  domain = Column(String(255))
  rank = Column(Integer)
  pub_date = Column(String(50))

  # Network log exclusive fields
  snippet_text = Column(Text)
  internal_score = Column(Float)
  metadata_json = Column(JSON)

  # Relationships
  search_query = relationship("SearchQuery", back_populates="sources")
  response = relationship("Response", foreign_keys=[response_id], back_populates="sources")


class SourceUsed(Base):
  """Source actually used/cited in the response."""
  __tablename__ = "sources_used"

  id = Column(Integer, primary_key=True)
  response_id = Column(Integer, ForeignKey("responses.id"))
  url = Column(Text, nullable=False)
  title = Column(Text)
  rank = Column(Integer)

  # Network log exclusive fields
  snippet_used = Column(Text)
  citation_confidence = Column(Float)
  metadata_json = Column(JSON)

  # Relationships
  response = relationship("Response", back_populates="sources_used")
