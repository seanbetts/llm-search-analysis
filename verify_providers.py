#!/usr/bin/env python
"""
Integration test script to verify API providers and model configurations.

This script tests real API calls to ensure:
- API keys are valid
- Model names are correct
- Search/grounding features work
- Response parsing works with real data

Usage:
    python verify_providers.py

Note: Requires valid API keys in .env file
"""

import sys
from src.config import Config
from src.providers.provider_factory import ProviderFactory


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_section(text):
    """Print a formatted section header."""
    print(f"\n--- {text} ---")


def verify_api_keys():
    """Check which API keys are configured."""
    print_header("API KEY VERIFICATION")

    keys_status = Config.validate_api_keys()

    for provider, is_set in keys_status.items():
        status = "✓ SET" if is_set else "✗ MISSING"
        print(f"{provider.upper():12} {status}")

    missing_keys = [p for p, is_set in keys_status.items() if not is_set]

    if missing_keys:
        print(f"\n⚠️  Missing API keys: {', '.join(missing_keys)}")
        print("   Add them to your .env file to test those providers")

    return keys_status


def test_provider(provider_name, model, api_keys):
    """
    Test a specific provider and model.

    Args:
        provider_name: Name of provider (openai, google, anthropic)
        model: Model identifier to test
        api_keys: Dictionary of API keys

    Returns:
        Dict with test results
    """
    result = {
        "provider": provider_name,
        "model": model,
        "success": False,
        "error": None,
        "response_preview": None,
        "search_queries": 0,
        "sources": 0,
        "citations": 0,
        "response_time_ms": None
    }

    try:
        # Get provider instance
        provider = ProviderFactory.get_provider(model, api_keys)

        # Test prompt that should trigger search
        test_prompt = "What are the latest developments in artificial intelligence this week?"

        print(f"   Testing: {model}")
        print(f"   Prompt: {test_prompt[:50]}...")

        # Send prompt
        response = provider.send_prompt(test_prompt, model)

        # Extract results
        result["success"] = True
        result["response_preview"] = response.response_text[:100] + "..." if len(response.response_text) > 100 else response.response_text
        result["search_queries"] = len(response.search_queries)
        result["sources"] = len(response.sources)
        result["citations"] = len(response.citations)
        result["response_time_ms"] = response.response_time_ms

        # Print results
        print(f"   ✓ Success!")
        print(f"   Response time: {response.response_time_ms}ms")
        print(f"   Search queries: {len(response.search_queries)}")
        print(f"   Sources fetched: {len(response.sources)}")
        print(f"   Citations used: {len(response.citations)}")

        if response.search_queries:
            print(f"   First query: '{response.search_queries[0].query}'")

        if response.sources:
            print(f"   First source: {response.sources[0].url}")

    except ValueError as e:
        result["error"] = f"Configuration error: {str(e)}"
        print(f"   ✗ Error: {result['error']}")
    except Exception as e:
        result["error"] = f"API error: {str(e)}"
        print(f"   ✗ Error: {result['error']}")

    return result


def main():
    """Run verification tests."""
    print_header("LLM SEARCH ANALYSIS - PROVIDER VERIFICATION")
    print("This script will test real API calls to verify configuration.")
    print("It will make actual API requests and may incur small costs.")

    # Verify API keys
    keys_status = verify_api_keys()
    api_keys = Config.get_api_keys()

    # Get all supported models
    all_models = ProviderFactory.get_all_supported_models()

    # Group by provider
    models_by_provider = {}
    for model in all_models:
        provider = ProviderFactory.get_provider_for_model(model)
        if provider not in models_by_provider:
            models_by_provider[provider] = []
        models_by_provider[provider].append(model)

    # Test each provider
    results = []

    for provider_name in ["openai", "google", "anthropic"]:
        print_header(f"{provider_name.upper()} PROVIDER")

        if not keys_status.get(provider_name):
            print(f"⚠️  Skipping - API key not configured")
            continue

        models = models_by_provider.get(provider_name, [])
        print(f"Testing {len(models)} models: {', '.join(models)}")

        for model in models:
            print_section(model)
            result = test_provider(provider_name, model, api_keys)
            results.append(result)

    # Print summary
    print_header("VERIFICATION SUMMARY")

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\nTotal models tested: {len(results)}")
    print(f"✓ Successful: {len(successful)}")
    print(f"✗ Failed: {len(failed)}")

    if successful:
        print("\n✓ WORKING MODELS:")
        for r in successful:
            search_info = f"({r['search_queries']} searches, {r['sources']} sources, {r['citations']} citations)"
            print(f"  • {r['model']:30} {search_info}")

    if failed:
        print("\n✗ FAILED MODELS:")
        for r in failed:
            print(f"  • {r['model']:30} - {r['error']}")

    # Search feature analysis
    print("\n📊 SEARCH FEATURE ANALYSIS:")
    models_with_search = [r for r in successful if r['search_queries'] > 0]
    models_without_search = [r for r in successful if r['search_queries'] == 0]

    if models_with_search:
        print(f"  ✓ {len(models_with_search)} models have working search:")
        for r in models_with_search:
            print(f"    • {r['model']}")

    if models_without_search:
        print(f"  ⚠️  {len(models_without_search)} models responded but didn't search:")
        for r in models_without_search:
            print(f"    • {r['model']}")

    # Final recommendation
    print("\n" + "=" * 80)
    if failed:
        print("⚠️  RECOMMENDATION: Fix failed models before proceeding to UI development")
        print("   Check model names and API configurations")
    elif models_without_search:
        print("⚠️  RECOMMENDATION: Investigate why some models aren't using search")
        print("   They may need different prompts or configuration")
    else:
        print("✓ ALL SYSTEMS GO! Ready to proceed with Phase 2: Streamlit UI")
    print("=" * 80)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
