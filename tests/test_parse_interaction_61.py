"""
Standalone test script to parse interaction 61's raw network log.

This script validates the parsing logic before implementing changes to the parser.
"""

import sys
from pathlib import Path
import re
import json

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.database import Database, Response, Prompt

def extract_citations_from_markdown(response_text):
    """
    Extract citations from markdown reference links.

    Format: [N]: URL "Title"

    Returns: List of (ref_num, url, title)
    """
    link_pattern = r'\[(\d+)\]:\s*(https?://[^\s\"]+)(?:\s+"([^"]*)")?'
    citations = re.findall(link_pattern, response_text)
    return [(int(num), url, title or "") for num, url, title in citations]


def parse_search_queries(raw_response):
    """Parse search queries from SSE event stream."""
    body = raw_response.get('body', '')
    if not body:
        return []

    queries = []
    lines = body.split('\n')

    for line in lines:
        if not line.startswith('data: '):
            continue

        try:
            data = json.loads(line[6:])  # Remove "data: " prefix

            # Handle potential string double-encoding
            if isinstance(data, str):
                data = json.loads(data)

            if 'v' in data and 'message' in data['v']:
                metadata = data['v']['message'].get('metadata', {})
                if 'search_model_queries' in metadata:
                    query_data = metadata['search_model_queries']
                    if 'queries' in query_data:
                        queries.extend(query_data['queries'])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return queries


def parse_sources_from_network_log(raw_response):
    """
    Parse sources from SSE event stream.

    Returns: List of source dicts with:
        - url
        - title
        - domain
        - snippet
        - pub_date
        - rank (position in search results)
    """
    body = raw_response.get('body', '')
    if not body:
        return []

    sources = []
    lines = body.split('\n')

    # Track groups as they're built incrementally
    search_result_groups = []

    for line in lines:
        if not line.startswith('data: '):
            continue

        try:
            data = json.loads(line[6:])

            # Handle potential string double-encoding
            if isinstance(data, str):
                data = json.loads(data)

            # Initial groups from message metadata
            if 'v' in data and 'message' in data['v']:
                metadata = data['v']['message'].get('metadata', {})
                if 'search_result_groups' in metadata:
                    for group in metadata['search_result_groups']:
                        search_result_groups.append(group)

            # Handle patch/append operations
            if 'p' in data:
                path = data.get('p', '')
                value = data.get('v')

                # Adding entries to a specific group
                if '/entries' in path and 'search_result_groups' in path:
                    if isinstance(value, list):
                        # Extract group index from path
                        # Path format: "/message/metadata/search_result_groups/0/entries"
                        parts = path.split('/')
                        try:
                            group_idx = int(parts[parts.index('search_result_groups') + 1])
                            # Ensure we have enough groups
                            while len(search_result_groups) <= group_idx:
                                search_result_groups.append({'entries': []})
                            if 'entries' not in search_result_groups[group_idx]:
                                search_result_groups[group_idx]['entries'] = []
                            search_result_groups[group_idx]['entries'].extend(value)
                        except (ValueError, IndexError):
                            pass

                # Adding a new group
                elif 'search_result_groups' in path:
                    if isinstance(value, dict) and value.get('type') == 'search_result_group':
                        search_result_groups.append(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and item.get('type') == 'search_result_group':
                                search_result_groups.append(item)

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Extract sources from groups
    rank = 1
    for group in search_result_groups:
        domain = group.get('domain', '')
        entries = group.get('entries', [])

        for entry in entries:
            if entry.get('type') != 'search_result':
                continue

            source = {
                'url': entry.get('url', ''),
                'title': entry.get('title', ''),
                'domain': entry.get('attribution', domain),
                'snippet': entry.get('snippet', ''),
                'pub_date': entry.get('pub_date'),
                'rank': rank
            }
            sources.append(source)
            rank += 1

    return sources


def clean_url(url):
    """Remove utm parameters for URL matching."""
    return url.replace('?utm_source=chatgpt.com', '')


def main():
    # Load interaction 61 from database
    db = Database()
    session = db.get_session()

    try:
        resp = session.query(Response).filter_by(id=61).first()
        if not resp:
            print("ERROR: Interaction 61 not found in database")
            return

        # Get prompt for model info
        prompt = session.query(Prompt).filter_by(id=resp.prompt_id).first()
        model = prompt.session.model_used

        response_text = resp.response_text
        raw_response = resp.raw_response_json
        response_time_ms = resp.response_time_ms

        print("=" * 80)
        print("INTERACTION 61 ANALYSIS")
        print("=" * 80)
        print()

        # Parse citations from markdown references
        citations = extract_citations_from_markdown(response_text)

        # Parse search queries
        queries = parse_search_queries(raw_response)

        # Parse sources from network log
        sources = parse_sources_from_network_log(raw_response)

        # Deduplicate sources by URL
        unique_sources = {}
        for source in sources:
            clean = clean_url(source['url'])
            if clean not in unique_sources:
                unique_sources[clean] = source

        sources_deduped = list(unique_sources.values())

        # Match citations to sources (sources used)
        citation_urls = {clean_url(url) for _, url, _ in citations}
        source_urls = {clean_url(s['url']): s for s in sources_deduped}

        sources_used = []
        for cite_num, cite_url, cite_title in citations:
            clean = clean_url(cite_url)
            if clean in source_urls:
                source = source_urls[clean].copy()
                source['cite_num'] = cite_num
                sources_used.append(source)

        extra_links_urls = citation_urls - set(source_urls.keys())
        extra_links = []
        for cite_num, cite_url, cite_title in citations:
            clean = clean_url(cite_url)
            if clean in extra_links_urls:
                extra_links.append({
                    'cite_num': cite_num,
                    'url': cite_url,
                    'title': cite_title
                })

        # Calculate average rank of sources used
        if sources_used:
            avg_rank = sum(s['rank'] for s in sources_used) / len(sources_used)
        else:
            avg_rank = 0.0

        # Output summary
        print(f"Model: {model}")
        print(f"Response Time: {response_time_ms}ms")
        print()
        print(f"Search Queries: {len(queries)}")
        print(f"Sources Fetched: {len(sources_deduped)}")
        print(f"Sources Used: {len(sources_used)}")
        print(f"Av. Rank: {avg_rank:.1f}")
        print(f"Extra Links: {len(extra_links)}")
        print(f"Citations: {len(citations)}")
        print()
        print(f"Response Text: {response_text[:500]}...")
        print()

        # Output search queries & sources
        print("=" * 80)
        print("SEARCH QUERIES & SOURCES")
        print("=" * 80)
        print()
        for idx, query in enumerate(queries, 1):
            print(f"Query {idx}: \"{query[:80]}...\"")
        print()
        print(f"All Sources ({len(sources_deduped)}):")
        for source in sources_deduped[:10]:  # Show first 10
            print(f"  [Rank {source['rank']}] {source['title']}")
            print(f"    Domain: {source['domain']}")
            print(f"    URL: {source['url'][:80]}...")
            if source['snippet']:
                print(f"    Snippet: {source['snippet'][:100]}...")
            if source['pub_date']:
                print(f"    Published: {source['pub_date']}")
            print()
        if len(sources_deduped) > 10:
            print(f"  ... and {len(sources_deduped) - 10} more")
        print()

        # Output sources used
        print("=" * 80)
        print(f"SOURCES USED ({len(sources_used)})")
        print("=" * 80)
        print()
        for source in sources_used:
            print(f"  [Citation {source['cite_num']}] [Search Rank {source['rank']}] {source['title']}")
            print(f"    Domain: {source['domain']}")
            print(f"    URL: {source['url']}")
            if source['snippet']:
                print(f"    Snippet: {source['snippet'][:100]}...")
            if source['pub_date']:
                print(f"    Published: {source['pub_date']}")
            print()

        # Output extra links
        print("=" * 80)
        print(f"EXTRA LINKS (NOT FROM SEARCH) ({len(extra_links)})")
        print("=" * 80)
        print()
        for link in extra_links:
            print(f"  [Citation {link['cite_num']}] {link['title'] or '(No title)'}")
            print(f"    URL: {link['url']}")
            print()

        print("=" * 80)
        print("VALIDATION")
        print("=" * 80)
        print()
        print(f"✓ Citations extracted: {len(citations)} (expected: 10)")
        print(f"✓ Sources fetched: {len(sources_deduped)} (expected: ~15)")
        print(f"✓ Sources used: {len(sources_used)} (expected: 3)")
        print(f"✓ Extra links: {len(extra_links)} (expected: 7)")
        print()

    finally:
        session.close()


if __name__ == "__main__":
    main()
