# Network Log Integration Plan

## Overview
Hybrid approach allowing users to toggle between API-based analysis and network log interception for deeper insights.

## Architecture

### Data Collection Modes

#### Mode 1: API-Based (Current - Default)
- Uses official provider APIs
- Fully compliant with ToS
- Limited to what APIs expose
- `data_source = 'api'` in database

#### Mode 2: Network Log Analysis (Optional - Toggle On)
- Intercepts browser network traffic
- Captures internal API responses
- Access to full search data (queries, snippets, rankings)
- `data_source = 'network_log'` in database

### Technical Approach

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit App                      │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │   Toggle: [ API Mode | Network Log Mode ]   │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  API Mode          │        Network Log Mode       │
│  ─────────────────────────────────────────────────  │
│                    │                                │
│  Uses              │        Uses                    │
│  providers/        │        network_capture/        │
│  ├─ openai_        │        ├─ browser_automation  │
│  │  provider.py    │        ├─ traffic_interceptor │
│  ├─ google_        │        └─ log_parser          │
│  │  provider.py    │                                │
│  └─ anthropic_     │                                │
│     provider.py    │                                │
│                    │                                │
│         └──────────┴────────────┘                   │
│                    │                                │
│              Unified Storage                        │
│              (database.py)                          │
└─────────────────────────────────────────────────────┘
```

## Database Schema Updates

### Add `data_source` tracking

```python
class Response(Base):
    """Model response."""
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("prompts.id"))
    response_text = Column(Text)
    response_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    raw_response_json = Column(JSON)
    data_source = Column(String(20))  # NEW: 'api' or 'network_log'
```

### Extended data fields (network log only)

```python
class SearchQuery(Base):
    """Search query made during response generation."""
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id"))
    search_query = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Network log exclusive fields
    internal_ranking_scores = Column(JSON)  # If available from logs
    query_reformulations = Column(JSON)     # Query evolution steps

class SourceModel(Base):
    """Source/URL fetched during search."""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    search_query_id = Column(Integer, ForeignKey("search_queries.id"))
    url = Column(Text, nullable=False)
    title = Column(Text)
    domain = Column(String(255))
    rank = Column(Integer)

    # Network log exclusive fields
    snippet_text = Column(Text)              # Actual snippet extracted
    internal_score = Column(Float)           # If available from logs
    metadata_json = Column(JSON)             # Full metadata from logs

class SourceUsed(Base):
    """Source actually used/cited in the response."""
    __tablename__ = "sources_used"

    id = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id"))
    url = Column(Text, nullable=False)
    title = Column(Text)
    rank = Column(Integer)

    # Network log exclusive fields
    snippet_used = Column(Text)              # Exact snippet cited
    citation_confidence = Column(Float)      # If available from logs
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Set up infrastructure for dual-mode operation

- [ ] Add `data_source` column to database
- [ ] Update database.py to handle optional network log fields
- [ ] Create network_capture/ module structure
- [ ] Add mode toggle to UI

**Files to create:**
```
src/network_capture/
    __init__.py
    base_capturer.py          # Abstract class
    chatgpt_capturer.py       # ChatGPT network interception
    claude_capturer.py        # Claude network interception
    gemini_capturer.py        # Gemini network interception
```

### Phase 2: ChatGPT Network Capture (Week 2)
**Goal:** Implement network log capture for ChatGPT as proof-of-concept

**Approach Options:**

#### Option A: Selenium + Browser DevTools Protocol
```python
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# Enable network logging
capabilities = DesiredCapabilities.CHROME
capabilities['goog:loggingPrefs'] = {'performance': 'ALL'}

driver = webdriver.Chrome(desired_capabilities=capabilities)
driver.get('https://chatgpt.com')

# Capture network logs
logs = driver.get_log('performance')
```

#### Option B: Playwright (Recommended)
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context()

    # Intercept network traffic
    page = context.new_page()

    page.on("response", lambda response: handle_response(response))
    page.goto('https://chatgpt.com')
```

**Key Implementation:**
- [ ] Launch browser instance
- [ ] Handle authentication (user logs in manually or via stored session)
- [ ] Submit prompt
- [ ] Intercept network responses
- [ ] Parse chat ID from URL
- [ ] Filter for relevant network calls
- [ ] Extract search_queries, snippets, metadata
- [ ] Parse into standardized format
- [ ] Save to database with `data_source='network_log'`

### Phase 3: Data Parser (Week 2-3)
**Goal:** Parse network log responses into our data model

```python
class NetworkLogParser:
    """Parse provider network logs into standardized format."""

    def parse_chatgpt_log(self, network_response: dict) -> ProviderResponse:
        """
        Parse ChatGPT network log response.

        Extracts:
        - search_queries: Query fanouts
        - snippets: Content extracted from pages
        - metadata: Title tags, meta descriptions
        - ranking_scores: Internal relevance scores (if available)
        """
        pass

    def parse_claude_log(self, network_response: dict) -> ProviderResponse:
        """Parse Claude network log response."""
        pass

    def parse_gemini_log(self, network_response: dict) -> ProviderResponse:
        """Parse Gemini network log response."""
        pass
```

### Phase 4: UI Integration (Week 3)
**Goal:** Seamless mode switching in Streamlit

```python
# In app.py

# Mode selection
mode = st.radio(
    "Data Collection Mode",
    ["API (Recommended)", "Network Logs (Experimental)"],
    help="API mode uses official APIs. Network Log mode captures browser traffic for deeper insights."
)

if mode == "Network Logs (Experimental)":
    st.warning(
        "⚠️ Network Log mode operates in a legal gray area. "
        "Use at your own discretion. This mode launches a browser and "
        "intercepts traffic from your own account."
    )

    # Browser session management
    if st.button("Start Browser Session"):
        # Launch browser, user logs in
        pass

    # Status indicator
    if browser_session_active:
        st.success("✓ Browser session active")
```

### Phase 5: Analysis & Comparison (Week 4)
**Goal:** Compare insights between API and Network Log data

**New Analysis Views:**

1. **Data Source Comparison**
   - Same prompt sent via both methods
   - Side-by-side comparison of captured data
   - Highlight what network logs reveal that APIs don't

2. **Network Log Exclusive Insights**
   - Snippet analysis view
   - Internal ranking visualization
   - Query reformulation timeline

3. **Dataset Statistics**
   - X interactions via API
   - Y interactions via network logs
   - Coverage comparison

## Example: ChatGPT Network Log Capture

### Step-by-step user flow:

1. User toggles "Network Log Mode"
2. App launches Chrome browser
3. User navigates to ChatGPT and logs in manually
4. User returns to Streamlit app and enters prompt
5. App submits prompt to ChatGPT via browser automation
6. App intercepts network response containing:
   ```json
   {
     "search_queries": ["query 1", "query 2"],
     "results": [
       {
         "url": "...",
         "title": "...",
         "snippet": "...",
         "rank": 1,
         "score": 0.95
       }
     ]
   }
   ```
7. App parses response and saves with `data_source='network_log'`
8. UI displays results with indicator: "📡 Network Log Data"

## Implementation Considerations

### Authentication Management
- **Option 1:** User logs in manually in browser each session
- **Option 2:** Save browser session cookies (more convenient, security concerns)
- **Option 3:** User provides session tokens (technical, fragile)

**Recommendation:** Start with Option 1 (manual login)

### Browser Management
- Keep browser open for entire session
- Reuse same tab for multiple prompts
- Clean shutdown on app exit
- Handle browser crashes gracefully

### Rate Limiting
- Network log mode is slower (browser automation overhead)
- Respect provider rate limits
- Add delays between requests

### Error Handling
- Network log parsing can fail if format changes
- Fallback to API mode on errors
- Log parsing failures for debugging

## Data Analysis Opportunities

Once we have both data sources, we can answer:

1. **What does API data miss?**
   - Compare snippet content available in logs vs missing in API
   - Identify ranking signals only visible in logs
   - Find query reformulations not exposed in API

2. **How do internal scores correlate with citations?**
   - Do high-scored sources always get cited?
   - What's the score threshold for citation?

3. **What content gets extracted?**
   - Pattern analysis of snippet characteristics
   - Content format preferences
   - Length and structure of extracted text

4. **Query evolution**
   - How do models reformulate queries?
   - What transformations are most common?
   - Difference in strategies across providers

## File Structure

```
src/
├── providers/              # API-based (existing)
│   ├── base_provider.py
│   ├── openai_provider.py
│   ├── google_provider.py
│   └── anthropic_provider.py
│
├── network_capture/        # Network log-based (NEW)
│   ├── __init__.py
│   ├── base_capturer.py
│   ├── chatgpt_capturer.py
│   ├── claude_capturer.py
│   ├── gemini_capturer.py
│   ├── parser.py
│   └── browser_manager.py
│
├── database.py             # Updated with data_source tracking
├── config.py
└── analysis/               # NEW: Comparison tools
    ├── __init__.py
    ├── data_source_comparator.py
    └── network_log_analyzer.py
```

## Dependencies to Add

```
# requirements.txt additions
playwright==1.40.0
selenium==4.15.0  # Alternative to Playwright
```

## Migration Script

```sql
-- Add data_source column to existing tables
ALTER TABLE responses ADD COLUMN data_source VARCHAR(20) DEFAULT 'api';

-- Add network log exclusive columns
ALTER TABLE sources ADD COLUMN snippet_text TEXT;
ALTER TABLE sources ADD COLUMN internal_score FLOAT;
ALTER TABLE sources ADD COLUMN metadata_json JSON;

ALTER TABLE sources_used ADD COLUMN snippet_used TEXT;
ALTER TABLE sources_used ADD COLUMN citation_confidence FLOAT;

ALTER TABLE search_queries ADD COLUMN internal_ranking_scores JSON;
ALTER TABLE search_queries ADD COLUMN query_reformulations JSON;

-- Create index for filtering by data source
CREATE INDEX idx_data_source ON responses(data_source);
```

## Success Metrics

After implementation, we should be able to:

1. ✅ Toggle between API and Network Log modes
2. ✅ Capture complete search data from ChatGPT network logs
3. ✅ Store both data types in same database with clear tagging
4. ✅ Compare insights from same prompt across both methods
5. ✅ Identify what additional insights network logs provide
6. ✅ Build analysis only possible with network log data

## Open Questions

1. **Browser persistence:** Keep browser open between prompts or restart each time?
2. **Multi-provider sessions:** Support multiple providers simultaneously in network log mode?
3. **Export:** Allow export of network log data for external analysis?
4. **Privacy:** What safeguards for sensitive prompts/responses?

## Timeline

- **Week 1:** Database schema + infrastructure
- **Week 2:** ChatGPT network capture (proof of concept)
- **Week 3:** UI integration + session management
- **Week 4:** Analysis tools + comparison views
- **Future:** Extend to Claude, Gemini

## Risk Mitigation

**ToS Risks:**
- Clearly label as experimental
- User accepts responsibility
- Document it's for research/personal use
- Don't distribute at scale

**Technical Risks:**
- Network log format changes → Parser needs updates
- Browser automation fragile → Graceful fallbacks
- Authentication issues → Manual login option

**Data Quality Risks:**
- Parsing errors → Validation + error logging
- Incomplete captures → Mark as such in database
- Rate limiting → Throttling + retry logic
