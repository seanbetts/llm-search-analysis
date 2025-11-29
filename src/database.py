"""
Database models and operations using SQLAlchemy.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from .config import Config

Base = declarative_base()


class Provider(Base):
    """AI provider information."""
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)  # e.g., "openai", "google", "anthropic"
    display_name = Column(String(100))  # e.g., "OpenAI", "Google", "Anthropic"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions = relationship("SessionModel", back_populates="provider")


class SessionModel(Base):
    """Prompt session."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey("providers.id"))
    model_used = Column(String(100))  # e.g., "gpt-5.1", "gemini-3.0"
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
    response_time_ms = Column(Integer)  # Response time in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow)
    raw_response_json = Column(JSON)  # Store raw API response
    data_source = Column(String(20), default='api')  # 'api' or 'network_log'
    extra_links_count = Column(Integer, default=0)  # Links in response not present in search results

    # Relationships
    prompt = relationship("Prompt", back_populates="response")
    search_queries = relationship("SearchQuery", back_populates="response")
    sources_used = relationship("SourceUsed", back_populates="response")


class SearchQuery(Base):
    """Search query made during response generation."""
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id"))
    search_query = Column(Text)  # The search query text
    created_at = Column(DateTime, default=datetime.utcnow)
    order_index = Column(Integer, default=0)  # Order of the query in the sequence

    # Network log exclusive fields
    internal_ranking_scores = Column(JSON)  # If available from logs
    query_reformulations = Column(JSON)  # Query evolution steps

    # Relationships
    response = relationship("Response", back_populates="search_queries")
    sources = relationship("SourceModel", back_populates="search_query")


class SourceModel(Base):
    """Source/URL fetched during search."""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    search_query_id = Column(Integer, ForeignKey("search_queries.id"))
    url = Column(Text, nullable=False)
    title = Column(Text)
    domain = Column(String(255))
    rank = Column(Integer)  # Position in search results (1-indexed)
    pub_date = Column(String(50))  # ISO-formatted publication date if available

    # Network log exclusive fields
    snippet_text = Column(Text)  # Actual snippet extracted by model
    internal_score = Column(Float)  # Internal relevance score if available
    metadata_json = Column(JSON)  # Full metadata from logs

    # Relationships
    search_query = relationship("SearchQuery", back_populates="sources")


class SourceUsed(Base):
    """Source actually used/cited in the response."""
    __tablename__ = "sources_used"

    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id"))
    url = Column(Text, nullable=False)
    title = Column(Text)
    rank = Column(Integer)  # Rank from original search results (1-indexed)

    # Network log exclusive fields
    snippet_used = Column(Text)  # Exact snippet cited
    citation_confidence = Column(Float)  # If available from logs
    metadata_json = Column(JSON)  # Additional citation metadata (e.g., citation_id)

    # Relationships
    response = relationship("Response", back_populates="sources_used")


class Database:
    """Database manager."""

    def __init__(self, database_url: str = None):
        """
        Initialize database connection.

        Args:
            database_url: Database URL (defaults to config value)
        """
        self.database_url = database_url or Config.DATABASE_URL
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)
        self._ensure_extra_links_column()

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def delete_interaction(self, response_id: int) -> bool:
        """
        Delete an interaction (response + prompt + related records) by response ID.
        Returns True if deleted, False if not found.
        """
        session = self.get_session()
        try:
            resp = session.query(Response).filter_by(id=response_id).first()
            if not resp:
                return False

            # Delete sources used
            session.query(SourceUsed).filter_by(response_id=response_id).delete()

            # Delete sources and search queries
            queries = session.query(SearchQuery).filter_by(response_id=response_id).all()
            for q in queries:
                session.query(SourceModel).filter_by(search_query_id=q.id).delete()
            session.query(SearchQuery).filter_by(response_id=response_id).delete()

            # Delete response
            prompt_id = resp.prompt_id
            session.delete(resp)

            # Delete prompt (orphan)
            if prompt_id:
                prompt_obj = session.query(Prompt).filter_by(id=prompt_id).first()
                if prompt_obj:
                    session.delete(prompt_obj)

            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ensure_providers(self):
        """Ensure default providers exist in database."""
        session = self.get_session()
        try:
            providers_data = [
                {"name": "openai", "display_name": "OpenAI"},
                {"name": "google", "display_name": "Google"},
                {"name": "anthropic", "display_name": "Anthropic"},
            ]

            for provider_data in providers_data:
                existing = session.query(Provider).filter_by(name=provider_data["name"]).first()
                if not existing:
                    provider = Provider(**provider_data)
                    session.add(provider)

            session.commit()
        finally:
            session.close()

    def _ensure_extra_links_column(self):
        """Ensure extra_links_count column exists on responses table (for network log metrics)."""
        with self.engine.connect() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(responses)")]
            if "extra_links_count" not in cols:
                conn.exec_driver_sql("ALTER TABLE responses ADD COLUMN extra_links_count INTEGER DEFAULT 0")

    def save_interaction(self, provider_name: str, model: str, prompt: str,
                        response_text: str, search_queries: List,
                        sources: List, citations: List,
                        response_time_ms: int, raw_response: dict,
                        data_source: str = 'api',
                        extra_links_count: int = 0):
        """
        Save a complete interaction to the database.

        Args:
            provider_name: Provider name (e.g., "openai")
            model: Model used
            prompt: User's prompt
            response_text: Model's response
            search_queries: List of SearchQuery objects
            sources: List of Source objects
            citations: List of Citation objects
            response_time_ms: Response time in milliseconds
            raw_response: Raw API response dictionary
            data_source: Data collection method ('api' or 'network_log')
            extra_links_count: Links in response not present in search results
        """
        # Normalize model naming (e.g., gpt-5-1 -> gpt-5.1)
        if model == "gpt-5-1":
            model = "gpt-5.1"

        session = self.get_session()
        try:
            # Get or create provider
            provider = session.query(Provider).filter_by(name=provider_name).first()
            if not provider:
                provider = Provider(name=provider_name, display_name=provider_name.capitalize())
                session.add(provider)
                session.flush()

            # Create session
            session_obj = SessionModel(provider_id=provider.id, model_used=model)
            session.add(session_obj)
            session.flush()

            # Create prompt
            prompt_obj = Prompt(session_id=session_obj.id, prompt_text=prompt)
            session.add(prompt_obj)
            session.flush()

            # Create response
            response_obj = Response(
                prompt_id=prompt_obj.id,
                response_text=response_text,
                response_time_ms=response_time_ms,
                raw_response_json=raw_response,
                data_source=data_source,
                extra_links_count=extra_links_count
            )
            session.add(response_obj)
            session.flush()

            # Create search queries and sources
            for query in search_queries:
                search_query_obj = SearchQuery(
                    response_id=response_obj.id,
                    search_query=query.query,
                    order_index=getattr(query, 'order_index', 0),
                    internal_ranking_scores=getattr(query, 'internal_ranking_scores', None),
                    query_reformulations=getattr(query, 'query_reformulations', None)
                )
                session.add(search_query_obj)
                session.flush()

                # Associate sources with this search query (use query.sources, not global sources list)
                for source in query.sources:
                    source_obj = SourceModel(
                        search_query_id=search_query_obj.id,
                        url=source.url,
                        title=source.title,
                        domain=source.domain,
                        rank=source.rank,
                        pub_date=getattr(source, 'pub_date', None),
                        snippet_text=getattr(source, 'snippet_text', None),
                        internal_score=getattr(source, 'internal_score', None),
                        metadata_json=getattr(source, 'metadata', None)
                    )
                    session.add(source_obj)

            # Create sources used
            for citation in citations:
                source_used_obj = SourceUsed(
                    response_id=response_obj.id,
                    url=citation.url,
                    title=citation.title,
                    rank=citation.rank,
                    snippet_used=getattr(citation, 'snippet_used', None),
                    citation_confidence=getattr(citation, 'citation_confidence', None),
                    metadata_json=getattr(citation, 'metadata', None)
                )
                session.add(source_used_obj)

            session.commit()
            return response_obj.id

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_recent_interactions(self, limit: int = 50):
        """
        Get recent interactions for display.

        Args:
            limit: Maximum number of interactions to return

        Returns:
            List of interaction dictionaries
        """
        session = self.get_session()
        try:
            results = []
            prompts = session.query(Prompt).order_by(Prompt.created_at.desc()).limit(limit).all()

            for prompt in prompts:
                if prompt.response:
                    search_count = len(prompt.response.search_queries)
                    source_count = sum(len(sq.sources) for sq in prompt.response.search_queries)
                    sources_used_count = len(prompt.response.sources_used)

                    # Calculate average rank from sources used
                    sources_with_rank = [su for su in prompt.response.sources_used if su.rank is not None]
                    avg_rank = sum(su.rank for su in sources_with_rank) / len(sources_with_rank) if sources_with_rank else None
                    extra_links = getattr(prompt.response, "extra_links_count", 0)
                    data_source = getattr(prompt.response, "data_source", "api")

                    results.append({
                        "id": prompt.id,
                        "timestamp": prompt.created_at,
                        "prompt": prompt.prompt_text,
                        "model": prompt.session.model_used,
                        "provider": prompt.session.provider.display_name,
                        "searches": search_count,
                        "sources": source_count,
                        "citations": sources_used_count,
                        "avg_rank": avg_rank,
                        "extra_links": extra_links,
                        "data_source": data_source
                    })

            return results
        finally:
            session.close()

    def get_interaction_details(self, prompt_id: int):
        """
        Get detailed information about a specific interaction.

        Args:
            prompt_id: ID of the prompt to retrieve

        Returns:
            Dictionary with full interaction details or None if not found
        """
        session = self.get_session()
        try:
            prompt = session.query(Prompt).filter_by(id=prompt_id).first()
            if not prompt or not prompt.response:
                return None

            # Build search queries with their sources
            search_queries = []
            for search_query in prompt.response.search_queries:
                sources = [
                    {
                        "url": source.url,
                        "title": source.title,
                        "domain": source.domain,
                        "rank": source.rank
                    }
                    for source in search_query.sources
                ]
                search_queries.append({
                    "query": search_query.search_query,
                    "sources": sources
                })

            # Build sources used
            citations = [
                {
                    "url": source_used.url,
                    "title": source_used.title,
                    "rank": source_used.rank,
                    "query_index": (source_used.metadata_json or {}).get("query_index") if isinstance(source_used.metadata_json, dict) else None,
                    "pub_date": (source_used.metadata_json or {}).get("pub_date") if isinstance(source_used.metadata_json, dict) else None,
                    "snippet": (source_used.metadata_json or {}).get("snippet") if isinstance(source_used.metadata_json, dict) else None,
                }
                for source_used in prompt.response.sources_used
            ]

            return {
                "prompt": prompt.prompt_text,
                "response_text": prompt.response.response_text,
                "provider": prompt.session.provider.display_name,
                "model": prompt.session.model_used,
                "response_time_ms": prompt.response.response_time_ms,
                "extra_links": getattr(prompt.response, "extra_links_count", 0),
                "search_queries": search_queries,
                "citations": citations,
                "created_at": prompt.created_at
            }
        finally:
            session.close()
