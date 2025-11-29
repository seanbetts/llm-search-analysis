# Network Capture Module

This module provides browser automation and network traffic interception capabilities to capture detailed search data that is not available through official provider APIs.

## Status: Phase 2 Complete (ChatGPT Infrastructure)

✅ Database schema updated with network log fields
✅ Base classes and module structure created
✅ UI toggle for mode selection implemented
✅ ChatGPT browser automation with Chrome
✅ Session persistence with storageState API
✅ Automatic login and session restoration
✅ Web search enablement (/search command + menu fallback)
✅ Response text extraction with inline citations
⚠️ Network log parsing not implemented (search metadata extraction pending)
⏳ Claude capture (not started)
⏳ Gemini capture (not started)

## Architecture

```
network_capture/
├── __init__.py              # Module exports
├── base_capturer.py         # Abstract base class for all capturers
├── browser_manager.py       # Browser lifecycle and network interception utilities
├── parser.py                # Network log parsers for different providers
├── chatgpt_capturer.py      # ChatGPT-specific implementation (in progress)
├── claude_capturer.py       # (future)
└── gemini_capturer.py       # (future)
```

## Usage

### Prerequisites

1. Install Playwright with Chrome browser:
   ```bash
   pip install playwright playwright-stealth
   python -m playwright install chrome
   ```

   **Important:** Use Chrome (not Chromium) - Chromium is detected by OpenAI.

2. Configure ChatGPT authentication in `.env`:
   ```bash
   CHATGPT_EMAIL=your_email@example.com
   CHATGPT_PASSWORD=your_password_here
   ```

   **Session Persistence:**
   - Login state saved to `data/chatgpt_session.json` (auto-created, ~190KB)
   - Subsequent runs skip authentication if session valid
   - Delete session file to force fresh login

3. Migrate existing database (if you have one):
   ```bash
   python migrations/add_network_log_fields.py
   ```

### In the UI

1. Navigate to the "Interactive" tab
2. Toggle "Network Logs (Experimental)" mode
3. Submit prompts normally - headless browser runs invisibly in background
4. No difference in UX - just richer data captured!

### Programmatic Usage

```python
from src.network_capture.chatgpt_capturer import ChatGPTCapturer

# Create capturer (optionally specify session file path)
capturer = ChatGPTCapturer()  # Uses default: data/chatgpt_session.json

# Start browser (non-headless for CAPTCHA bypass, uses Chrome)
capturer.start_browser(headless=False)

# Authenticate (auto-restores session if valid, otherwise logs in)
# Requires CHATGPT_EMAIL and CHATGPT_PASSWORD in .env
if capturer.authenticate():
    # Send prompt with web search enabled
    response = capturer.send_prompt(
        prompt="What are the latest AI developments?",
        model="chatgpt-free",
        enable_search=True  # Uses /search command + menu fallback
    )

    # Response includes text and inline citations
    print(f"Response: {response.response_text}")
    print(f"Citations found: {len(response.sources_used)}")

    # Note: Network log parsing for search metadata not yet implemented

# Cleanup
capturer.stop_browser()
```

## Data Captured in Network Log Mode

Beyond what APIs provide, network logs can capture:

### Search Queries
- `internal_ranking_scores`: How model scored each result
- `query_reformulations`: How queries evolved during search

### Sources
- `snippet_text`: Actual text extracted by model
- `internal_score`: Relevance score assigned by model
- `metadata`: Full metadata model saw (titles, descriptions, etc.)

### Citations
- `snippet_used`: Exact snippet used in response
- `citation_confidence`: Model's confidence in citation

## Implementation Status

### Phase 1: Infrastructure ✅
- [x] Database schema updates
- [x] Base classes and abstractions
- [x] Module structure
- [x] UI mode toggle
- [x] Migration script

### Phase 2: ChatGPT Capture ✅
- [x] Chrome browser integration (bypasses detection)
- [x] Session persistence with storageState API
- [x] Automatic login and session restoration
- [x] Login detection (check for chat interface + absence of login buttons)
- [x] UI interaction (prompt submission)
- [x] Web search enablement via /search command
- [x] Fallback menu navigation (Add → More → Web search)
- [x] Search activation detection
- [x] Response text extraction
- [x] Inline citation parsing from response text
- [ ] Network log parsing (search metadata extraction - pending)

### Phase 3: Parsing & Analysis ⏳
- [ ] Complete ChatGPT network log parser implementation
- [ ] Extract search queries from network responses
- [ ] Extract sources with snippets and internal scores
- [ ] Map queries to their corresponding results
- [ ] Validate data accuracy
- [ ] Add error handling for format changes
- [ ] Create comparison views (API vs Network Log)

### Phase 4: Additional Providers ⏳
- [ ] Claude network capture
- [ ] Gemini network capture
- [ ] Cross-provider analysis tools

## Next Steps

To continue development:

1. **Capture real free ChatGPT network logs:**
   - Open https://chatgpt.com (no login)
   - Open browser DevTools → Network tab
   - Submit a test prompt
   - Copy chat ID from URL (if present)
   - Filter network logs for relevant endpoints
   - Analyze response structure (search queries, snippets, etc.)
   - Document JSON format

2. **Update `chatgpt_capturer.py`:**
   - Find actual textarea selector for prompt input
   - Implement prompt submission logic
   - Detect response completion
   - Filter captured network responses for search data
   - Extract the relevant response containing snippets/scores

3. **Update `parser.py`:**
   - Parse actual ChatGPT response format
   - Extract search queries, snippets, internal scores
   - Map to our ProviderResponse data model
   - Handle edge cases (no search performed, etc.)

4. **Test end-to-end:**
   - Toggle network log mode in UI
   - Submit test prompt
   - Verify headless browser captures data correctly
   - Compare with OpenAI API data for same prompt
   - Validate network log fields are populated

## Key Advantages of This Approach

1. **Session Persistence:** Login once, sessions persist across runs (storageState API)
2. **Free tier:** Uses ChatGPT account, no API costs
3. **Dual Search Methods:** /search command (primary) + menu navigation (fallback)
4. **Automatic Login:** Credentials from .env, manual 2FA/CAPTCHA when needed
5. **Detection Bypass:** Chrome browser successfully bypasses OpenAI detection
6. **Rich Data:** Response text + inline citations (network log parsing pending)

## Legal & Ethical Notes

- This module operates in a legal gray area
- Intended for personal research use only
- Users capture traffic from their own accounts
- Requires explicit user consent via UI toggle
- Not for commercial use or scale
- May violate provider Terms of Service

Use responsibly and at your own risk.
