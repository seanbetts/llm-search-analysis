"""
ChatGPT network traffic capturer implementation.

Uses browser automation to capture network logs from ChatGPT.
"""

import time
import re
import html
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

    def __init__(self, storage_state_path: Optional[str] = None):
        """Initialize ChatGPT capturer.

        Args:
            storage_state_path: Path to JSON file storing session data (cookies, localStorage).
                               If None, uses a default file in the project.
        """
        super().__init__()
        self.playwright = None
        self.browser_manager = BrowserManager()

        # Set up storage state file path for session persistence
        if storage_state_path is None:
            # Use default file in project
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            storage_state_path = str(project_root / 'data' / 'chatgpt_session.json')

        self.storage_state_path = storage_state_path

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openai"

    def get_supported_models(self) -> list[str]:
        """Get list of supported ChatGPT models."""
        return self.SUPPORTED_MODELS

    def start_browser(self, headless: bool = True) -> None:
        """
        Start browser instance with stealth mode to avoid detection.
        Supports two modes:
        1. CDP Mode (Docker): Connect to Chrome running on host Mac via CDP
        2. Launch Mode (Local): Launch Chrome locally

        Restores session state from file if available.

        Args:
            headless: Whether to run in headless mode (default: True for seamless UX)
                     Note: Ignored in CDP mode (headless controlled by host Chrome)

        Raises:
            Exception: If browser fails to start or connect
        """
        try:
            from pathlib import Path
            import os

            self.playwright = sync_playwright().start()

            # Check if we should connect via CDP (Docker mode)
            cdp_url = os.getenv('CHROME_CDP_URL')

            if cdp_url:
                # CDP Mode: Connect to Chrome running on host
                print(f"🔗 Connecting to Chrome via CDP at {cdp_url}")

                # Fetch WebSocket URL manually with proper Host header
                # Chrome rejects requests with non-localhost Host headers
                import json
                import urllib.request

                try:
                    # Parse the CDP URL to get host and port
                    from urllib.parse import urlparse
                    parsed = urlparse(cdp_url)

                    # Create request with localhost Host header
                    version_url = f"{cdp_url}/json/version"
                    req = urllib.request.Request(version_url)
                    req.add_header('Host', 'localhost:9223')  # Force localhost Host header

                    # Fetch the WebSocket URL
                    with urllib.request.urlopen(req, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        ws_endpoint = data['webSocketDebuggerUrl']

                    # Replace localhost with actual host for Docker
                    # ws://localhost:9223/... -> ws://host.docker.internal:9223/...
                    ws_endpoint = ws_endpoint.replace('localhost', parsed.hostname)

                    print(f"🔗 WebSocket endpoint: {ws_endpoint}")

                    # Connect directly to WebSocket endpoint
                    self.browser = self.playwright.chromium.connect_over_cdp(ws_endpoint)
                    print("✅ Connected to host Chrome successfully")

                except Exception as e:
                    print(f"❌ Failed to connect via CDP: {e}")
                    print("💡 Falling back to local Chrome launch...")
                    cdp_url = None  # Fall through to local launch

            if not cdp_url:
                # Launch Mode: Start Chrome locally (for non-Docker environments)
                print("🚀 Launching Chrome locally")
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    channel='chrome',  # Use installed Chrome instead of Chromium
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--no-sandbox',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-setuid-sandbox'
                    ]
                )

            # Check if storage state file exists
            storage_state = None
            if os.path.exists(self.storage_state_path):
                print(f"📁 Found session file: {self.storage_state_path}")
                storage_state = self.storage_state_path
            else:
                print(f"📁 No existing session (will create at: {self.storage_state_path})")

            # Create context with realistic viewport and user agent
            # Load storage state if available
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                storage_state=storage_state,  # Will be None if file doesn't exist
                permissions=["clipboard-read", "clipboard-write"]
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

    def authenticate(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Handle ChatGPT authentication.

        First checks if already logged in (from persistent session).
        If credentials provided and not logged in, will login. Otherwise uses anonymous mode.

        Args:
            email: ChatGPT account email (optional)
            password: ChatGPT account password (optional)

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Navigate to ChatGPT
            print("🌐 Navigating to ChatGPT...")
            self.page.goto(self.CHATGPT_URL, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)

            # Check if we're already logged in from saved session
            print("🔍 Checking for existing session...")
            if self._is_logged_in():
                print("✅ Already logged in (session restored from saved state)")
                # Save session if we're logged in but don't have a session file yet
                # This handles cases where cookies persist from system Chrome
                import os
                if not os.path.exists(self.storage_state_path):
                    print("💾 Saving current session for future use...")
                    self._save_session()
                return True

            # If credentials provided, use login flow
            if email and password:
                print("🔐 Not logged in, attempting to authenticate...")
                success = self._login_with_credentials(email, password)
                if success:
                    # Save session state after successful login
                    self._save_session()
                return success

            # Otherwise use anonymous mode (free ChatGPT)
            print("👤 Using anonymous mode (no credentials provided)...")

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

    def _save_session(self) -> None:
        """Save current session state (cookies, localStorage) to file."""
        try:
            import os
            from pathlib import Path

            # Create data directory if it doesn't exist
            os.makedirs(Path(self.storage_state_path).parent, exist_ok=True)

            # Save storage state
            self.context.storage_state(path=self.storage_state_path)
            print(f"💾 Session saved to: {self.storage_state_path}")

        except Exception as e:
            print(f"⚠️  Failed to save session: {str(e)[:50]}")

    def _is_logged_in(self) -> bool:
        """
        Check if already logged in by looking for chat interface.

        Returns:
            True if logged in, False otherwise
        """
        try:
            # Check for chat interface elements
            chat_interface_selectors = [
                '#prompt-textarea',
                'textarea[placeholder*="Message"]',
                '[data-testid="composer-input"]'
            ]

            # Also check that login/signup buttons are NOT present
            login_button_selectors = [
                'button:has-text("Log in")',
                'a:has-text("Log in")',
                'button:has-text("Sign up")',
                'a:has-text("Sign up")',
            ]

            # Look for chat interface
            has_chat_interface = False
            for selector in chat_interface_selectors:
                try:
                    if self.page.locator(selector).count() > 0:
                        has_chat_interface = True
                        break
                except:
                    continue

            # Look for login buttons
            has_login_button = False
            for selector in login_button_selectors:
                try:
                    button = self.page.locator(selector).first
                    if button.count() > 0 and button.is_visible():
                        has_login_button = True
                        break
                except:
                    continue

            # Logged in if we have chat interface and no login button
            return has_chat_interface and not has_login_button

        except Exception as e:
            print(f"  ⚠️  Error checking login status: {str(e)[:50]}")
            return False

    def _login_with_credentials(self, email: str, password: str) -> bool:
        """
        Login to ChatGPT with email and password.
        Assumes we're already on the ChatGPT page.

        Args:
            email: ChatGPT account email
            password: ChatGPT account password

        Returns:
            True if login successful, False otherwise
        """
        try:
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
                print("   Waiting 10 seconds for manual verification...")
                try:
                    self.page.wait_for_timeout(10000)
                except Exception:
                    pass

                # Re-check login after manual verification
                logged_in = False
                for selector in chat_interface_selectors:
                    try:
                        if self.page.locator(selector).count() > 0:
                            logged_in = True
                            break
                    except:
                        continue

                if logged_in:
                    print("✅ Login successful after manual verification!")
                    return True

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

            # Try to enable search using /search command first (simpler and more reliable)
            print("🔍 Enabling web search...")
            print("  Method 1: Trying /search command...")
            # Type "/search" and then press Space to activate the command
            textarea.type("/search")
            time.sleep(0.3)
            textarea.press("Space")  # Press Space key to trigger /search recognition
            time.sleep(1.0)  # Wait longer for /search to be recognized and UI to update

            # Check if /search activated search mode (look for search indicator in UI)
            search_activated = self._check_search_activated()

            if search_activated:
                print("  ✓ Search enabled via /search command")
                # Now type the actual prompt
                textarea.type(prompt)
                time.sleep(0.5)
            else:
                print("  ⚠️  /search command didn't activate search, trying menu method...")
                # Clear the /search prefix and revert to plain prompt
                textarea.fill(prompt)
                time.sleep(0.5)

                # Fallback: Try menu-based search toggle
                search_enabled = self._enable_search_toggle()
                if search_enabled:
                    print("  ✓ Search enabled via menu")
                else:
                    print("  ⚠️  Menu method also failed, proceeding without search")

            # Wait a moment for search mode to fully activate
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
            response_text, response_html = self._extract_response_text()

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get captured network responses
            captured_responses = self.browser_manager.get_captured_responses()

            # Find the event stream response containing search data
            print(f"📊 Captured {len(captured_responses)} network responses")

            # Look for event-stream response (contains all search data)
            event_stream_response = None
            largest_stream = None
            for resp in captured_responses:
                if 'event-stream' in resp.get('content_type', ''):
                    if not event_stream_response:
                        event_stream_response = resp
                    # track largest by body_size
                    if not largest_stream or resp.get('body_size', 0) > largest_stream.get('body_size', 0):
                        largest_stream = resp

            if not event_stream_response and largest_stream:
                event_stream_response = largest_stream

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
            # Preserve the raw event stream in the response for debugging
            parsed_response.raw_response = event_stream_response

            print(f"✓ Parsed: {len(parsed_response.search_queries)} queries, {len(parsed_response.sources)} sources")

            return parsed_response

        except Exception as e:
            raise Exception(f"ChatGPT capture error: {str(e)}")

    def _extract_response_text(self):
        """Extract ChatGPT's response text from the page, preferring the Copy button markdown."""
        try:
            # ChatGPT responses are typically in article or div elements
            # Try to find the last assistant message
            selectors = [
                '[data-message-author-role="assistant"] article',
                'article[data-testid^="conversation-turn"]',
                '.markdown',
                '[data-testid="conversation-turn"]',
                '[data-message-author-role="assistant"]'
            ]

            for selector in selectors:
                try:
                    elements = self.page.locator(selector)
                    count = elements.count()
                    if count > 0:
                        # Get the last one (most recent response)
                        last_elem = elements.nth(count - 1)
                        # Try to click the Copy button inside this block
                        copy_btn = last_elem.locator('button[data-testid="copy-turn-action-button"]')
                        clipboard_text = ""
                        try:
                            for attempt in range(3):
                                if copy_btn.count() > 0:
                                    btn = copy_btn.first
                                    btn.wait_for(state="visible", timeout=5000)
                                    btn.click(timeout=2000)
                                    self.page.wait_for_timeout(500)
                                    clipboard_text = self.page.evaluate("navigator.clipboard.readText()")
                                    if clipboard_text:
                                        break
                                self.page.wait_for_timeout(500)
                        except Exception as e:
                            print(f"  ⚠️  Copy button fetch failed: {str(e)[:50]}")

                        html_content = last_elem.inner_html()
                        text_content = last_elem.inner_text()

                        if clipboard_text and len(clipboard_text) > 5:
                            print("  ✓ Extracted response via Copy button")
                            return clipboard_text.strip(), ""

                        # Fallback: convert anchor tags in HTML to markdown to preserve URLs
                        if html_content and len(html_content) > 10:
                            md = html_content
                            md = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', md, flags=re.IGNORECASE|re.DOTALL)
                            md = re.sub(r'<[^>]+>', '', md)  # strip other tags
                            md = html.unescape(md).strip()
                            if md:
                                print("  ✓ Extracted response via HTML fallback")
                                return md, ""

                        # Final fallback to plain text
                        if text_content and len(text_content) > 10:
                            text_content = text_content.replace("ChatGPT said:", "").replace("ChatGPT:", "").strip()
                            print(f"  ✓ Extracted response text (fallback)")
                            return text_content or "", ""
                except:
                    continue

            print("  ⚠️  Could not extract response text from page")
            return "", ""

        except Exception as e:
            print(f"  ✗ Error extracting response: {str(e)[:50]}")
            return "", ""

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

    def _check_search_activated(self) -> bool:
        """
        Check if web search mode is activated in the UI.

        Looks for the Search pill/badge button that appears when search is enabled.
        The button has aria-label="Search, click to remove" and class="__composer-pill".

        Returns:
            True if search appears to be activated, False otherwise
        """
        try:
            # Give UI more time to update after /search command
            time.sleep(0.5)

            # Primary indicator: Search pill button with specific aria-label
            # This appears when /search command or menu toggle activates search
            search_pill_selectors = [
                'button[aria-label="Search, click to remove"]',  # Most specific
                'button.__composer-pill:has-text("Search")',     # Class + text
                'button[aria-label*="Search"][class*="composer-pill"]',  # Flexible
            ]

            print("    Checking for search pill button...")
            for selector in search_pill_selectors:
                try:
                    count = self.page.locator(selector).count()
                    if count > 0:
                        print(f"    ✓ Found search pill: {selector} ({count} matches)")
                        return True
                except Exception as e:
                    continue

            # Debug: Print what's actually in the composer area
            try:
                composer = self.page.locator('[data-testid="composer"]').first
                if composer.count() > 0:
                    text = composer.inner_text()
                    print(f"    Composer text: {text[:100]}")
            except:
                pass

            return False

        except Exception as e:
            print(f"  ⚠️  Error checking search activation: {str(e)[:50]}")
            return False

    def _enable_search_toggle(self) -> bool:
        """
        Enable web search in ChatGPT UI via: Add button → More → Web search.

        This is a fallback method when /search command doesn't work.

        Returns:
            True if search was enabled, False otherwise
        """
        try:
            # Step 1: Find and click the "Add files and more" button
            print("  Looking for 'Add' button...")
            add_button = self.page.locator('button[aria-label*="Add"]').first

            if add_button.count() == 0:
                print("    ⚠️  'Add' button not found")
                return False

            print(f"    Clicking 'Add files and more' button...")
            add_button.click()
            time.sleep(1)

            # Step 2: Hover over "More" menuitem to open submenu
            print("  Looking for 'More' menu item...")
            # The "More" option is a menuitem that appears after clicking Add
            # It has aria-haspopup="menu" and needs hover to show submenu
            more_menuitem = self.page.locator('[role="menuitem"][data-has-submenu]').filter(has_text="More").first

            if more_menuitem.count() == 0:
                print("    ⚠️  'More' menu item not found")
                return False

            print(f"    Hovering over 'More'...")
            more_menuitem.hover()
            time.sleep(1)

            # Step 3: Find and click "Web search" in the submenu
            print("  Looking for 'Web search' option...")
            # Note: It's role="menuitemradio" with text "Web search" (lowercase 's')
            web_search_menuitem = self.page.locator('[role="menuitemradio"]').filter(has_text="Web search").first

            if web_search_menuitem.count() == 0:
                print("    ⚠️  'Web search' option not found")
                return False

            print(f"    Clicking 'Web search'...")
            web_search_menuitem.click()
            time.sleep(1)
            print("    ✓ Web search enabled")
            return True

        except Exception as e:
            print(f"  ✗ Error enabling search: {str(e)[:50]}")
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
