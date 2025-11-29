# LLM Search Analysis - Development Plan

## Project Overview

A comparative analysis tool for evaluating web search capabilities across OpenAI, Google Gemini, and Anthropic Claude models with dual data collection modes: API-based and Network Capture.

## Current Status

### ✅ Fully Implemented

**API-Based Data Collection:**
- ✅ 9 models across 3 providers (OpenAI, Google, Anthropic)
- ✅ Complete provider abstraction layer
- ✅ Three-tab Streamlit interface (Interactive, Batch Analysis, History)
- ✅ SQLite database with full schema
- ✅ Source rank tracking (1-indexed)
- ✅ Multi-model batch comparison
- ✅ CSV export functionality
- ✅ Query history with search/filter
- ✅ Average rank metrics

**Network Capture Infrastructure:**
- ✅ Database schema with `data_source` field
- ✅ Network capture module structure
- ✅ Browser automation with Playwright
- ✅ Response text extraction
- ✅ Non-headless mode (bypasses Cloudflare CAPTCHA)
- ✅ Stealth mode integration
- ✅ Modal dismissal automation
- ✅ UI routing for dual modes

**Network Capture - ChatGPT:**
- ✅ Basic browser automation works
- ✅ Chrome browser successfully bypasses detection
- ✅ Session persistence with storageState API
- ✅ Automatic login and session restoration
- ✅ Prompt submission successful
- ✅ Web search enablement via /search command
- ✅ Fallback menu navigation (Add → More → Web search)
- ✅ Search activation detection
- ✅ Response text extraction with inline citations
- ⚠️ **Known Issue**: ChatGPT free tier search execution unreliable (platform issue, bug filed)

### 📊 Test Results: 52 Passing Tests

All API providers and core functionality verified working.

## Critical Learnings

### 1. Browser Detection (OpenAI)

**Finding:** OpenAI detects Playwright browsers and serves degraded UI without Search functionality.

**Evidence:**
- Safari (normal browser): Shows "Attach/Search/Study" buttons ✓
- Our Playwright + Chromium: Shows only "Add/Voice" buttons ✗
- Even with stealth mode applied, detection succeeds

**Detection Methods Used by OpenAI:**
- Browser fingerprinting (WebGL, Canvas)
- Missing browser APIs (Notifications, Permissions)
- Chrome vs Chromium differences
- Automation signals despite `--disable-blink-features=AutomationControlled`

**Current Mitigation Attempts:**
```python
# Applied but insufficient:
- playwright-stealth library
- Realistic user agent
- Realistic viewport (1920x1080)
- Browser args: --disable-blink-features=AutomationControlled
- Non-headless mode
```

**Status:** ✅ RESOLVED - Chrome browser (channel='chrome') successfully bypasses detection!

**Solution:**
```python
self.browser = self.playwright.chromium.launch(
    headless=False,
    channel='chrome',  # Use Chrome instead of Chromium
    args=[...]
)
```

**Result:** Chrome has different fingerprint from Chromium and is not detected. Search button is now accessible and functional.

### 2. Cloudflare CAPTCHA

**Finding:** Headless mode triggers Cloudflare CAPTCHA blocking.

**Solution:** Use non-headless mode (`headless=False`)

**Implementation:**
```python
browser = playwright.chromium.launch(headless=False)
```

**Result:** ✅ CAPTCHA bypassed successfully when using non-headless mode.

### 3. Stealth Mode Requirements

**Finding:** Must use correct Python environment with playwright-stealth installed.

**Issue Encountered:**
- User's `p` alias points to Homebrew Python (`/opt/homebrew/bin/python3.11`)
- Playwright-stealth installed in pyenv Python (`~/.pyenv/shims/python`)
- Running with wrong Python = no stealth mode applied = failures

**Solution:** Always use: `~/.pyenv/shims/python`

### 4. Search Toggle Behavior

**Finding:** Search button behavior changes based on UI state.

**Initial Hypothesis (Incorrect):** Search button appears after typing prompt.

**Actual Finding:** In automated Chromium browsers, search button never appears - OpenAI serves different UI entirely.

**Screenshots Evidence:**
- Normal browser: "Attach/Search/Study" buttons visible
- Playwright + Chromium: Only "Add/Voice" buttons, no Search option

### 5. Network Interception Setup

**Finding:** Must set up network interception correctly to avoid async/sync bugs.

**Bug Fixed:** browser_manager.py was using `async def` with sync Playwright API, causing hangs.

**Solution:**
```python
# WRONG (caused hangs):
async def handle_response(response):
    body = await response.body()

# CORRECT:
def handle_response(response):
    body = response.body()
```

## Next Steps

### Immediate Priority: Parse Network Responses

**Goal:** Extract search metadata from captured network traffic.

**Completed:**
- ✅ Chrome browser installed
- ✅ Updated chatgpt_capturer.py to use Chrome (`channel='chrome'`)
- ✅ Tested and confirmed Chrome bypasses detection
- ✅ Search functionality working (retrieves current information)
- ✅ Citations visible in responses
- ✅ 66 network responses captured during search interaction

**Next Steps:**
1. Analyze captured network responses to find search metadata
2. Identify which endpoints contain search queries and results
3. Parse search queries from network logs
4. Extract sources/citations with URLs
5. Map queries to their corresponding results
6. Update parser.py to extract this data

**Expected Outcome:** Full search metadata extraction from network logs.

### Alternative Approaches

#### Option 1: Logged-In ChatGPT Account
**Pros:**
- May have different UI/detection rules
- Could have search access
- Plus tier has guaranteed search

**Cons:**
- Requires user authentication
- Session management complexity
- Account risk if ToS violation

#### Option 2: Undetected Libraries
**Libraries to try:**
- undetected-chromedriver
- playwright-undetected
- More aggressive anti-fingerprinting

**Pros:**
- Designed specifically to bypass detection

**Cons:**
- More dependencies
- May still fail against sophisticated detection
- Ongoing cat-and-mouse game

#### Option 3: Accept Limitation
**Document that:**
- Free ChatGPT search not accessible via automation
- Network capture works for response text only
- Search metadata requires manual testing or API mode

## Architecture

### Current Structure

```
llm-search-analysis/
├── app.py                      # Streamlit UI (3 tabs)
├── src/
│   ├── config.py              # Config & API keys
│   ├── database.py            # SQLAlchemy models
│   ├── analyzer.py            # Statistics
│   ├── providers/             # API-based collection
│   │   ├── base_provider.py
│   │   ├── provider_factory.py
│   │   ├── openai_provider.py
│   │   ├── google_provider.py
│   │   └── anthropic_provider.py
│   └── network_capture/       # Browser automation
│       ├── browser_manager.py
│       ├── chatgpt_capturer.py
│       └── parser.py
├── tests/                     # 52 passing tests
├── llm_search_analysis.db     # SQLite database
└── README.md                  # Documentation
```

### Data Flow

```
User Input
    ↓
Mode Selection (API vs Network)
    ↓
┌─────────────┬──────────────────┐
│  API Mode   │  Network Mode    │
├─────────────┼──────────────────┤
│ providers/  │ network_capture/ │
│  - OpenAI   │  - Playwright    │
│  - Google   │  - Stealth       │
│  - Anthropic│  - Interception  │
└─────────────┴──────────────────┘
    ↓
Unified Database (data_source field)
    ↓
Analysis & Display
```

## Technical Decisions

### 1. Database Schema

**Key Fields:**
- `responses.data_source` - 'api' or 'network_log'
- `sources.rank` - 1-indexed position
- `sources.snippet_text` - Network log only
- `sources.internal_score` - Network log only

**Design:** Single schema handles both modes with optional fields for network-specific data.

### 2. Browser Choice

**Previous:** Chromium (detected by OpenAI - degraded UI)
**Current:** Chrome (testing if bypasses detection)
**Reason:** Chrome has different fingerprint than Chromium, may avoid detection

### 3. Stealth Configuration

**Strategy:**
```python
# Launch args
args=[
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--disable-web-security',
    '--no-sandbox'
]

# Realistic fingerprint
viewport={'width': 1920, 'height': 1080}
user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...'

# Stealth library
stealth.apply_stealth_sync(page)
```

### 4. Error Handling

**Current Approach:**
- Try network capture
- On failure, display error
- User can switch to API mode

**Future Enhancement:**
- Automatic fallback to API on network failure
- Retry logic for transient errors

## Future Enhancements

### High Priority

**1. Complete Network Capture**
- [ ] Switch to Chrome browser
- [ ] Test search functionality
- [ ] Parse search metadata from network responses
- [ ] Extract citations and sources from network logs
- [ ] Map search queries to results

**2. Enhanced Analysis**
- [ ] Compare API vs Network data side-by-side
- [ ] Identify what network logs reveal that APIs don't
- [ ] Network-exclusive insights visualization

**3. Multi-Provider Network Capture**
- [ ] Claude network capture
- [ ] Gemini network capture
- [ ] Unified capturer interface

### Medium Priority

**UI Improvements:**
- [ ] Real-time progress for network capture
- [ ] Browser session status indicator
- [ ] Data source badges in results
- [ ] Network log data preview

**Analysis Features:**
- [ ] Snippet content analysis
- [ ] Internal ranking visualization
- [ ] Query reformulation timeline
- [ ] Source overlap analysis (Venn diagrams)

**Performance:**
- [ ] Browser session reuse
- [ ] Parallel network captures
- [ ] Response caching

### Low Priority / Future Ideas

**Advanced Analytics:**
- [ ] Word clouds for search terms
- [ ] Domain network graphs
- [ ] Search pattern clustering
- [ ] Heat maps for usage patterns
- [ ] Time-series trend analysis

**Provider Comparison:**
- [ ] Side-by-side model comparison view
- [ ] Radar charts for metrics
- [ ] Cost comparison
- [ ] Response time benchmarking

**Infrastructure:**
- [ ] PostgreSQL support
- [ ] Docker containerization
- [ ] Cloud deployment
- [ ] User authentication (multi-user)

**Export Options:**
- [ ] JSON export (in addition to CSV)
- [ ] Shareable query links
- [ ] Custom report generation

**Polish:**
- [ ] Dark mode theme
- [ ] Custom prompt templates
- [ ] Saved configurations
- [ ] Browser session management UI

## API Documentation

### OpenAI Responses API
**Endpoint:** `/v1/responses`

**Key Configuration:**
```python
response = client.responses.create(
    model="gpt-5",
    tools=[{"type": "web_search"}],
    include=["web_search_call.action.sources"],  # Critical for sources
    input=prompt
)
```

**Key Fields:**
- `web_search_call.action.query` - Search query
- `web_search_call.action.sources` - All URLs fetched
- `message.content[0].annotations` - Citations used

### Google Gemini
**SDK:** `google-generativeai`

**Key Configuration:**
```python
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    tools=[genai.Tool(google_search=GoogleSearch())]
)
```

**Key Fields:**
- `grounding_metadata.grounding_chunks` - Sources
- `grounding_metadata.search_entry_point` - Queries
- `grounding_metadata.grounding_supports` - Citations

### Anthropic Claude
**SDK:** `anthropic`

**Key Configuration:**
```python
message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    tools=[{"type": "web_search_20250305"}],
    messages=[{"role": "user", "content": prompt}]
)
```

**Key Fields:**
- `server_tool_use` blocks - Search queries
- `web_search_tool_result` blocks - Sources
- Text block `annotations` - Citations

## Known Issues & Limitations

### Current Issues

**1. ChatGPT Free Tier Search Unreliable**
- **Issue:** Web search mode enables successfully, but ChatGPT doesn't always execute searches
- **Impact:** Network capture can activate search, but results inconsistent
- **Status:** Platform issue (bug filed with OpenAI)
- **Workaround:** Use API mode with OpenAI Responses API for reliable search
- **Note:** Our code correctly enables search mode - execution is ChatGPT's responsibility

**2. Network Log Parsing Not Implemented**
- **Issue:** Search metadata extraction from network logs not yet implemented
- **Impact:** Network mode captures response text and citations only
- **Status:** Infrastructure complete, parsing implementation pending
- **Next Step:** Analyze captured network responses to extract search queries and sources

**3. Assistant-Only Links**
- **Issue:** Assistant may include links in the response that are not present in the captured search results (SSE)
- **Impact:** Such links will not appear in "Search Queries & Sources" or "Sources Used"
- **Status:** "Extra Links" metric now tracks these links separately; raw SSE is stored in `raw_response_json` for inspection

### Resolved Issues

**✅ Browser Detection (Chromium vs Chrome)**
- **Solution:** Use Chrome browser with `channel='chrome'` parameter
- **Impact:** Search toggle accessible, web search functional

**✅ Session Persistence File Bloat**
- **Solution:** Switch from persistent profile (696 files) to storageState API (1 file)
- **Impact:** 99.3% reduction in storage (29MB → 190KB)

**✅ Login Detection False Positives**
- **Solution:** Check for both "Log in" and "Sign up" buttons
- **Impact:** Accurate logged-in state detection

**✅ Web Search Toggle Not Working**
- **Solution:** Updated selectors for new ChatGPT UI (Add → More → Web search)
- **Impact:** Menu-based search toggle functional

**✅ /search Command Not Activating**
- **Solution:** Use keyboard simulation (`type()` + `press("Space")`) instead of `fill()`
- **Impact:** Primary search enablement method working

**✅ Search Activation Not Detected**
- **Solution:** Look for "Web search" text indicators (15+ matches when active)
- **Impact:** Reliable detection of search mode activation

**✅ Cloudflare CAPTCHA**
- **Solution:** Non-headless mode

**✅ Async/Sync Bug**
- **Solution:** Use sync functions with sync Playwright

**✅ Cookie Banners**
- **Solution:** Automated dismissal

**✅ Textarea Not Found**
- **Solution:** Selector `#prompt-textarea`

**✅ Wrong Python Environment**
- **Solution:** Use `~/.pyenv/shims/python`

## Development Workflow

### Testing Network Capture

**Run interactive test:**
```bash
~/.pyenv/shims/python -c "
from src.network_capture.chatgpt_capturer import ChatGPTCapturer
capturer = ChatGPTCapturer()
capturer.start_browser(headless=False)
capturer.authenticate()
response = capturer.send_prompt('What happened in the news today?', 'chatgpt-free')
print(f'Response: {response.response_text[:300]}...')
capturer.stop_browser()
"
```

**Check browser fingerprint:**
```bash
~/.pyenv/shims/python open_browser_for_testing.py
# Manually check what UI appears
```

### Running Tests

**Full test suite:**
```bash
pytest tests/ -v
```

**Verify providers:**
```bash
python tests/verify_providers.py
```

### Database Migrations

**Current schema version:** Includes data_source and network log fields

**Future migrations:** Create in `migrations/` directory

## Success Metrics

### Phase 1: ✅ Complete
- Multi-provider API integration
- Full UI with 3 tabs
- Database with rank tracking
- Batch analysis
- Query history

### Phase 2: 🔄 In Progress
- Network capture infrastructure
- Browser automation
- Response extraction
- **BLOCKED:** Search toggle access

### Phase 3: Not Started
- Network log parsing
- Search metadata extraction
- API vs Network comparison
- Extended to all providers

## Risk Mitigation

### Technical Risks

**Browser Detection:**
- **Mitigation:** Multiple browser options (Chrome, undetected-chromedriver)
- **Fallback:** Document limitation, use API mode

**Network Format Changes:**
- **Mitigation:** Version tracking, robust parsing
- **Fallback:** Graceful degradation, error logging

**Rate Limiting:**
- **Mitigation:** Throttling, delays between requests
- **Fallback:** Queue system, retry logic

### Compliance Risks

**Terms of Service:**
- **Mitigation:** Clear experimental labeling
- **Mitigation:** User accepts responsibility
- **Mitigation:** Research/personal use only
- **Fallback:** Remove network capture if requested

## Resources

### Documentation
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Google Gemini API Docs](https://ai.google.dev/docs)
- [Anthropic API Docs](https://docs.anthropic.com/)
- [Playwright Docs](https://playwright.dev/python/)
- [Playwright Stealth](https://github.com/AtuboDad/playwright_stealth)

### Key Dependencies
```
streamlit>=1.30.0
openai>=1.12.0
google-generativeai>=0.3.0
anthropic>=0.18.0
sqlalchemy>=2.0.25
pandas>=2.1.4
playwright>=1.40.0
playwright-stealth>=2.0.0
```

## Timeline Estimate

### Immediate (Now)
- [x] Switch to Chrome browser
- [x] Test search toggle access with Chrome - ✅ SUCCESS
- [x] Document findings - Chrome bypasses detection
- [x] Decision: proceed with network log parsing

### Short Term (1-2 Weeks)
- [ ] If Chrome works: Parse network responses
- [ ] Extract search metadata
- [ ] Map queries to sources
- [ ] Test with various prompts

### Medium Term (1 Month)
- [ ] Extend to Claude/Gemini
- [ ] Comparison analysis views
- [ ] Enhanced UI for network mode
- [ ] Performance optimization

### Long Term (Future)
- [ ] Advanced analytics
- [ ] Multi-provider comparison
- [ ] Production deployment
- [ ] User authentication

## Open Questions

1. **Chrome vs Chromium:** Will Chrome bypass detection?
2. **Logged-in accounts:** Worth the complexity?
3. **Rate limiting:** What are the actual limits for network mode?
4. **Multi-tab support:** Can we capture multiple prompts in parallel?
5. **Session persistence:** How long to keep browser alive?
6. **Privacy:** What safeguards for sensitive data?

## Decision Log

### 2024: Use Non-Headless Mode
**Decision:** Run browsers with `headless=False`
**Reason:** Headless mode triggers Cloudflare CAPTCHA
**Trade-off:** Visible browser window vs. reliability

### 2024: Dual Mode Architecture
**Decision:** Support both API and Network modes
**Reason:** API reliable but limited, Network powerful but fragile
**Trade-off:** Complexity vs. flexibility

### 2024: SQLite Database
**Decision:** Use SQLite for MVP
**Reason:** Simple, sufficient for single-user
**Future:** Migrate to PostgreSQL for production

### 2024-11-28: Chrome Browser Switch
**Decision:** Switched from Chromium to Chrome
**Reason:** Chrome has different browser fingerprint from Chromium
**Result:** ✅ SUCCESS - Chrome bypasses OpenAI detection completely
**Impact:** Search button accessible, web search functional, current news retrieved
**Implementation:** `channel='chrome'` parameter in `playwright.chromium.launch()`

### 2024-11-29: Session Persistence with storageState API
**Decision:** Use Playwright's storageState API instead of persistent Chrome profiles
**Reason:** Persistent profiles created 696 files (29MB) - excessive overhead
**Result:** ✅ SUCCESS - Single JSON file (190KB, 99.3% reduction)
**Impact:** Fast session persistence, automatic login/restore, no file bloat
**Implementation:** `context.storage_state(path=...)` to save, `new_context(storage_state=...)` to restore
**Trade-off:** Requires storing session file vs. cleaner but heavier profile approach

### 2024-11-29: /search Command as Primary Search Method
**Decision:** Use `/search` slash command as primary method, menu navigation as fallback
**Reason:** ChatGPT UI changed - new menu structure (Add → More → Web search) more fragile
**Result:** ✅ SUCCESS - Slash command more reliable than menu navigation
**Impact:** Faster search enablement, fewer UI interaction failures
**Implementation:** Type `/search ` (with space) in textarea, detect activation, fallback to menu if needed
**Trade-off:** Depends on ChatGPT supporting slash command vs. pure UI automation
