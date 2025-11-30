# Network Log Analysis: Issues, Desired Behavior, and Remediation Plan

## Context
We ingest ChatGPT network logs to recover searches, results, citations, and the final response. For network logs we **cannot** reliably map results to specific queries (OpenAI does not expose that cleanly), but we **can** store all results and reconcile the final answer’s links back to stored results when URLs align.

## Current Issues (latest run, response id 66)
- **URL normalization missing:** Links with tracking params (e.g., `?utm_source=chatgpt.com`) aren’t normalized, so real matches are missed. After stripping, 2/12 links would match stored sources.
- **Source capture gap:** Most response links (10/12) were never saved in `sources`, so they cannot be matched.
- **Sources Used empty/incorrect:** Because matching fails, `sources_used` is empty; ranks/used counts/avg. rank become meaningless.
- **Extra Links undercounted:** Stored `extra_links_count` was 0, but at least 10 response URLs were not in saved sources.
- **Metrics unreliable:** “Sources Used,” “Avg. Rank,” and “Extra Links” are incorrect until matching and capture are fixed.
- **Citation parsing too narrow:** Only markdown reference definitions (`[N]: URL`) are parsed; inline links in the response body are ignored, so extra links go uncounted.
- **UI metrics re-derived incorrectly:** Interactive/history views compute “Sources Used” as citations with rank and “Extra Links” as citations without rank, ignoring unmatched inline links and ignoring the stored `extra_links_count`.

## How It Should Work (network logs)
1) **Capture all search results:** Persist every result URL with rank, domain, title, snippet, pub_date, and `response_id`. Do not force `search_query_id`; optionally keep a `query_index` if inferable.
2) **Normalize URLs:** Strip common tracking params (at least `utm_source=chatgpt.com`) before any matching.
3) **Expand link extraction:** Parse both markdown reference definitions and inline links from the response text so all links participate in matching/extra-link counting.
4) **Match response links/citations to stored sources:** Use normalized URLs. If matched, record rank/query_index; if not, mark as extra.
5) **Compute metrics off real matches:**
   - Sources Found = count of stored sources for the response.
   - Sources Used = matched citations/links.
   - Avg. Rank = average rank of matched items; “N/A” if none.
   - Extra Links = all response URLs (citations + inline links) not found in stored sources after normalization.
6) **UI messaging:** Keep queries visible, but do not imply per-query source mapping for network logs.

## Remediation Plan
1) **URL normalization:** Implement stripping of `utm_source=chatgpt.com` (and similar) before matching links to sources and when computing extra links.
2) **Fix source capture:** Audit the network log parser to ensure all search-result URLs are saved; diagnose why 10/12 response URLs were missing from `sources` in the latest run.
3) **Expand link extraction:** Parse both markdown reference definitions and inline links from the response text so all links participate in matching/extra-link counting.
4) **Matching logic:** When saving `sources_used`, match normalized URLs to stored sources; assign rank/query_index only when matched; otherwise flag as extra.
5) **Extra link counting:** Recompute `extra_links_count` from all normalized response URLs not found in stored sources (citations + inline links), not just those flagged.
6) **Metrics update:** Drive “Sources Used,” “Avg. Rank,” and “Extra Links” from the corrected matching logic (and/or stored `extra_links_count`), and avoid implying per-query mapping for network logs.
7) **Verification:** Run a fresh network-log test and confirm expectations: after normalization, matches should be counted; remaining unmatched links should inflate Extra Links; metrics should reflect the true breakdown.

## Progress Tracking
- [ ] URL normalization implemented
- [ ] Decide if normalized URLs need columns in DB (sources/sources_used)
- [ ] Source capture gap resolved
- [ ] Matching logic corrected (sources_used populated only on real matches)
- [ ] Extra_links_count computed from unmatched response URLs
- [ ] Metrics updated to use matched/unmatched split
- [ ] Verified on fresh network-log run
