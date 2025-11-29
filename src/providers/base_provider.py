"""
Abstract base class for LLM provider implementations.

Defines the interface that all provider implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchQuery:
    """Represents a search query made by the model."""
    query: str
    sources: List['Source'] = None
    timestamp: Optional[str] = None
    order_index: int = 0
    # Network log exclusive fields
    internal_ranking_scores: Optional[Dict] = None
    query_reformulations: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize sources list if not provided."""
        if self.sources is None:
            self.sources = []


@dataclass
class Source:
    """Represents a source fetched during search."""
    url: str
    title: Optional[str] = None
    domain: Optional[str] = None
    rank: Optional[int] = None  # Position in search results (1-indexed)
    pub_date: Optional[str] = None  # ISO-formatted publication date if available
    # Network log exclusive fields
    snippet_text: Optional[str] = None
    internal_score: Optional[float] = None
    metadata: Optional[Dict] = None


@dataclass
class Citation:
    """Represents a citation used in the response."""
    url: str
    title: Optional[str] = None
    text_snippet: Optional[str] = None
    rank: Optional[int] = None  # Rank from original search results (1-indexed)
    metadata: Optional[Dict] = None  # Additional citation metadata (e.g., citation_id)
    # Network log exclusive fields
    snippet_used: Optional[str] = None
    citation_confidence: Optional[float] = None


@dataclass
class ProviderResponse:
    """Standardized response format across all providers."""
    response_text: str
    search_queries: List[SearchQuery]
    sources: List[Source]
    citations: List[Citation]
    raw_response: Dict[str, Any]
    model: str
    provider: str
    response_time_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional provider-specific metadata
    extra_links_count: int = 0  # Citations not from search results (network log only)


class BaseProvider(ABC):
    """
    Abstract base class for LLM providers.

    All provider implementations (OpenAI, Google, Anthropic) must inherit
    from this class and implement the required methods.
    """

    def __init__(self, api_key: str):
        """
        Initialize the provider with API credentials.

        Args:
            api_key: API key for the provider
        """
        self.api_key = api_key

    @abstractmethod
    def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
        """
        Send a prompt to the LLM and get a response with search data.

        Args:
            prompt: The user's prompt/query
            model: The specific model to use (e.g., "gpt-5.1")

        Returns:
            ProviderResponse object with standardized data

        Raises:
            Exception: If the API call fails
        """
        pass

    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of supported models for this provider.

        Returns:
            List of model identifiers (e.g., ["gpt-5.1", "gpt-4o"])
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider name (e.g., "openai", "google", "anthropic")
        """
        pass

    def validate_model(self, model: str) -> bool:
        """
        Check if a model is supported by this provider.

        Args:
            model: Model identifier to validate

        Returns:
            True if model is supported, False otherwise
        """
        return model in self.get_supported_models()
