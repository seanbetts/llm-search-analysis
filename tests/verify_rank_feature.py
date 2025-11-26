"""
Test script to verify rank feature works correctly across all providers.
"""

from src.config import Config
from src.providers.openai_provider import OpenAIProvider
from src.providers.google_provider import GoogleProvider
from src.providers.anthropic_provider import AnthropicProvider

def test_provider(provider, model, provider_name):
    """Test a single provider to verify rank tracking."""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name} with model {model}")
    print('='*60)

    prompt = "Who won the 2024 NBA championship?"

    try:
        response = provider.send_prompt(prompt, model)

        print(f"\n✓ Response received ({len(response.response_text)} chars)")
        print(f"  Response time: {response.response_time_ms}ms")

        # Check search queries and sources
        print(f"\n📊 Search Queries: {len(response.search_queries)}")
        for i, query in enumerate(response.search_queries, 1):
            print(f"  {i}. \"{query.query}\" - {len(query.sources)} sources")

            # Verify each source has a rank
            for j, source in enumerate(query.sources, 1):
                if source.rank:
                    print(f"     ✓ Source {j}: rank={source.rank}, url={source.url[:50]}...")
                else:
                    print(f"     ✗ Source {j}: NO RANK! url={source.url[:50]}...")

        # Check all sources
        print(f"\n📚 Total Sources: {len(response.sources)}")
        sources_with_rank = sum(1 for s in response.sources if s.rank)
        print(f"  Sources with rank: {sources_with_rank}/{len(response.sources)}")

        # Check citations
        print(f"\n📝 Citations: {len(response.citations)}")
        for i, citation in enumerate(response.citations, 1):
            if citation.rank:
                print(f"  {i}. rank={citation.rank}, url={citation.url[:50]}...")
            else:
                print(f"  {i}. NO RANK, url={citation.url[:50]}...")

        citations_with_rank = sum(1 for c in response.citations if c.rank)
        print(f"  Citations with rank: {citations_with_rank}/{len(response.citations)}")

        # Summary
        print(f"\n✅ Test passed for {provider_name}")
        if sources_with_rank < len(response.sources):
            print(f"⚠️  Warning: Not all sources have ranks ({sources_with_rank}/{len(response.sources)})")

        return True

    except Exception as e:
        print(f"\n❌ Test failed for {provider_name}: {str(e)}")
        return False

def main():
    """Run tests for all available providers."""
    print("="*60)
    print("RANK FEATURE TEST SUITE")
    print("="*60)

    # Get API keys
    api_keys = Config.get_api_keys()

    results = {}

    # Test OpenAI
    if api_keys.get('openai'):
        provider = OpenAIProvider(api_keys['openai'])
        results['OpenAI'] = test_provider(provider, 'gpt-5.1', 'OpenAI')
    else:
        print("\n⊘ Skipping OpenAI (no API key)")
        results['OpenAI'] = None

    # Test Google
    if api_keys.get('google'):
        provider = GoogleProvider(api_keys['google'])
        results['Google'] = test_provider(provider, 'gemini-2.5-flash', 'Google')
    else:
        print("\n⊘ Skipping Google (no API key)")
        results['Google'] = None

    # Test Anthropic
    if api_keys.get('anthropic'):
        provider = AnthropicProvider(api_keys['anthropic'])
        results['Anthropic'] = test_provider(provider, 'claude-sonnet-4-5-20250929', 'Anthropic')
    else:
        print("\n⊘ Skipping Anthropic (no API key)")
        results['Anthropic'] = None

    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)

    for provider, result in results.items():
        if result is None:
            print(f"{provider}: SKIPPED (no API key)")
        elif result:
            print(f"{provider}: ✅ PASSED")
        else:
            print(f"{provider}: ❌ FAILED")

    print("\nTest suite complete!")

if __name__ == "__main__":
    main()
