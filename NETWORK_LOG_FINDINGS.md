# ChatGPT Network Log Parsing: Findings & Architectural Decisions

## Executive Summary

After deep analysis of ChatGPT network logs, we discovered a fundamental limitation: **the network logs do not provide reliable mapping between search queries and their results**. This document explains what we learned, the architectural decisions we made, and how we're storing this data honestly.

## Key Findings

### What We CAN Determine

1. **Search Queries Executed**
   - ChatGPT reports the search queries it executed via `search_model_queries` metadata
   - Example from interaction 61: 2 distinct queries

2. **Sources Fetched from Searches**
   - Search results are provided in `search_result_groups`
   - Each group contains entries with URL, title, domain, snippet, publication date
   - Example from interaction 61: 13 unique sources fetched

3. **Citations in Response**
   - ChatGPT uses markdown reference format: `[N]: URL "Title"`
   - These can be reliably extracted via regex
   - Example from interaction 61: 10 citations

4. **Sources Used (Citation-Search Intersection)**
   - By comparing citation URLs to fetched sources, we can determine which cited sources came from searches
   - Example from interaction 61: 3 out of 10 citations were from search results

5. **Extra Links (Sources NOT from Searches)**
   - Citations that don't match any fetched source
   - These come from ChatGPT's training data or uncaptured searches
   - Example from interaction 61: 7 extra links

### What We CANNOT Determine

**Query-to-Source Association** - The network logs do NOT indicate which query produced which source.

#### Evidence

1. **Both queries appear simultaneously**
   - Queries are listed together in one metadata block
   - No temporal separation or ordering

2. **Sources added to non-sequential group indices**
   - Groups created at indices: 0, 7, 10, 14, 22, 23
   - Same group (e.g., group 0) receives sources at different times
   - No correlation between group index and query order

3. **No query metadata in groups**
   - Groups only contain: `type`, `domain`, `entries`
   - No `query_id`, `query_index`, or similar fields

4. **SSE streaming format complicates tracking**
   - Sources added incrementally via PATCH operations
   - Path format: `/message/metadata/search_result_groups/N/entries`
   - Group index N doesn't correlate to query index

## Architectural Decisions

### Database Schema Changes

**Before:**
```python
class SourceModel:
    search_query_id = Column(Integer, ForeignKey("search_queries.id"))  # Required
```

**After:**
```python
class SourceModel:
    search_query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=True)
    response_id = Column(Integer, ForeignKey("responses.id"), nullable=True)
```

### Storage Strategy

**For API-Based Analysis:**
- Sources have `search_query_id` (one-to-one mapping possible)
- `response_id` is NULL

**For Network Log Analysis:**
- Sources have `response_id` but NULL `search_query_id`
- Search queries are stored separately without source associations
- Honest representation: "We know these sources were fetched, but not from which specific query"

### Updated Definitions

**For Network Logs:**

1. **Search Queries** - Queries executed (tracked separately, no source association)
2. **Sources Fetched** - Results from searches (associated with response, NOT specific queries)
3. **Sources Used** - Sources that appear in BOTH fetched sources AND response citations
4. **Extra Links** - Citations that do NOT appear in fetched sources
5. **Citations** - All links referenced in response text using `[N]: URL` format

## Metrics for Interaction 61

```
Model: gpt-5.1
Response Time: 29527ms

Search Queries: 2
  1. "Half-Life 3 latest news 2025 Half Life 3 rumours November 2025"
  2. "is there any recent news about Half-Life 3 game development Half Life 3 news November 2025 Valve"

Sources Fetched: 13 (from searches, query association unknown)
Sources Used: 3 (citations that came from fetched sources)
Average Rank: 5.7 (average rank of the 3 used sources)
Extra Links: 7 (citations not in fetched sources)
Citations: 10 (total links in response)
```

### The 3 Sources Used

1. [Citation 3] Half-Life 3 Appears To Be In Late Stage Development
   - Search Rank: 3
   - Domain: www.thegamer.com

2. [Citation 6] OK, for real though, what's the chance of a Half-Life 3 announcement happening soon?
   - Search Rank: 4
   - Domain: www.pcgamer.com

3. [Citation 10] 27 Years Later: Are Half-Life 3 Rumors Finally Real This Time?
   - Search Rank: 10
   - Domain: wccftech.com

### The 7 Extra Links

Citations [1, 2, 4, 5, 7, 8, 9] were NOT in the fetched search results. These came from:
- ChatGPT's training data
- Additional searches not captured in network log
- Other knowledge sources

## Implications

### For Analysis

1. **Cannot track query effectiveness individually**
   - Can't say "Query 1 returned N useful sources"
   - Can only say "Combined searches returned N sources, M were used"

2. **Aggregate metrics only**
   - Total sources fetched
   - Total sources used
   - Average rank of used sources
   - Extra links count

3. **Network logs reveal ChatGPT's hybrid approach**
   - Searches provide some sources
   - Training data/other sources provide additional citations
   - Not purely search-based like Perplexity

### For UI Display

**Search Queries Section:**
- List all queries executed
- Show all sources fetched (without per-query breakdown)

**Sources Used Section:**
- Show which citations came from searches
- Include search rank for context

**Extra Links Section:**
- Show citations that didn't come from searches
- Acknowledge these are from other sources

## Validation Script

See `tests/test_parse_interaction_61.py` for the standalone validation script that:
- Parses citations from markdown references
- Extracts search queries from SSE metadata
- Parses sources from search_result_groups
- Calculates sources used and extra links
- Outputs all metrics for verification

Run with: `python tests/test_parse_interaction_61.py`

## Migration Script

See `migrate_sources_schema.py` to apply database schema changes.

Run with: `python migrate_sources_schema.py`

## Lessons Learned

1. **Don't assume data exists** - Just because something seems logical doesn't mean the API provides it
2. **Validate with real data** - Our test script revealed the limitation before implementation
3. **Be honest about limitations** - Better to acknowledge what we can't determine than create false associations
4. **Document findings** - Future developers need to understand these constraints

## Future Considerations

If OpenAI updates their network log format to include query-source mappings, we can:
1. Update the parser to populate `search_query_id` when available
2. Keep backward compatibility with `response_id` approach
3. Provide richer per-query analysis

Until then, we represent the data honestly within its limitations.

---

**Last Updated:** 2025-11-29
**Analysis of:** Interaction 61 (ChatGPT Free, 2025-11-29)
