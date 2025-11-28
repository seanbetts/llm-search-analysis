"""
ChatGPT network traffic capturer implementation.

Uses browser automation to capture network logs from ChatGPT.
"""

import time
from typing import Optional, Any
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Locator

try:
    from playwright_stealth import Stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

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

    # Model identifier - we can't actually control the model in free ChatGPT
    # So we just use a single identifier for the free tier
    SUPPORTED_MODELS = [
        "chatgpt-free",
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

    def start_browser(self, headless: bool = True) -> None:
        """
        Start browser instance with stealth mode to avoid detection.

        Args:
            headless: Whether to run in headless mode (default: True for seamless UX)

        Raises:
            Exception: If browser fails to start
        """
        try:
            self.playwright = sync_playwright().start()

            # Launch Chrome (not Chromium) to reduce detection
            # Chrome has different fingerprint and may bypass OpenAI's detection
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                channel='chrome',  # Use installed Chrome instead of Chromium
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--no-sandbox'
                ]
            )

            # Create context with realistic viewport and user agent
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            )

            self.page = self.context.new_page()

            # Apply stealth mode to avoid detection if available
            if STEALTH_AVAILABLE:
                stealth = Stealth()
                stealth.apply_stealth_sync(self.page)
                print("  ✓ Stealth mode applied")
            else:
                print("  ⚠️  Stealth mode not available")

            # Set up network interception
            self.browser_manager.setup_network_interception(
                self.page,
                response_filter=lambda resp: 'chatgpt.com' in resp.url
            )

            self.is_active = True
            print(f"✓ Browser started with stealth mode for ChatGPT capture")

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

    def authenticate(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Handle ChatGPT authentication.

        If credentials provided, will login. Otherwise uses anonymous mode.

        Args:
            email: ChatGPT account email (optional)
            password: ChatGPT account password (optional)

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # If credentials provided, use login flow
            if email and password:
                return self._login_with_credentials(email, password)

            # Otherwise use anonymous mode (free ChatGPT)
            print("🌐 Navigating to ChatGPT (anonymous mode)...")
            self.page.goto(self.CHATGPT_URL, wait_until='domcontentloaded', timeout=30000)

            print("⏳ Waiting for page to settle...")
            time.sleep(2)  # Give page time to fully render

            # Check for Cloudflare CAPTCHA
            print("🔍 Checking for Cloudflare CAPTCHA...")
            captcha_selectors = [
                'iframe[src*="cloudflare"]',
                'text="Verify you are human"',
                '[name="cf-turnstile"]',
                '#cf-challenge-running'
            ]

            for selector in captcha_selectors:
                try:
                    if self.page.locator(selector).count() > 0:
                        print("⚠️  CAPTCHA detected!")
                        print("    Cloudflare is blocking automated access.")
                        print("    Waiting 30 seconds for manual CAPTCHA solve...")
                        print("    (If running headless, this will fail)")
                        time.sleep(30)
                        break
                except:
                    continue

            print("🔍 Looking for chat interface...")
            # Just return True - we'll handle UI elements in send_prompt
            # Don't wait here since modals might be blocking
            return True

        except Exception as e:
            print(f"❌ Failed to load ChatGPT: {str(e)}")
            raise Exception(f"Failed to load ChatGPT: {str(e)}")

    def _login_with_credentials(self, email: str, password: str) -> bool:
        """
        Login to ChatGPT with email and password.

        Args:
            email: ChatGPT account email
            password: ChatGPT account password

        Returns:
            True if login successful, False otherwise
        """
        try:
            print("🔐 Logging in to ChatGPT...")

            # Navigate to ChatGPT
            print("🌐 Navigating to ChatGPT...")
            self.page.goto(self.CHATGPT_URL, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)

            # Look for "Log in" button
            print("🔍 Looking for login button...")
            login_button_selectors = [
                'button:has-text("Log in")',
                'a:has-text("Log in")',
                '[data-testid="login-button"]'
            ]

            login_clicked = False
            for selector in login_button_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.count() > 0 and button.is_visible():
                        print(f"  ✓ Found login button: {selector}")
                        button.click()
                        login_clicked = True
                        time.sleep(3)
                        break
                except:
                    continue

            if not login_clicked:
                print("  ⚠️  Login button not found, may already be at login page")

            # Avoid Google sign-in - look for email/password login option
            print("🔍 Looking for email/password login option...")

            # Wait for login page to load
            time.sleep(2)

            # Check if we need to dismiss "Sign in with Google" and use email instead
            email_login_selectors = [
                'button:has-text("Continue with email")',
                'button:has-text("Use email")',
                'a:has-text("Continue with email")',
                '[data-provider="email"]',
            ]

            for selector in email_login_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.count() > 0 and button.is_visible():
                        print(f"  ✓ Found email login option: {selector}")
                        button.click()
                        time.sleep(2)
                        break
                except:
                    continue

            # Enter email
            print("📧 Entering email...")
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[id="email-input"]',
                'input[placeholder*="email" i]'
            ]

            email_entered = False
            for selector in email_selectors:
                try:
                    input_field = self.page.locator(selector).first
                    if input_field.count() > 0:
                        input_field.wait_for(state='visible', timeout=5000)
                        input_field.fill(email)
                        print(f"  ✓ Email entered")
                        email_entered = True
                        time.sleep(1)
                        break
                except Exception as e:
                    continue

            if not email_entered:
                raise Exception("Could not find email input field")

            # Click "Continue" button after entering email (NOT "Continue with Google")
            print("⏭️  Clicking Continue...")

            # First, try to find the specific Continue button (not Google)
            continue_clicked = False

            # Try the submit button directly (most reliable)
            try:
                # Look for button with type="submit" that's NOT a Google button
                submit_buttons = self.page.locator('button[type="submit"]')
                count = submit_buttons.count()
                print(f"  Found {count} submit button(s)")

                for i in range(count):
                    button = submit_buttons.nth(i)
                    button_text = button.inner_text().lower()
                    print(f"    Button {i+1} text: {button_text}")

                    # Skip Google buttons
                    if 'google' in button_text or 'microsoft' in button_text or 'apple' in button_text:
                        print(f"    Skipping (OAuth button)")
                        continue

                    # This should be the email Continue button
                    if button.is_visible():
                        print(f"    ✓ Clicking button {i+1}")
                        button.click()
                        continue_clicked = True
                        time.sleep(3)
                        break
            except Exception as e:
                print(f"  ✗ Error finding submit button: {str(e)[:50]}")

            if not continue_clicked:
                print("  ⚠️  Continue button not found")

            # Enter password (OpenAI login page, not Google)
            print("🔑 Entering password...")
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id="password"]',
                '#password'
            ]

            password_entered = False
            # Try multiple times in case page is loading
            for attempt in range(3):
                if password_entered:
                    break

                for selector in password_selectors:
                    try:
                        input_field = self.page.locator(selector).first
                        if input_field.count() > 0:
                            input_field.wait_for(state='visible', timeout=5000)
                            input_field.fill(password)
                            print(f"  ✓ Password entered")
                            password_entered = True
                            time.sleep(1)
                            break
                    except:
                        continue

                if not password_entered and attempt < 2:
                    print(f"  Waiting for password field... (attempt {attempt + 1}/3)")
                    time.sleep(2)

            if not password_entered:
                # Take screenshot for debugging
                try:
                    self.page.screenshot(path='password_not_found.png')
                    print("📸 Screenshot saved to: password_not_found.png")
                except:
                    pass
                raise Exception("Could not find password input field")

            # Submit login form
            print("🚀 Submitting login...")
            submit_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Log in")',
                'button:has-text("Sign in")',
                'button[type="submit"]'
            ]

            for selector in submit_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.count() > 0 and button.is_visible():
                        button.click()
                        break
                except:
                    continue

            # Wait for login to complete
            print("⏳ Waiting for login to complete...")
            time.sleep(5)

            # Check if we're logged in by looking for chat interface
            print("🔍 Verifying login...")
            chat_interface_selectors = [
                '#prompt-textarea',
                'textarea[placeholder*="Message"]',
                '[data-testid="composer-input"]'
            ]

            logged_in = False
            for selector in chat_interface_selectors:
                try:
                    if self.page.locator(selector).count() > 0:
                        logged_in = True
                        break
                except:
                    continue

            if logged_in:
                print("✅ Login successful!")
                return True
            else:
                # May need 2FA or additional verification
                print("⚠️  Login may require additional verification (2FA, CAPTCHA, etc.)")
                print("    Waiting 30 seconds for manual verification...")
                time.sleep(30)

                # Check again
                for selector in chat_interface_selectors:
                    try:
                        if self.page.locator(selector).count() > 0:
                            print("✅ Login successful after verification!")
                            return True
                    except:
                        continue

                raise Exception("Login failed - could not verify chat interface")

        except Exception as e:
            print(f"❌ Login failed: {str(e)}")
            # Take screenshot for debugging
            try:
                self.page.screenshot(path='login_failed.png')
                print("📸 Screenshot saved to: login_failed.png")
            except:
                pass
            raise Exception(f"Failed to login: {str(e)}")

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
            print(f"Submitting prompt to ChatGPT (model: {model})...")
            print(f"Prompt: {prompt[:100]}...")

            # Handle any modals/overlays that might be blocking the UI
            print("🚫 Checking for modals...")
            self._dismiss_modals()

            # Find textarea FIRST
            print("📝 Looking for textarea...")
            textarea = self._find_textarea()
            if not textarea:
                raise Exception(
                    "Could not find textarea element. "
                    "This is likely due to Cloudflare CAPTCHA blocking automated access. "
                    "Free ChatGPT now requires human verification. "
                    "Consider using API mode instead, or try with a logged-in account."
                )

            # Enter the prompt BEFORE enabling search
            print(f"✍️  Typing prompt...")
            textarea.fill(prompt)
            time.sleep(0.5)

            # Enable search toggle AFTER typing prompt
            print("🔍 Enabling search toggle...")
            search_enabled = self._enable_search_toggle()
            if search_enabled:
                print("  ✓ Search toggle enabled (after typing)")
            else:
                print("  ⚠️  Search toggle not found")

            # Wait a moment for search mode to activate
            time.sleep(1)

            # Submit the prompt
            print("📤 Submitting prompt...")
            submitted = self._submit_prompt(textarea)

            if not submitted:
                raise Exception("Failed to submit prompt")

            # Wait for ChatGPT to respond
            print("⏳ Waiting for ChatGPT to generate response...")
            self._wait_for_response_complete(max_wait=90)
            print("✓ Response appears complete, extracting response text...")

            # Extract the actual response text from the page
            response_text = self._extract_response_text()

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get captured network responses
            captured_responses = self.browser_manager.get_captured_responses()

            # Find the event stream response containing search data
            print(f"📊 Captured {len(captured_responses)} network responses")

            # Look for event-stream response (contains all search data)
            event_stream_response = None
            for resp in captured_responses:
                if 'event-stream' in resp.get('content_type', ''):
                    event_stream_response = resp
                    print(f"✓ Found event stream: {resp['url'][:80]} ({resp.get('body_size', 0)} bytes)")
                    break

            if not event_stream_response:
                print("⚠️  No event stream found in network capture")
                # Return response with extracted text but no search data
                return ProviderResponse(
                    response_text=response_text if response_text else "ChatGPT responded but network capture did not find event stream data.",
                    search_queries=[],
                    sources=[],
                    citations=[],
                    raw_response={'captured_responses': len(captured_responses)},
                    model="ChatGPT",
                    provider='openai',
                    response_time_ms=response_time_ms
                )

            # Parse the event stream response
            print("🔍 Parsing event stream for search data...")
            parsed_response = NetworkLogParser.parse_chatgpt_log(
                network_response=event_stream_response,
                model="ChatGPT",
                response_time_ms=response_time_ms,
                extracted_response_text=response_text
            )

            print(f"✓ Parsed: {len(parsed_response.search_queries)} queries, {len(parsed_response.sources)} sources")

            return parsed_response

        except Exception as e:
            raise Exception(f"ChatGPT capture error: {str(e)}")

    def _extract_response_text(self) -> str:
        """Extract ChatGPT's response text from the page."""
        try:
            # ChatGPT responses are typically in article or div elements
            # Try to find the last assistant message
            selectors = [
                'article[data-testid^="conversation-turn"]',
                '.markdown',
                '[data-message-author-role="assistant"]'
            ]

            for selector in selectors:
                try:
                    elements = self.page.locator(selector)
                    count = elements.count()
                    if count > 0:
                        # Get the last one (most recent response)
                        last_elem = elements.nth(count - 1)
                        text = last_elem.inner_text()
                        if text and len(text) > 10:  # Sanity check
                            # Remove "ChatGPT said:" prefix if present
                            text = text.replace("ChatGPT said:", "").strip()
                            # Also remove common prefixes
                            text = text.replace("ChatGPT:", "").strip()
                            print(f"  ✓ Extracted {len(text)} characters of response text")
                            return text
                except:
                    continue

            print("  ⚠️  Could not extract response text from page")
            return ""

        except Exception as e:
            print(f"  ✗ Error extracting response: {str(e)[:50]}")
            return ""

    def _wait_for_response_complete(self, max_wait: int = 60):
        """
        Wait for ChatGPT to complete its response.

        Args:
            max_wait: Maximum seconds to wait (default 60)
        """
        print(f"  Waiting for response (max {max_wait}s)...")

        # Look for signs that ChatGPT is generating
        generating_indicators = [
            'button[aria-label*="Stop"]',
            'button:has-text("Stop generating")',
            '[data-testid="stop-button"]'
        ]

        # Wait initial period for response to start
        time.sleep(3)

        # Check if ChatGPT is generating
        is_generating = False
        for selector in generating_indicators:
            try:
                if self.page.locator(selector).count() > 0:
                    print("  Response generation started...")
                    is_generating = True
                    break
            except:
                continue

        if is_generating:
            # Wait for generation to complete (stop button to disappear)
            print("  Waiting for generation to complete...")
            waited = 0
            while waited < max_wait:
                all_gone = True
                for selector in generating_indicators:
                    try:
                        if self.page.locator(selector).count() > 0:
                            all_gone = False
                            break
                    except:
                        continue

                if all_gone:
                    print(f"  ✓ Generation complete after {waited}s")
                    time.sleep(2)  # Extra wait for network traffic to finish
                    return

                time.sleep(1)
                waited += 1
                if waited % 5 == 0:
                    print(f"  Still generating... ({waited}s)")

            print(f"  ⚠️  Max wait time reached ({max_wait}s)")
        else:
            # No generation indicator found, wait a reasonable time
            print("  No generation indicator found, waiting 15s...")
            time.sleep(15)

    def _enable_search_toggle(self) -> bool:
        """
        Find and enable the search toggle button in ChatGPT UI.

        Returns:
            True if search toggle was found and clicked, False otherwise
        """
        # Possible selectors for the search toggle/button
        search_selectors = [
            'button:has-text("Search the web")',
            'button:has-text("Search")',
            'button[aria-label*="search"]',
            'button[aria-label*="Search"]',
            '[data-testid*="search"]',
            'button[title*="search"]',
            'button[title*="Search"]',
            # Icon buttons near the textarea
            'button svg[class*="search"]',
        ]

        time.sleep(1)  # Give UI time to render

        for selector in search_selectors:
            try:
                print(f"  Trying: {selector}")
                buttons = self.page.locator(selector)
                count = buttons.count()

                if count > 0:
                    print(f"    Found {count} match(es)")
                    # Try each matching button
                    for i in range(min(count, 3)):  # Try up to 3 matches
                        try:
                            button = buttons.nth(i)
                            if button.is_visible():
                                print(f"    Button {i+1} is visible, clicking...")
                                button.click()
                                time.sleep(1)  # Wait for toggle to take effect
                                return True
                        except Exception as e:
                            print(f"    Button {i+1} click failed: {str(e)[:50]}")
                            continue
            except Exception as e:
                continue

        return False

    def _dismiss_modals(self):
        """Dismiss any modals or overlays blocking the UI."""
        modal_selectors = [
            'button:has-text("Accept")',
            'button:has-text("Accept all")',
            'button:has-text("Accept cookies")',
            'button:has-text("Continue")',
            'button:has-text("Okay")',
            'button:has-text("OK")',
            'button:has-text("Got it")',
            'button:has-text("Log in")',  # Try to click past login prompts
            'button:has-text("Stay logged out")',
            '[role="dialog"] button',
            '[aria-label*="close"]',
            '[aria-label*="dismiss"]',
        ]

        print("  Checking for modals/overlays...")
        dismissed_any = False
        for selector in modal_selectors:
            try:
                buttons = self.page.locator(selector)
                count = buttons.count()
                if count > 0:
                    print(f"  Found {count} button(s) matching: {selector}")
                    for i in range(count):
                        try:
                            button = buttons.nth(i)
                            if button.is_visible():
                                print(f"  Clicking button {i+1}...")
                                button.click()
                                time.sleep(2)
                                dismissed_any = True
                                break
                        except:
                            continue
                    if dismissed_any:
                        break
            except Exception as e:
                continue

        if dismissed_any:
            print("  ✓ Dismissed modal")
            time.sleep(1)  # Brief wait after dismissal
        else:
            print("  No modals found")

    def _find_textarea(self) -> Optional[Any]:
        """Find the prompt textarea element."""
        textarea_selectors = [
            '#prompt-textarea',
            'textarea[id="prompt-textarea"]',
            'textarea[data-id="root"]',
            'textarea[placeholder*="Message"]',
            'textarea[placeholder*="Ask"]',
            'textarea[placeholder*="Send"]',
            'div[contenteditable="true"]',  # ChatGPT might use contenteditable
            'textarea',
        ]

        # Give page brief time to load
        time.sleep(1)

        for selector in textarea_selectors:
            try:
                print(f"  Trying selector: {selector}")
                elems = self.page.locator(selector)
                count = elems.count()
                print(f"    Found {count} element(s)")

                if count > 0:
                    # Try each matching element
                    for i in range(count):
                        try:
                            elem = elems.nth(i)
                            print(f"    Checking element {i+1}/{count} for visibility...")
                            elem.wait_for(state='visible', timeout=3000)
                            print(f"    ✓ Element {i+1} is visible!")
                            return elem
                        except Exception as e:
                            print(f"    Element {i+1} not visible: {str(e)[:50]}")
                            continue
            except Exception as e:
                print(f"  ✗ Selector failed: {str(e)[:50]}")
                continue

        # Last resort: take screenshot to help debug
        try:
            screenshot_path = 'chatgpt_textarea_not_found.png'
            self.page.screenshot(path=screenshot_path)
            print(f"  📸 Screenshot saved to: {screenshot_path}")
        except:
            pass

        print("  ❌ No textarea found with any selector")
        return None

    def _submit_prompt(self, textarea) -> bool:
        """Submit the prompt via button or Enter key."""
        submit_selectors = [
            'button[data-testid="send-button"]',
            'button[aria-label*="Send"]',
            'button[type="submit"]',
        ]

        for selector in submit_selectors:
            try:
                button = self.page.locator(selector).first
                if button.count() > 0 and button.is_visible():
                    button.click()
                    return True
            except Exception:
                continue

        # Fallback: try Enter key
        try:
            textarea.press('Enter')
            return True
        except Exception:
            return False
