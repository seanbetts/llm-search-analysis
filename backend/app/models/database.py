"""Database models using SQLAlchemy."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
  JSON,
  Boolean,
  CheckConstraint,
  DateTime,
  Float,
  ForeignKey,
  Index,
  Integer,
  String,
  Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
  """Base class for SQLAlchemy ORM models."""


class Provider(Base):
  """AI provider information."""

  __tablename__ = "providers"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
  display_name: Mapped[Optional[str]] = mapped_column(String(100))
  is_active: Mapped[bool] = mapped_column(Boolean, default=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  interactions: Mapped[List["InteractionModel"]] = relationship(
    "InteractionModel",
    back_populates="provider",
  )


class InteractionModel(Base):
  """Root interaction metadata."""

  __tablename__ = "interactions"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"), nullable=False)
  model_name: Mapped[str] = mapped_column(String(100), nullable=False)
  prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
  data_source: Mapped[str] = mapped_column(String(20), nullable=False, default="api")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
  deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
  metadata_json: Mapped[Optional[Any]] = mapped_column(JSON)

  __table_args__ = (
    Index("ix_interactions_created_at", "created_at"),
    Index("ix_interactions_provider_id", "provider_id"),
    Index("ix_interactions_data_source", "data_source"),
  )

  provider: Mapped["Provider"] = relationship("Provider", back_populates="interactions")
  responses: Mapped[List["Response"]] = relationship(
    "Response",
    back_populates="interaction",
    cascade="all, delete-orphan",
  )


class Response(Base):
  """Model response."""

  __tablename__ = "responses"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  interaction_id: Mapped[int] = mapped_column(
    Integer,
    ForeignKey("interactions.id", ondelete="CASCADE"),
    nullable=False,
  )
  response_text: Mapped[Optional[str]] = mapped_column(Text)
  response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  raw_response_json: Mapped[Optional[Any]] = mapped_column(JSON)
  data_source: Mapped[str] = mapped_column(String(20), default="api")
  extra_links_count: Mapped[int] = mapped_column(Integer, default=0)

  sources_found: Mapped[int] = mapped_column(Integer, default=0)
  sources_used_count: Mapped[int] = mapped_column(Integer, default=0)
  avg_rank: Mapped[Optional[float]] = mapped_column(Float)

  citation_tagging_requested: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  citation_tagging_status: Mapped[Optional[str]] = mapped_column(String(32))
  citation_tagging_error: Mapped[Optional[str]] = mapped_column(Text)
  citation_tagging_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
  citation_tagging_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

  __table_args__ = (
    Index("ix_responses_created_at", "created_at"),
  )

  interaction: Mapped["InteractionModel"] = relationship("InteractionModel", back_populates="responses")
  search_queries: Mapped[List["SearchQuery"]] = relationship(
    "SearchQuery",
    back_populates="response",
    cascade="all, delete-orphan",
  )
  response_sources: Mapped[List["ResponseSource"]] = relationship(
    "ResponseSource",
    back_populates="response",
    cascade="all, delete-orphan",
  )
  sources_used: Mapped[List["SourceUsed"]] = relationship(
    "SourceUsed",
    back_populates="response",
    cascade="all, delete-orphan",
  )


class SearchQuery(Base):
  """Search query made during response generation."""

  __tablename__ = "search_queries"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  response_id: Mapped[int] = mapped_column(Integer, ForeignKey("responses.id"), nullable=False)
  search_query: Mapped[Optional[str]] = mapped_column(Text)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  order_index: Mapped[int] = mapped_column(Integer, default=0)

  internal_ranking_scores: Mapped[Optional[Any]] = mapped_column(JSON)
  query_reformulations: Mapped[Optional[Any]] = mapped_column(JSON)

  __table_args__ = (
    Index("ix_search_queries_response_id", "response_id"),
  )

  response: Mapped["Response"] = relationship("Response", back_populates="search_queries")
  sources: Mapped[List["QuerySource"]] = relationship("QuerySource", back_populates="search_query")


class QuerySource(Base):
  """Source/URL fetched for a specific search query."""

  __tablename__ = "query_sources"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  search_query_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_queries.id"), nullable=False)
  url: Mapped[str] = mapped_column(Text, nullable=False)
  title: Mapped[Optional[str]] = mapped_column(Text)
  domain: Mapped[Optional[str]] = mapped_column(String(255))
  rank: Mapped[Optional[int]] = mapped_column(Integer)
  pub_date: Mapped[Optional[str]] = mapped_column(String(50))
  internal_score: Mapped[Optional[float]] = mapped_column(Float)
  metadata_json: Mapped[Optional[Any]] = mapped_column(JSON)

  search_query: Mapped["SearchQuery"] = relationship("SearchQuery", back_populates="sources")

  __table_args__ = (
    Index("ix_query_sources_search_query_id", "search_query_id"),
  )


class ResponseSource(Base):
  """Source fetched directly for a response (web/network log mode)."""

  __tablename__ = "response_sources"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  response_id: Mapped[int] = mapped_column(Integer, ForeignKey("responses.id"), nullable=False)
  url: Mapped[str] = mapped_column(Text, nullable=False)
  title: Mapped[Optional[str]] = mapped_column(Text)
  domain: Mapped[Optional[str]] = mapped_column(String(255))
  rank: Mapped[Optional[int]] = mapped_column(Integer)
  pub_date: Mapped[Optional[str]] = mapped_column(String(50))
  search_description: Mapped[Optional[str]] = mapped_column(Text)
  internal_score: Mapped[Optional[float]] = mapped_column(Float)
  metadata_json: Mapped[Optional[Any]] = mapped_column(JSON)

  response: Mapped["Response"] = relationship("Response", back_populates="response_sources")

  __table_args__ = (
    Index("ix_response_sources_response_id", "response_id"),
  )


class SourceUsed(Base):
  """Source actually used/cited in the response."""

  __tablename__ = "sources_used"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  response_id: Mapped[int] = mapped_column(Integer, ForeignKey("responses.id"), nullable=False)
  query_source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("query_sources.id"), nullable=True)
  response_source_id: Mapped[Optional[int]] = mapped_column(
    Integer,
    ForeignKey("response_sources.id"),
    nullable=True,
  )
  url: Mapped[str] = mapped_column(Text, nullable=False)
  title: Mapped[Optional[str]] = mapped_column(Text)
  rank: Mapped[Optional[int]] = mapped_column(Integer)

  snippet_cited: Mapped[Optional[str]] = mapped_column(Text)
  citation_confidence: Mapped[Optional[float]] = mapped_column(Float)
  metadata_json: Mapped[Optional[Any]] = mapped_column(JSON)
  function_tags: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
  stance_tags: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
  provenance_tags: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
  influence_summary: Mapped[Optional[str]] = mapped_column(Text)

  __table_args__ = (
    Index("ix_sources_used_response_id", "response_id"),
    Index("ix_sources_used_query_source_id", "query_source_id"),
    Index("ix_sources_used_response_source_id", "response_source_id"),
    CheckConstraint(
      "(query_source_id IS NULL) OR (response_source_id IS NULL)",
      name="ck_sources_used_single_reference",
    ),
  )

  response: Mapped["Response"] = relationship("Response", back_populates="sources_used")
  query_source: Mapped[Optional["QuerySource"]] = relationship("QuerySource")
  response_source: Mapped[Optional["ResponseSource"]] = relationship("ResponseSource")
