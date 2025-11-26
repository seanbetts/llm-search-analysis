# Network Capture Module

This module provides browser automation and network traffic interception capabilities to capture detailed search data that is not available through official provider APIs.

## Status: Phase 1 Complete (Infrastructure)

✅ Database schema updated with network log fields
✅ Base classes and module structure created
✅ UI toggle for mode selection implemented
🚧 ChatGPT capture implementation (placeholder - needs real network log analysis)
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

1. Install Playwright:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. Migrate existing database (if you have one):
   ```bash
   python migrations/add_network_log_fields.py
   ```

### In the UI

1. Navigate to the "Interactive" tab
2. Toggle "Network Logs (Experimental)" mode
3. Submit prompts normally - headless browser runs invisibly in background
4. No difference in UX - just richer data captured!

### Programmatic Usage (Future)

```python
from src.network_capture.chatgpt_capturer import ChatGPTCapturer

# Create capturer
capturer = ChatGPTCapturer()

# Start browser (headless by default - invisible to user)
capturer.start_browser()

# Navigate to free ChatGPT (no auth needed)
if capturer.authenticate():
    # Send prompt and capture network logs
    response = capturer.send_prompt(
        prompt="What are the latest AI developments?",
        model="gpt-5.1"  # Free ChatGPT model
    )

    # Response includes network log data
    print(f"Search queries: {len(response.search_queries)}")
    for source in response.sources:
        print(f"Snippet: {source.snippet_text}")  # Only in network logs!

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

### Phase 2: ChatGPT Capture 🚧
- [ ] Analyze actual ChatGPT network traffic
- [ ] Identify relevant API endpoints
- [ ] Implement UI interaction (prompt submission)
- [ ] Extract chat ID from URL
- [ ] Parse network responses
- [ ] Map to standardized format
- [ ] Test with real prompts

### Phase 3: Parsing & Analysis ⏳
- [ ] Complete ChatGPT parser implementation
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

1. **Seamless UX:** No visible browser, no manual login, just works
2. **Free tier:** Uses free ChatGPT, no API costs
3. **Headless:** Runs in background, user sees no difference
4. **No auth complexity:** No cookies, sessions, or login flows
5. **Faster:** No waiting for user authentication

## Legal & Ethical Notes

- This module operates in a legal gray area
- Intended for personal research use only
- Users capture traffic from their own accounts
- Requires explicit user consent via UI toggle
- Not for commercial use or scale
- May violate provider Terms of Service

Use responsibly and at your own risk.
