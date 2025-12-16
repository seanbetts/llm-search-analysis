"""Google AI Mode capturer using Playwright network interception.

This capturer navigates to https://www.google.com/aimode, submits a prompt, and
parses the `/async/folif` response into the common ProviderResponse structure.
"""

from __future__ import annotations

import re
import time

from playwright.sync_api import sync_playwright

from backend.app.services.providers.base_provider import ProviderResponse

from .base_capturer import BaseCapturer
from .browser_manager import BrowserManager
from .google_aimode_parser import choose_latest_folif_response, parse_google_aimode_folif_html


class GoogleAIModeCapturer(BaseCapturer):
  """Google AI Mode network traffic capturer."""

  AIMODE_URL = "https://www.google.com/aimode"
  SUPPORTED_MODELS = ["google-aimode"]

  def __init__(self, status_callback=None):  # noqa: ANN001
    """Initialize capturer.

    Args:
      status_callback: Optional callable that accepts status messages.
    """
    super().__init__()
    self.playwright = None
    self.browser = None
    self.context = None
    self.page = None
    self.browser_manager = BrowserManager()
    self._status_callback = status_callback

  def _log_status(self, message: str) -> None:
    """Emit status updates to the UI callback, when provided."""
    if self._status_callback:
      try:
        self._status_callback(message)
      except Exception:
        pass

  def get_provider_name(self) -> str:
    """Return provider name."""
    return "google"

  def get_supported_models(self) -> list[str]:
    """Return supported model identifiers."""
    return self.SUPPORTED_MODELS

  def start_browser(self, headless: bool = True) -> None:
    """Start browser instance."""
    self._log_status("🚀 Starting browser...")
    self.playwright = sync_playwright().start()
    self.browser = self.playwright.chromium.launch(headless=headless, channel="chrome")
    self.context = self.browser.new_context(viewport={"width": 1440, "height": 900})
    self.page = self.context.new_page()
    self.browser_manager.setup_network_interception(
      self.page,
      response_filter=lambda resp: "google.com" in resp.url,
    )
    self.is_active = True

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
    finally:
      self.is_active = False

  def authenticate(self, *_args, **_kwargs) -> bool:
    """No authentication is required for Google AI Mode."""
    return True

  def send_prompt(self, prompt: str, model: str = "google-aimode", enable_search: bool = True) -> ProviderResponse:
    """Submit a prompt to AI Mode and return normalized response."""
    del enable_search  # AI Mode implicitly searches as needed.
    if not self.page:
      raise RuntimeError("Browser not started")
    if model not in self.SUPPORTED_MODELS:
      raise ValueError(f"Unsupported model: {model}")

    self.browser_manager.clear_captured_data()

    self._log_status("🌐 Navigating to Google AI Mode...")
    self.page.goto(self.AIMODE_URL, wait_until="domcontentloaded", timeout=30000)
    # Give the app shell time to hydrate; AI Mode is a heavy SPA.
    try:
      self.page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
      pass

    # Accept consent dialogs if they appear (best-effort).
    try:
      consent = self.page.get_by_role("button", name=re.compile("accept all", re.I))
      if consent and consent.is_visible():
        consent.click(timeout=2000)
    except Exception:
      pass

    # Find a textbox/textarea and submit prompt. Use broad fallbacks for resilience.
    self._log_status("📝 Entering prompt...")
    input_locator = None
    # AI Mode currently exposes the prompt box as a textarea with aria-label "Ask anything".
    try:
      self.page.wait_for_selector("textarea[aria-label='Ask anything']", timeout=10000)
    except Exception:
      pass
    locator_candidates = [
      ("textarea[aria-label]", self.page.locator("textarea[aria-label='Ask anything']").first),
      ("textarea[placeholder]", self.page.locator("textarea[placeholder='Ask anything']").first),
      ("textarea.ITIRGe", self.page.locator("textarea.ITIRGe").first),
      # Most robust: accessibility role
      ("role:textbox", self.page.get_by_role("textbox").first),
      # Common inputs
      ("textarea", self.page.locator("textarea").first),
      ("role=textbox", self.page.locator("[role='textbox']").first),
      ("contenteditable", self.page.locator("[contenteditable='true']").first),
      ("input", self.page.locator("input[type='text'], input:not([type])").first),
    ]
    for _label, loc in locator_candidates:
      try:
        if loc and loc.is_visible(timeout=3000):
          input_locator = loc
          break
      except Exception:
        continue
    if input_locator is None:
      # Provide some lightweight diagnostics.
      counts = {}
      for label, loc in locator_candidates:
        try:
          counts[label] = int(loc.count())  # type: ignore[union-attr]
        except Exception:
          counts[label] = 0
      raise RuntimeError(f"Could not find input box on /aimode. Candidates={counts}")

    started = time.time()
    input_locator.click()
    # Some AI Mode inputs are contenteditable and do not support `.fill()`.
    try:
      input_locator.fill(prompt)
    except Exception:
      self.page.keyboard.type(prompt)

    # Prefer clicking the send button (more reliable than Enter for textarea inputs).
    send_clicked = False
    send_locators = [
      # Known send icon controller in AI Mode markup.
      self.page.locator("button:has(svg[jscontroller='Veb2cb'])").first,
      self.page.locator("button:has(div.wilSz.Iq9dx)").first,
      # Best-effort generic label matches.
      self.page.get_by_role("button", name=re.compile(r"(send|submit|ask)", re.I)).first,
    ]
    for loc in send_locators:
      try:
        if loc and loc.is_visible(timeout=1000) and loc.is_enabled():
          loc.click()
          send_clicked = True
          break
      except Exception:
        continue

    if not send_clicked:
      # Fallback: try Enter if we couldn't locate a send button.
      self.page.keyboard.press("Enter")

    # Wait for a folif response to be captured.
    self._log_status("⏳ Waiting for AI Mode response...")
    deadline = time.time() + 60
    folif_html = None
    while time.time() < deadline:
      body = choose_latest_folif_response(self.browser_manager.get_captured_responses(url_pattern="/async/folif"))
      if isinstance(body, str) and body.strip():
        folif_html = body
        break
      time.sleep(0.5)

    response_time_ms = int((time.time() - started) * 1000)
    if not folif_html:
      # Try clicking a likely send/submit button (best-effort) and wait again briefly.
      try:
        for loc in send_locators:
          if loc and loc.is_visible(timeout=1000) and loc.is_enabled():
            loc.click()
            break
        extra_deadline = time.time() + 15
        while time.time() < extra_deadline:
          body = choose_latest_folif_response(self.browser_manager.get_captured_responses(url_pattern="/async/folif"))
          if isinstance(body, str) and body.strip():
            folif_html = body
            break
          time.sleep(0.5)
      except Exception:
        pass

    if not folif_html:
      raise RuntimeError("Timed out waiting for /async/folif response")

    self._log_status("✅ Parsing response...")
    return parse_google_aimode_folif_html(
      folif_html,
      model=model,
      provider="google",
      response_time_ms=response_time_ms,
    )
