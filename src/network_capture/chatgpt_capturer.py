"""
ChatGPT network traffic capturer implementation.

Uses browser automation to capture network logs from ChatGPT.
"""

import time
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .base_capturer import BaseCapturer
from .browser_manager import BrowserManager
from .parser import NetworkLogParser
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from providers.base_provider import ProviderResponse


class ChatGPTCapturer(BaseCapturer):
    """ChatGPT network traffic capturer using Playwright."""

    SUPPORTED_MODELS = [
        "gpt-5.1",
        "gpt-5-mini",
        "gpt-5-nano",
    ]

    CHATGPT_URL = "https://chatgpt.com"

    def __init__(self):
        """Initialize ChatGPT capturer."""
        super().__init__()
        self.playwright = None
        self.browser_manager = BrowserManager()

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openai"

    def get_supported_models(self) -> list[str]:
        """Get list of supported ChatGPT models."""
        return self.SUPPORTED_MODELS

    def start_browser(self, headless: bool = False) -> None:
        """
        Start browser instance.

        Args:
            headless: Whether to run in headless mode (not recommended for manual auth)

        Raises:
            Exception: If browser fails to start
        """
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=headless)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()

            # Set up network interception
            self.browser_manager.setup_network_interception(
                self.page,
                response_filter=lambda resp: 'chatgpt.com' in resp.url
            )

            self.is_active = True
            print(f"✓ Browser started for ChatGPT capture")

        except Exception as e:
            raise Exception(f"Failed to start browser: {str(e)}")

    def stop_browser(self) -> None:
        """Stop browser and cleanup."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()

            self.is_active = False
            print("✓ Browser stopped")

        except Exception as e:
            raise Exception(f"Failed to stop browser: {str(e)}")

    def authenticate(self) -> bool:
        """
        Handle ChatGPT authentication.

        Navigates to ChatGPT and waits for user to manually log in.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            print(f"Navigating to {self.CHATGPT_URL}...")
            self.page.goto(self.CHATGPT_URL)

            print("Please log in to ChatGPT in the browser window...")
            print("Waiting for authentication (timeout: 120 seconds)...")

            # Wait for chat interface to be available (indicates successful login)
            # TODO: Update this selector based on actual ChatGPT UI
            try:
                self.page.wait_for_selector(
                    'textarea[data-id="root"]',  # Placeholder selector
                    timeout=120000
                )
                print("✓ Authentication successful")
                return True

            except PlaywrightTimeout:
                print("✗ Authentication timeout - please try again")
                return False

        except Exception as e:
            print(f"✗ Authentication failed: {str(e)}")
            return False

    def send_prompt(self, prompt: str, model: str) -> ProviderResponse:
        """
        Send prompt to ChatGPT and capture network traffic.

        Args:
            prompt: User's prompt
            model: Model to use

        Returns:
            ProviderResponse with captured network log data

        Raises:
            ValueError: If model not supported
            Exception: If prompt submission or capture fails
        """
        if not self.validate_model(model):
            raise ValueError(
                f"Model '{model}' not supported. "
                f"Supported models: {self.SUPPORTED_MODELS}"
            )

        if not self.is_active:
            raise Exception("Browser not started. Call start_browser() first.")

        # Clear previous captures
        self.browser_manager.clear_captured_data()

        # Track response time
        start_time = time.time()

        try:
            # TODO: Implement actual ChatGPT interaction
            # This is a placeholder that will need to be updated based on:
            # 1. ChatGPT's actual UI selectors
            # 2. How to switch models
            # 3. How to submit prompts
            # 4. How to detect response completion

            # Example flow (to be updated):
            # 1. Find and click model selector
            # 2. Select the desired model
            # 3. Find prompt textarea
            # 4. Type prompt
            # 5. Submit
            # 6. Wait for response completion
            # 7. Extract chat ID from URL
            # 8. Filter network logs for that chat ID

            # Placeholder implementation
            print(f"Submitting prompt to ChatGPT (model: {model})...")
            print(f"Prompt: {prompt[:100]}...")

            # This will be replaced with actual implementation
            raise NotImplementedError(
                "ChatGPT network capture not yet implemented. "
                "This requires analyzing ChatGPT's actual UI and network traffic."
            )

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get captured network responses
            # TODO: Filter for the specific chat ID
            captured_responses = self.browser_manager.get_captured_responses()

            # Find the relevant response containing search data
            # TODO: Identify which response contains the search data
            relevant_response = None
            for resp in captured_responses:
                # This logic will need to be updated based on actual network structure
                if 'conversation' in resp['url'] or 'chat' in resp['url']:
                    relevant_response = resp
                    break

            if not relevant_response:
                raise Exception("Could not find search data in network logs")

            # Parse the network response
            parsed_response = NetworkLogParser.parse_chatgpt_log(
                network_response=relevant_response,
                model=model,
                response_time_ms=response_time_ms
            )

            return parsed_response

        except Exception as e:
            raise Exception(f"ChatGPT capture error: {str(e)}")
