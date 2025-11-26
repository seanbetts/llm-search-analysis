"""
Abstract base class for network traffic capturers.

Defines the interface that all network capturer implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from providers.base_provider import ProviderResponse


class BaseCapturer(ABC):
    """
    Abstract base class for network traffic capturers.

    All network capturer implementations (ChatGPT, Claude, Gemini) must inherit
    from this class and implement the required methods.
    """

    def __init__(self):
        """Initialize the capturer."""
        self.browser = None
        self.page = None
        self.is_active = False

    @abstractmethod
    def start_browser(self, headless: bool = False) -> None:
        """
        Start browser instance for automation.

        Args:
            headless: Whether to run browser in headless mode

        Raises:
            Exception: If browser fails to start
        """
        pass

    @abstractmethod
    def stop_browser(self) -> None:
        """
        Stop browser instance and cleanup resources.

        Raises:
            Exception: If cleanup fails
        """
        pass

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Handle user authentication to the provider.

        This typically involves navigating to login page and waiting for
        user to manually log in, or using stored session cookies.

        Returns:
            True if authentication successful, False otherwise

        Raises:
            Exception: If authentication process fails
        """
        pass

    @abstractmethod
    def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
        """
        Send a prompt and capture network traffic.

        Args:
            prompt: User's prompt/query
            model: Model to use (e.g., "gpt-5.1")

        Returns:
            ProviderResponse with data captured from network logs

        Raises:
            Exception: If prompt submission or capture fails
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

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """
        Get list of supported models for this provider.

        Returns:
            List of model identifiers
        """
        pass

    def is_browser_active(self) -> bool:
        """
        Check if browser session is active.

        Returns:
            True if browser is running, False otherwise
        """
        return self.is_active

    def validate_model(self, model: str) -> bool:
        """
        Check if a model is supported by this provider.

        Args:
            model: Model identifier to validate

        Returns:
            True if model is supported, False otherwise
        """
        return model in self.get_supported_models()
