# LLM Search Analysis: Comprehensive Findings & Learnings

## Executive Summary

This document captures everything we've learned from building a comparative analysis tool for evaluating web search capabilities across OpenAI, Google Gemini, and Anthropic Claude models. It includes both API-based and network capture findings, architectural decisions, provider quirks, and key insights about how LLMs use web search.

**Last Updated:** 2024-12-01

---

## Table of Contents

1. [Data Collection Methods](#data-collection-methods)
2. [Provider Comparisons](#provider-comparisons)
3. [Citation Behavior Insights](#citation-behavior-insights)
4. [Network Log Findings](#network-log-findings)
5. [Browser Automation Learnings](#browser-automation-learnings)
6. [Architecture Decisions](#architecture-decisions)
7. [Metrics & Calculations](#metrics--calculations)
8. [Key Limitations](#key-limitations)
9. [Future Research Questions](#future-research-questions)

---

## Data Collection Methods

### API Mode (Structured Data)

**Providers Supported:**
- OpenAI (Responses API with web_search tool)
- Google Gemini (Search Grounding)
- Anthropic Claude (web_search_20250305 tool)

**Advantages:**
- Structured, reliable data
- Full query-to-source mapping
- Official API support
- No detection concerns

**Limitations:**
- Limited to what API exposes
- No internal ranking scores
- No query reformulation visibility
- No snippet or published-date metadata (all APIs tested omit real excerpts; UI must display “N/A”)

### Network Capture Mode (Browser Automation)

**Providers Supported:**
- ChatGPT (Free) via Chrome browser automation

**Advantages:**
- Internal ranking scores visible
- Query reformulations captured
- Actual search-result snippets and published dates captured (e.g., Brave/ChatGPT network payloads)
- Citation confidence scores
- Deeper insight into model behavior

**Limitations:**
- Only ChatGPT currently
- Requires Chrome browser
- Browser detection challenges
- Query-to-source mapping unreliable (see [Network Log Findings](#network-log-findings))

---

## Provider Comparisons

### OpenAI (API Mode)

**Model:** gpt-5.1, gpt-5-mini, gpt-5-nano

**Search Behavior:**
- Uses `web_search` tool via Responses API
- Returns search queries executed
- Provides full source list with URLs and titles
- Citations clearly linked to search results via annotations
- Rank information: Position in search results (1-indexed)

**Data Quality:**
- ✅ Query-to-source mapping: Clear
- ✅ Citation tracking: Excellent
- ✅ Rank information: Available
- ⚠️ Internal scores: Not available (API mode)

**Quirks:**
- Sometimes cites from training data even when search is enabled
- Citations use `[N]` format in response text

### Google Gemini (API Mode)

**Model:** gemini-2.5-flash, gemini-2.5-flash-lite, gemini-3-pro-preview

**Search Behavior:**
- Uses Search Grounding feature
- Sources in `grounding_metadata.grounding_chunks`
- Citations in `grounding_metadata.grounding_supports`
- Queries visible in `grounding_metadata.search_entry_point`

**Data Quality:**
- ✅ Query-to-source mapping: Available
- ⚠️ Citation tracking: **Cannot distinguish sources used from sources found**
- ❌ Rank information: Not provided by API
- ❌ Internal scores: Not available

**Quirks:**
- **Critical Limitation:** Google's API doesn't separate "sources found" from "sources used"
- All sources are treated as potentially used
- Cannot calculate meaningful "sources used" metric
- No rank information makes citation preference analysis impossible

**Display Note:** Sources Used shows 0 for Google with explanation that API doesn't provide this data

### Anthropic Claude (API Mode)

**Model:** claude-sonnet-4-5, claude-haiku-4-5, claude-opus-4-1

**Search Behavior:**
- Uses native `web_search_20250305` tool (powered by Brave Search)
- Server-side tool execution
- Search queries in `server_tool_use` blocks
- Results in `web_search_tool_result` blocks
- Citations in text block `annotations`

**Data Quality:**
- ✅ Query-to-source mapping: Excellent
- ✅ Citation tracking: Very good
- ✅ Rank information: Available (1-indexed)
- ❌ Internal scores: Not available

**Quirks:**
- Uses Brave Search under the hood
- Sometimes performs multiple searches per query
- Very detailed source information
- Citations use `[†source]` format

### ChatGPT (Network Capture Mode)

**Model:** chatgpt-free

**Search Behavior:**
- Browser automation captures network traffic
- Search queries in SSE metadata
- Results in `search_result_groups`
- Citations extracted from markdown references

**Data Quality:**
- ❌ Query-to-source mapping: **Not available** (see [Network Log Findings](#network-log-findings))
- ✅ Citation tracking: Good (via URL matching)
- ✅ Rank information: Available from search results
- ✅ Internal scores: **Captured** (network logs only)
- ✅ Query reformulations: **Captured** (network logs only)
- ✅ Snippet text: **Available** (network logs only)

**Quirks:**
- Free tier search execution unreliable (platform issue)
- Hybrid approach: Combines search + training data
- Many citations come from training data ("Extra Links")
- Network logs don't map queries to sources (architectural limitation)

---

## Citation Behavior Insights

### Two Types of Citations

Through extensive testing, we discovered that LLMs cite URLs from **two distinct sources**:

1. **Search Results** (Sources Used)
   - URLs the model found via web search
   - Have rank numbers (position in search results)
   - Counted as "Sources Used"
   - Used for Average Rank calculation

2. **Training Data** (Extra Links)
   - URLs the model knows from pre-training
   - No rank numbers (weren't in search results)
   - Counted as "Extra Links"
   - Indicates model used existing knowledge

### Key Finding: Hybrid Citation Behavior

**Discovery:** Even when web search is enabled, models often cite from both sources in a single response.

**Example from ChatGPT:**
- Total Citations: 10
- Sources Used (from search): 3 (ranks 3, 4, 10)
- Extra Links (from training): 7
- Average Rank: 5.7 (calculated from 3 sources used)

**Implications:**
- Models don't exclusively rely on search
- Pre-existing knowledge supplements search results
- Some models prefer training data over fresher search results
- "Extra Links" metric reveals this behavior

### Rank Preference Patterns

**Finding:** Models don't always prefer top-ranked sources

**ChatGPT Example:**
- Cited sources at ranks: 3, 4, 10
- Skipped ranks 1, 2
- Average rank: 5.7

**Interpretation:**
- Content quality matters more than rank
- Models evaluate relevance beyond search engine ranking
- Lower average rank ≠ better response necessarily

---

## Network Log Findings

### Critical Discovery: No Query-to-Source Mapping

**What We Learned:** ChatGPT's network logs do **NOT** provide reliable mapping between search queries and their results.

#### Evidence

1. **Both queries appear simultaneously**
   - Queries listed together in one metadata block
   - No temporal separation or ordering
   - Cannot determine which query was executed first

2. **Sources added to non-sequential group indices**
   - Groups created at indices: 0, 7, 10, 14, 22, 23
   - Same group receives sources at different times
   - No correlation between group index and query order

3. **No query metadata in result groups**
   - Groups only contain: `type`, `domain`, `entries`
   - Missing: `query_id`, `query_index`, or similar fields
   - No way to link a source back to its originating query

4. **SSE streaming format complicates tracking**
   - Sources added incrementally via PATCH operations
   - Path format: `/message/metadata/search_result_groups/N/entries`
   - Group index N doesn't correlate to query index

#### Architectural Impact

**Decision:** Store sources with `response_id` instead of `search_query_id` for network logs

```python
# API Mode
source.search_query_id = query.id  # One-to-one mapping
source.response_id = None

# Network Log Mode
source.search_query_id = None  # No reliable mapping
source.response_id = response.id  # Associate with response
```

**Display Strategy:**
- API Mode: Sources grouped by query
- Network Mode: All sources shown together under response
- UI displays caption: "Note: Network logs don't provide reliable query-to-source mapping"

### What Network Logs DO Provide

Despite the limitation, network logs offer unique insights:

1. **Search Queries Executed**
   - Full list of queries sent to search engine
   - Query reformulations visible
   - Example: `search_model_queries` metadata field

2. **Sources Fetched**
   - Complete list of search results
   - URL, title, domain, snippet, publication date
   - Rank information (position in results)

3. **Internal Ranking Scores**
   - ChatGPT's internal relevance scoring
   - Not available via API
   - Shows how model evaluates source importance

4. **Query Reformulations**
   - How ChatGPT refines searches
   - Multiple attempts to find better results
   - Insight into search strategy

5. **Snippet Text**
   - Actual text previews from search results
   - Shows what content model saw before citing
   - Useful for understanding citation decisions

6. **Citation Confidence Scores**
   - Model's confidence in each citation
   - Helps understand citation quality

### Validation: Interaction 61 Case Study

```
Model: gpt-5.1
Response Time: 29,527ms

Search Queries: 2
  1. "Half-Life 3 latest news 2025 Half Life 3 rumours November 2025"
  2. "is there any recent news about Half-Life 3 game development..."

Sources Fetched: 13 (query association unknown)
Sources Used: 3 (citations from fetched sources)
  - Rank 3: www.thegamer.com
  - Rank 4: www.pcgamer.com
  - Rank 10: wccftech.com
Average Rank: 5.7

Extra Links: 7 (citations not in fetched sources)
Citations Total: 10
```

**Analysis:**
- 70% of citations came from training data, not search
- Only 23% of fetched sources were actually cited
- Model preferred mid-ranked sources over top results
- Demonstrates hybrid search + knowledge approach

---

## Browser Automation Learnings

### Challenge 1: OpenAI Browser Detection

**Problem:** OpenAI detects automated browsers and serves degraded UI

**Evidence:**
- Safari (normal browser): Shows "Attach/Search/Study" buttons ✓
- Playwright + Chromium: Shows only "Add/Voice" buttons ✗
- Search functionality completely hidden

**Detection Methods Used:**
- Browser fingerprinting (WebGL, Canvas)
- Missing browser APIs (Notifications, Permissions)
- Chrome vs Chromium differences
- Automation signals despite `--disable-blink-features=AutomationControlled`

**Solution:** Use Chrome instead of Chromium

```python
browser = playwright.chromium.launch(
    headless=False,
    channel='chrome',  # Key: Use Chrome, not Chromium
    args=['--disable-blink-features=AutomationControlled']
)
```

**Result:** ✅ Chrome bypasses detection - Search button accessible

**Lesson:** Browser fingerprint matters more than stealth libraries

### Challenge 2: Cloudflare CAPTCHA

**Problem:** Headless mode triggers Cloudflare CAPTCHA

**Solution:** Use non-headless mode (`headless=False`)

**Trade-off:** Visible browser window vs. reliability

**Result:** ✅ CAPTCHA bypassed successfully

### Challenge 3: Session Persistence

**Initial Approach:** Persistent Chrome profile
- Created 696 files (29MB)
- Excessive overhead
- Slow initialization

**Final Approach:** Playwright's storageState API
- Single JSON file (190KB)
- 99.3% storage reduction
- Fast session restore

**Implementation:**
```python
# Save session
await context.storage_state(path='data/chatgpt_session.json')

# Restore session
context = browser.new_context(storage_state='data/chatgpt_session.json')
```

**Result:** ✅ Sessions persist between runs, auto-login works

### Challenge 4: Search Toggle Activation

**Evolution of Solutions:**

1. **Initial:** Menu navigation (Add → More → Web search)
   - Works but fragile
   - UI changes break it

2. **Better:** `/search` slash command
   - Type `/search ` (with space) in textarea
   - More reliable than menu
   - Faster activation

3. **Current:** Slash command + menu fallback
   - Try `/search` first
   - Fall back to menu if needed
   - Detect activation by counting "Web search" text

**Result:** ✅ Robust search enablement with dual approach

---

## Architecture Decisions

### Decision 1: Dual Mode Support (API + Network)

**Rationale:**
- API: Reliable but limited insight
- Network: Deeper insight but fragile
- Both have value for different use cases

**Implementation:**
- Single unified schema
- `data_source` field: 'api' or 'network_log'
- Optional fields for network-exclusive data

**Trade-off:** Complexity vs. flexibility

### Decision 2: Citation Classification

**Problem:** Models cite from multiple sources

**Solution:** Classify by rank presence

```python
# Sources Used: Citations WITH ranks (from search)
sources_used = [c for c in citations if c.rank is not None]

# Extra Links: Citations WITHOUT ranks (from training)
extra_links = [c for c in citations if c.rank is None]
```

**Impact:**
- Reveals hybrid citation behavior
- More accurate metrics
- Better understanding of model behavior

**Metrics Affected:**
- Sources Used: Now only counts search-based citations
- Extra Links: New metric for training-based citations
- Average Rank: Only calculated from Sources Used

### Decision 3: response_id for Network Logs

**Problem:** Network logs don't map queries to sources

**Solution:** Associate sources with response, not query

**Honest Representation:**
- "We know these sources were fetched"
- "We don't know from which specific query"
- UI clearly states the limitation

**Benefits:**
- Accurate data representation
- No false associations
- Forward compatible (can add query_id if API changes)

### Decision 4: Database Schema

**Key Fields:**

```sql
-- Responses
data_source VARCHAR  -- 'api' or 'network_log'
extra_links_count INT  -- Citations not from search

-- Sources
search_query_id INT NULL  -- API mode: required, Network: NULL
response_id INT NULL      -- API mode: NULL, Network: required
rank INT NULL             -- Position in search results (1-indexed)
internal_score FLOAT NULL -- Network logs only
snippet_text TEXT NULL    -- Network logs only

-- Search Queries
query_reformulations JSON NULL  -- Network logs only
```

**Design Principle:** Single schema handles both modes with optional fields

---

## Metrics & Calculations

### Search Queries

**Definition:** Number of searches the model executed

**Calculation:**
```python
len(response.search_queries)
```

**Notes:**
- Models may execute multiple queries per prompt
- Query reformulations captured in network logs
- Shows search strategy complexity

### Sources Found

**Definition:** Total URLs retrieved from web search

**Calculation:**

API Mode (per-query):
```python
sum(len(query.sources) for query in search_queries)
```

Network Mode (response-level):
```python
len(response.sources)
```

**Notes:**
- Network mode doesn't map to individual queries
- Represents search result volume
- Doesn't indicate which were actually cited

### Sources Used

**Definition:** Citations that came FROM search results

**Calculation:**
```python
sources_used = [c for c in citations if c.rank is not None]
count = len(sources_used)
```

**Key Insight:** Rank presence = from search results

**Notes:**
- Only citations WITH rank numbers
- Excludes training data citations (Extra Links)
- Used for Average Rank calculation
- Google: Always 0 (API limitation)

### Extra Links

**Definition:** Citations that came FROM training data

**Calculation:**
```python
extra_links = [c for c in citations if c.rank is None]
count = len(extra_links)
```

**Key Insight:** No rank = from training data

**Notes:**
- URLs model already knew about
- Not from current search results
- Indicates hybrid search + knowledge approach
- Higher count = more reliance on training

### Average Rank

**Definition:** Mean position of cited sources in search results

**Calculation:**
```python
sources_used = [c for c in citations if c.rank is not None]
if sources_used:
    avg_rank = sum(c.rank for c in sources_used) / len(sources_used)
else:
    avg_rank = None  # Display as "N/A"
```

**Interpretation:**
- Lower = prefers higher-ranked sources
- Higher = cites from deeper in results
- Shows citation preference pattern

**Notes:**
- Only calculated from Sources Used (not Extra Links)
- Google: N/A (no rank data)
- 1-indexed (1 = top result)

### Response Time

**Definition:** Model response latency in milliseconds

**Calculation:**
```python
response_time_ms = (end_time - start_time) * 1000
```

**Display:**
```python
response_time_s = f"{response_time_ms / 1000:.1f}s"
```

---

## Key Limitations

### Provider-Specific

**Google Gemini:**
- ❌ Cannot distinguish Sources Used from Sources Found
- ❌ No rank information
- Result: Limited citation analysis

**ChatGPT Network Logs:**
- ❌ No query-to-source mapping
- ⚠️ Free tier search execution unreliable
- Result: Response-level aggregates only

**All Providers (API Mode):**
- ❌ No internal ranking scores
- ❌ No query reformulations
- ❌ Limited snippet text
- Result: Surface-level metadata only

### Technical

**Browser Automation:**
- Requires Chrome (Chromium detected)
- Non-headless mode needed (visible browser)
- Single provider (ChatGPT) supported
- Session management complexity

**Rate Limiting:**
- Unknown limits for network mode
- No official support
- Risk of account issues

---

## Future Research Questions

### Unanswered Questions

1. **Citation Preference:**
   - Why do models skip top-ranked sources?
   - What factors drive citation selection?
   - How much does recency matter vs. rank?

2. **Search Strategy:**
   - Why multiple queries for simple questions?
   - How are query reformulations decided?
   - What triggers additional searches?

3. **Hybrid Behavior:**
   - When does model prefer training data over search?
   - How does it decide between sources?
   - Can we predict Extra Links count?

4. **Provider Differences:**
   - Why different citation volumes across providers?
   - How do search result counts compare?
   - What explains rank preference patterns?

5. **Network Logs:**
   - Will OpenAI add query-source mapping?
   - Can we reverse-engineer the mapping?
   - What other metadata is available but unparsed?

### Potential Enhancements

1. **Multi-Provider Network Capture:**
   - Extend to Claude, Gemini
   - Compare network vs API data
   - Identify unique insights per provider

2. **Advanced Analytics:**
   - Citation confidence visualization
   - Internal score analysis
   - Query reformulation timeline
   - Domain preference patterns

3. **Machine Learning:**
   - Predict citation likelihood from rank + score
   - Classify queries by search strategy
   - Detect citation patterns

---

## Lessons Learned

### Development

1. **Don't assume data exists**
   - Just because it seems logical doesn't mean the API provides it
   - Always validate with real data first

2. **Be honest about limitations**
   - Better to acknowledge what we can't determine
   - Clear communication prevents misinterpretation

3. **Test with real examples**
   - Validation scripts caught the query-mapping issue early
   - Saved implementation of flawed architecture

4. **Document everything**
   - Future developers need context
   - Decisions make sense with rationale

### Technical

5. **Browser fingerprints matter**
   - Chrome vs Chromium makes a difference
   - Stealth libraries aren't always enough
   - Non-headless mode often required

6. **Session persistence is valuable**
   - storageState API is lightweight and effective
   - Avoids repeated authentication
   - 99% storage reduction vs. persistent profiles

7. **Fallback strategies work**
   - Slash command + menu navigation
   - Dual mode (API + Network) architecture
   - Graceful degradation when features unavailable

### Analysis

8. **Models use hybrid approaches**
   - Search + training data citations
   - Not purely search-based
   - Extra Links metric reveals this

9. **Citation ≠ search result**
   - Models cite what's useful, not just what's found
   - Rank preference varies by content
   - Higher rank doesn't guarantee citation

10. **Provider APIs vary greatly**
    - Google: No citation separation
    - OpenAI: Full query mapping
    - Anthropic: Detailed tool execution
    - Network logs: Rich but unmapped

---

## References

### Related Documents
- `README.md` - Project overview and setup
- `docs/proposals/LIVE_NETWORK_LOGS_PLAN.md` - Live log tab design
- `tests/test_parse_interaction_61.py` - Network log validation script

### Key Code Locations
- `backend/app/services/providers/` - API provider implementations
- `frontend/network_capture/parser.py` - Network log parsing
- `backend/app/models/database.py` - Schema and metrics calculation
- `frontend/components/` - UI rendering helpers

---

**Document Maintainers:** Add new findings and insights as they're discovered. Keep this as the single source of truth for project learnings.
