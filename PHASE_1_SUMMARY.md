# Phase 1 Complete: Network Log Integration Infrastructure

## What We Built

Phase 1 establishes the complete infrastructure for dual-mode data collection, allowing the app to capture data either through official APIs (current) or browser network logs (future).

### Key Accomplishment

You can now toggle between two data collection modes in the UI, with all backend infrastructure ready to support network log capture once the implementation is completed.

## Changes Made

### 1. Database Schema Updates

**New Fields:**
- `responses.data_source` - Tracks whether data came from 'api' or 'network_log'
- `search_queries.internal_ranking_scores` - Model's internal ranking (network log only)
- `search_queries.query_reformulations` - Query evolution steps (network log only)
- `sources.snippet_text` - Actual snippet extracted by model (network log only)
- `sources.internal_score` - Relevance score (network log only)
- `sources.metadata_json` - Full metadata from logs (network log only)
- `sources_used.snippet_used` - Exact snippet cited (network log only)
- `sources_used.citation_confidence` - Citation confidence score (network log only)

**Migration:**
- Created `migrations/add_network_log_fields.py` to update existing databases
- Run with: `python migrations/add_network_log_fields.py`

### 2. Data Model Extensions

Updated base provider dataclasses to support optional network log fields:

```python
@dataclass
class SearchQuery:
    query: str
    sources: List['Source'] = None
    timestamp: Optional[str] = None
    # New network log fields
    internal_ranking_scores: Optional[Dict] = None
    query_reformulations: Optional[List[str]] = None

@dataclass
class Source:
    url: str
    title: Optional[str] = None
    domain: Optional[str] = None
    rank: Optional[int] = None
    # New network log fields
    snippet_text: Optional[str] = None
    internal_score: Optional[float] = None
    metadata: Optional[Dict] = None

@dataclass
class Citation:
    url: str
    title: Optional[str] = None
    text_snippet: Optional[str] = None
    rank: Optional[int] = None
    # New network log fields
    snippet_used: Optional[str] = None
    citation_confidence: Optional[float] = None
```

### 3. Network Capture Module

Created complete module structure:

```
src/network_capture/
├── __init__.py              # Module exports
├── base_capturer.py         # Abstract base class (complete)
├── browser_manager.py       # Browser utilities (complete)
├── parser.py                # Network log parsers (placeholders)
├── chatgpt_capturer.py      # ChatGPT implementation (skeleton)
└── README.md                # Documentation
```

**BaseCapturer Interface:**
- `start_browser()` - Launch browser instance
- `stop_browser()` - Cleanup
- `authenticate()` - Handle user login
- `send_prompt()` - Capture network traffic
- `get_provider_name()` - Provider identifier
- `get_supported_models()` - Model list

### 4. UI Enhancements

**Mode Toggle:**
- Radio buttons to switch between "API (Recommended)" and "Network Logs (Experimental)"
- Warning message explaining experimental nature
- Info notice that implementation is in progress

**Data Source Indicator:**
- Responses captured from network logs show "📡 This response was captured from network logs"
- Allows distinguishing data sources in analysis

### 5. Dependencies

Added to requirements.txt:
- `playwright>=1.40.0` - Browser automation framework

Install with:
```bash
pip install playwright
playwright install chromium
```

## Current State

### What Works ✅
- Database schema supports both data sources
- UI toggle switches between modes
- Data models accommodate network log fields
- Module structure is complete
- Migration script ready

### What's Not Implemented 🚧
- Actual network log capture (ChatGPT, Claude, Gemini)
- Network response parsing
- Browser automation logic
- Real prompt submission via browser

### Why This Matters

This infrastructure enables **comparative analysis**:
1. Send same prompt via API and Network Log
2. Compare what data each method captures
3. Identify gaps in API data
4. Quantify value of network log insights

## Architecture Decisions

### 1. Unified Data Model
Both API and network log data flow through the same `ProviderResponse` format, ensuring consistent analysis tools work across both sources.

### 2. Optional Fields
Network log fields are optional in dataclasses, so API providers don't break. Uses `getattr(obj, 'field', None)` pattern.

### 3. Database Tracking
`data_source` column allows filtering and comparison queries:
```sql
SELECT * FROM responses WHERE data_source = 'network_log';
```

### 4. Abstract Base Class
`BaseCapturer` mirrors `BaseProvider` interface, allowing polymorphic usage:
```python
# Future code will work with both
capturer = ChatGPTCapturer()  # or OpenAIProvider()
response = capturer.send_prompt(prompt, model)
```

## Next Steps (Phase 2)

To make network log capture functional:

### Step 1: Analyze Real Traffic
1. Open ChatGPT in browser with DevTools
2. Submit a prompt
3. Copy chat ID from URL
4. Filter network logs for chat ID responses
5. Document actual response structure

### Step 2: Implement Capture
1. Update `chatgpt_capturer.py` with real UI selectors
2. Implement prompt submission logic
3. Add response completion detection
4. Extract relevant network responses

### Step 3: Implement Parsing
1. Update `parser.py` with actual response format
2. Extract search queries, snippets, rankings
3. Map to our data model
4. Validate accuracy

### Step 4: Test End-to-End
1. Toggle network log mode in UI
2. Submit test prompt
3. Verify data captured correctly
4. Compare with API data

## Testing the Infrastructure

You can verify Phase 1 is working:

1. **Start the app:**
   ```bash
   streamlit run app.py
   ```

2. **Toggle to Network Log mode:**
   - Should see warning message
   - Should see "not yet implemented" notice

3. **Check database schema:**
   ```bash
   sqlite3 data/llm_search.db ".schema responses"
   ```
   Should see `data_source` column

4. **Verify module imports:**
   ```python
   from src.network_capture import BaseCapturer
   from src.network_capture.chatgpt_capturer import ChatGPTCapturer
   ```

## Files Changed

```
Modified:
- src/database.py                   (schema + save logic)
- src/providers/base_provider.py    (dataclass fields)
- app.py                             (UI toggle + indicator)
- requirements.txt                   (playwright dependency)

Created:
- NETWORK_LOG_INTEGRATION.md        (full plan)
- PHASE_1_SUMMARY.md                (this file)
- migrations/add_network_log_fields.py
- src/network_capture/__init__.py
- src/network_capture/base_capturer.py
- src/network_capture/browser_manager.py
- src/network_capture/parser.py
- src/network_capture/chatgpt_capturer.py
- src/network_capture/README.md
```

## Commit

Phase 1 is committed to `network-log-integration` branch:
- Commit: 34eb34f
- Message: "Phase 1: Add network log integration infrastructure"

## Risks & Considerations

### Legal Gray Area
- Network log capture may violate provider ToS
- Intended for personal research only
- User explicitly opts in via toggle
- Clear warnings in UI

### Maintenance Burden
- Provider UIs change frequently
- Network formats can change without notice
- Requires ongoing updates

### Value Proposition
This infrastructure is justified because:
1. Network logs reveal data unavailable in APIs (snippets, scores, reformulations)
2. Enables comparative analysis (API vs reality)
3. Supports the LinkedIn post use case (understanding search behavior)
4. Provides ground truth for prompt optimization research

## Design Decisions Made

### Using Free ChatGPT with Headless Browser

**Decision:** Use free ChatGPT (no login) with headless Playwright browser.

**Rationale:**
- **Seamless UX:** User toggles mode and submits - no visible browser, no extra steps
- **No authentication:** Free ChatGPT requires no login, eliminating session management
- **Identical experience:** Only difference is "📡" indicator showing richer data captured
- **Simpler implementation:** No browser window management, cookies, or auth flows
- **Free tier:** No API costs for network log mode

**Implementation approach:**
1. Start headless browser invisibly in background
2. Navigate to chatgpt.com (no auth needed)
3. Submit prompt programmatically
4. Capture network traffic with search data
5. Parse and return response
6. Clean up browser

This provides the best of both worlds: rich network log data with API-like UX simplicity.

## Questions for Next Session

Before starting Phase 2 implementation:

1. **Which provider to prioritize after ChatGPT?**
   - Claude (if free tier available)
   - Gemini (if free tier available)
   - Or continue with API-only for paid tiers

2. **Error handling strategy?**
   - Fail gracefully and fall back to API mode
   - Retry logic for transient network failures
   - Clear error messages for user

3. **Browser lifecycle:**
   - Start/stop browser per request (safer, slower)
   - Keep browser alive across requests (faster, more complex)
   - Connection pooling for concurrent requests

Ready to proceed to Phase 2 when you are!
