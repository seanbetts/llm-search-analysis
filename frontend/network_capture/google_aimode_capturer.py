"""Google AI Mode capturer using Playwright network interception.

This capturer navigates to https://www.google.com/aimode, submits a prompt, and
parses the `/async/folif` response into the common ProviderResponse structure.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

from backend.app.services.providers.base_provider import ProviderResponse, SearchQuery

from .base_capturer import BaseCapturer
from .browser_manager import BrowserManager
from .google_aimode_parser import (
  choose_latest_folif_response,
  extract_sources_from_folif_html,
  parse_google_aimode_folif_html,
)

try:
  from playwright_stealth import Stealth
  STEALTH_AVAILABLE = True
except ImportError:  # pragma: no cover
  STEALTH_AVAILABLE = False


class GoogleAIModeCapturer(BaseCapturer):
  """Google AI Mode network traffic capturer."""

  AIMODE_URL = "https://www.google.com/aimode"
  SUPPORTED_MODELS = ["google-aimode"]

  def __init__(self, storage_state_path: str | None = None, status_callback=None):  # noqa: ANN001
    """Initialize capturer.

    Args:
      storage_state_path: Optional Playwright storageState file path used to
        persist captcha/consent cookies across runs.
      status_callback: Optional callable that accepts status messages.
    """
    super().__init__()
    self.playwright = None
    self.browser = None
    self.context = None
    self.page = None
    self.browser_manager = BrowserManager()
    self._status_callback = status_callback
    if storage_state_path is None:
      project_root = Path(__file__).resolve().parents[2]
      storage_state_path = str(project_root / "data" / "google_aimode_session.json")
    self.storage_state_path = storage_state_path

  def _connect_over_cdp(self, cdp_url: str):
    """Connect to an existing Chrome instance via CDP.

    This mirrors the ChatGPT capturer's behavior of resolving the WebSocket
    debugger endpoint first, which is more reliable across Docker/host setups.

    Args:
      cdp_url: Base CDP HTTP URL (e.g. `http://localhost:9223`).

    Returns:
      Connected Playwright browser instance.
    """
    parsed = urlparse(cdp_url)
    version_url = f"{cdp_url}/json/version"
    req = Request(version_url)
    req.add_header("Host", f"localhost:{parsed.port or 9222}")
    with urlopen(req, timeout=5) as response:
      data = response.read().decode("utf-8")

    import json
    payload = json.loads(data)
    ws_endpoint = payload["webSocketDebuggerUrl"]
    ws_endpoint = ws_endpoint.replace("localhost", parsed.hostname or "localhost")
    return self.playwright.chromium.connect_over_cdp(ws_endpoint)

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
    self._headless = headless
    self.playwright = sync_playwright().start()
    chrome_args = [
      "--disable-blink-features=AutomationControlled",
      "--disable-infobars",
      "--disable-dev-shm-usage",
      "--disable-web-security",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--disable-setuid-sandbox",
    ]
    ignore_default_args = ["--enable-automation"]

    # Best option to reduce repeated CAPTCHA prompts: reuse a persistent user profile.
    cdp_url = os.getenv("CHROME_CDP_URL")
    if cdp_url:
      self._log_status(f"🔗 Attaching to Chrome via CDP: {cdp_url}")
      self.browser = self._connect_over_cdp(cdp_url)
      contexts = getattr(self.browser, "contexts", None) or []
      self.context = contexts[0] if contexts else self.browser.new_context()
      self.page = self.context.new_page()
      self.is_active = True
      self.browser_manager.setup_network_interception(
        self.page,
        response_filter=lambda resp: "google.com" in resp.url,
      )
      return

    use_persistent_profile = os.getenv("GOOGLE_AIMODE_USE_PERSISTENT_PROFILE", "1") != "0"
    user_data_dir_value = os.getenv("GOOGLE_AIMODE_USER_DATA_DIR")
    user_data_dir = (
      Path(user_data_dir_value)
      if user_data_dir_value
      else (Path.cwd() / "data" / "google_aimode_profile")
    )

    if use_persistent_profile:
      user_data_dir.mkdir(parents=True, exist_ok=True)
      self._log_status(f"🔒 Using persistent Chrome profile: {user_data_dir}")
      self.context = self.playwright.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        headless=headless,
        channel="chrome",
        args=chrome_args,
        ignore_default_args=ignore_default_args,
        viewport={"width": 1440, "height": 900},
        user_agent=(
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        permissions=["clipboard-read", "clipboard-write"],
      )
      self.browser = self.context.browser
      self.page = self.context.new_page()
    else:
      self.browser = self.playwright.chromium.launch(
        headless=headless,
        channel="chrome",
        args=chrome_args,
        ignore_default_args=ignore_default_args,
      )

      storage_state = None
      if self.storage_state_path:
        path = Path(self.storage_state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
          storage_state = self.storage_state_path

      self.context = self.browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent=(
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        storage_state=storage_state,
        permissions=["clipboard-read", "clipboard-write"],
      )
      self.page = self.context.new_page()

    if STEALTH_AVAILABLE:
      try:
        Stealth().apply_stealth_sync(self.page)
        self._log_status("✓ Stealth mode applied")
      except Exception:
        self._log_status("⚠️ Stealth mode failed to apply")
    self.browser_manager.setup_network_interception(
      self.page,
      response_filter=lambda resp: "google.com" in resp.url,
    )
    self.is_active = True

  def stop_browser(self) -> None:
    """Stop browser and cleanup."""
    try:
      if self.context and self.storage_state_path:
        try:
          Path(self.storage_state_path).parent.mkdir(parents=True, exist_ok=True)
          self.context.storage_state(path=self.storage_state_path)
        except Exception:
          pass
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

  def _maybe_wait_for_challenge_clear(self, timeout_seconds: int = 180) -> None:
    """Wait for a visible prompt input to appear when a CAPTCHA blocks the page.

    Google frequently blocks `/aimode` behind a bot-check. When running in
    headed mode, we keep the browser open so the user can complete the challenge.
    """
    if not self.page or getattr(self, "_headless", True):
      return

    self._log_status("⚠️ CAPTCHA/bot-check detected. Please complete it in the browser window…")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
      locator = self._find_prompt_input_locator(wait_for_textarea=False)
      if locator is not None:
        self._log_status("✅ CAPTCHA cleared; continuing…")
        return
      time.sleep(2)

  def _find_prompt_input_locator(self, *, wait_for_textarea: bool = True):
    """Return a Playwright locator for the prompt input when available."""
    if not self.page:
      return None

    if wait_for_textarea:
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
          return loc
      except Exception:
        continue
    return None

  def _extract_search_queries(self) -> list[SearchQuery]:
    """Extract best-effort search queries from captured Google requests.

    AI Mode performs searches behind the scenes; we attempt to infer query strings
    from request URLs / payloads so the persisted schema stays consistent.

    Returns:
      List of SearchQuery objects (sources are not mapped in web-capture mode).
    """
    requests = getattr(self.browser_manager, "intercepted_requests", []) or []
    candidates: list[str] = []

    def is_likely_human_query(value: str) -> bool:
      """Return True when a captured query value looks like a real search query."""
      lowered = value.lower().strip()
      # Google image thumbnail requests often look like `tbn:ANd9Gc...`.
      if lowered.startswith("tbn:") or "tbn:and9gc" in lowered or "tbn:an" in lowered:
        return False
      if "encrypted-tbn" in lowered:
        return False
      # Filter out hash-like single tokens.
      if len(value.split()) == 1 and re.fullmatch(r"[A-Za-z0-9_-]{20,}", value):
        return False
      return True

    def consider(value: str) -> None:
      if not value:
        return
      value = value.strip()
      if len(value) < 3 or len(value) > 240:
        return
      if value.lower().startswith("http"):
        return
      if not is_likely_human_query(value):
        return
      candidates.append(value)

    for req in requests:
      if not isinstance(req, dict):
        continue
      url = req.get("url") or ""
      post_data = req.get("post_data") or ""
      # URLs: look for common q= query params.
      if isinstance(url, str) and "q=" in url:
        try:
          parsed = urlparse(url)
          qs = parse_qs(parsed.query or "")
          q = qs.get("q", [None])[0]
          if isinstance(q, str):
            consider(q)
        except Exception:
          pass
      # JSON-ish payloads: look for "q":"...".
      if isinstance(post_data, str) and post_data:
        m = re.search(r'"q"\\s*:\\s*"([^"]{3,240})"', post_data)
        if m:
          consider(m.group(1))

    # De-dupe in order.
    seen = set()
    deduped: list[str] = []
    for q in candidates:
      key = q.lower()
      if key in seen:
        continue
      seen.add(key)
      deduped.append(q)

    return [SearchQuery(query=q, order_index=i) for i, q in enumerate(deduped)]

  def _extract_response_text_via_copy_button(self) -> str:
    """Attempt to extract the rendered answer via AI Mode's copy UI, when present."""
    if not self.page:
      return ""

    # Best-effort selectors; AI Mode UI changes frequently.
    selectors = [
      "button:has-text('Copy')",
      "button[aria-label*='Copy']",
      "[role='button']:has-text('Copy')",
    ]
    for selector in selectors:
      try:
        btn = self.page.locator(selector).first
        if btn and btn.is_visible(timeout=1000) and btn.is_enabled():
          btn.click(timeout=2000)
          self.page.wait_for_timeout(300)
          text = self.page.evaluate("navigator.clipboard.readText()")
          if isinstance(text, str) and len(text.strip()) > 10:
            return text.strip()
      except Exception:
        continue
    return ""

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
    # Avoid long `networkidle` waits; AI Mode keeps background connections open.
    try:
      self.page.wait_for_timeout(500)
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
    input_locator = self._find_prompt_input_locator()
    if input_locator is None:
      # If the input isn't available, Google is often showing a CAPTCHA/bot-check.
      # Keep the browser open (headed mode) to allow the user to clear it.
      self._maybe_wait_for_challenge_clear(timeout_seconds=600)
      input_locator = self._find_prompt_input_locator(wait_for_textarea=False)
      if input_locator is None:
        raise RuntimeError(
          "Could not find input box on /aimode. If a CAPTCHA is shown, enable "
          "'Show browser window' and complete the challenge, then retry."
        )

    started = time.time()
    input_locator.click()
    # Some AI Mode inputs are contenteditable and do not support `.fill()`.
    try:
      input_locator.fill(prompt)
    except Exception:
      self.page.keyboard.type(prompt)

    # Clear captured data again so query extraction focuses on post-submit traffic.
    self.browser_manager.clear_captured_data()

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
    search_queries = self._extract_search_queries()
    if not search_queries and extract_sources_from_folif_html(folif_html):
      # If we can see sources in the response but couldn't infer a concrete query
      # from requests, use the user's prompt as a best-effort proxy query.
      search_queries = [SearchQuery(query=prompt, order_index=0)]
    copied_text = ""
    try:
      copied_text = self._extract_response_text_via_copy_button()
    except Exception:
      copied_text = ""
    return parse_google_aimode_folif_html(
      folif_html,
      model=model,
      provider="google",
      response_time_ms=response_time_ms,
      search_queries=search_queries,
      response_text_override=copied_text or None,
    )
