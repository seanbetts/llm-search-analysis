"""
Script to analyze ChatGPT network traffic structure.

This script helps us understand:
1. What network requests are made
2. Which endpoints contain search data
3. The structure of responses
4. How to identify relevant data

Run this script manually to observe network traffic, then use findings
to implement the actual capturer.
"""

from playwright.sync_api import sync_playwright
import json
import time


def analyze_chatgpt_network():
    """
    Launch browser and capture network traffic from free ChatGPT.

    Instructions:
    1. Script will open ChatGPT
    2. Manually submit a prompt that requires web search
    3. Script will capture and display all network responses
    4. Analyze the output to find search data
    """

    print("Starting ChatGPT network analysis...")
    print("=" * 80)

    captured_responses = []

    with sync_playwright() as p:
        # Launch browser (visible for manual interaction)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Capture network responses
        def handle_response(response):
            """Capture all responses from chatgpt.com domain."""
            if 'chatgpt.com' in response.url:
                try:
                    # Try to get response body
                    body = response.body()

                    captured_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'method': response.request.method,
                        'body_size': len(body) if body else 0,
                        'content_type': response.headers.get('content-type', 'unknown')
                    })

                    # Print interesting responses in real-time
                    if response.status == 200 and len(body) > 1000:
                        print(f"\n📡 Captured response:")
                        print(f"  URL: {response.url[:100]}")
                        print(f"  Size: {len(body)} bytes")
                        print(f"  Content-Type: {response.headers.get('content-type')}")

                        # Try to parse as JSON and show snippet
                        try:
                            if 'application/json' in response.headers.get('content-type', ''):
                                data = json.loads(body.decode('utf-8'))
                                print(f"  JSON keys: {list(data.keys())[:10]}")
                        except:
                            pass

                except Exception as e:
                    pass  # Some responses can't be read

        page.on('response', handle_response)

        # Navigate to ChatGPT
        print("\n🌐 Navigating to ChatGPT...")
        page.goto('https://chatgpt.com')

        print("\n" + "=" * 80)
        print("INSTRUCTIONS:")
        print("1. Submit a prompt that requires web search (e.g., 'What are the latest AI news?')")
        print("2. Wait for the response to complete")
        print("3. Press Enter in this terminal when done")
        print("=" * 80 + "\n")

        # Wait for user to submit prompt and observe traffic
        input("Press Enter when you've seen the response...")

        # Save captured data
        print(f"\n\n📊 Analysis Summary:")
        print(f"Total responses captured: {len(captured_responses)}")

        # Group by endpoint
        endpoints = {}
        for resp in captured_responses:
            # Extract endpoint from URL
            url_parts = resp['url'].split('?')[0]  # Remove query params
            endpoint = url_parts.replace('https://chatgpt.com', '')

            if endpoint not in endpoints:
                endpoints[endpoint] = []
            endpoints[endpoint].append(resp)

        print(f"\nUnique endpoints hit: {len(endpoints)}")
        print("\nEndpoints by frequency:")
        for endpoint, responses in sorted(endpoints.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {len(responses):3d}x  {endpoint[:80]}")

        # Find likely candidates for search data
        print("\n\n🔍 Likely search data endpoints (large JSON responses):")
        candidates = []
        for resp in captured_responses:
            if (resp['status'] == 200 and
                resp['body_size'] > 5000 and
                'json' in resp['content_type'].lower()):
                candidates.append(resp)
                print(f"  ✓ {resp['url'][:100]}")
                print(f"    Size: {resp['body_size']} bytes")

        # Save full analysis to file
        output_file = 'chatgpt_network_analysis.json'
        with open(output_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_responses': len(captured_responses),
                    'unique_endpoints': len(endpoints),
                    'candidates_for_search_data': len(candidates)
                },
                'endpoints': {k: len(v) for k, v in endpoints.items()},
                'all_responses': captured_responses
            }, f, indent=2)

        print(f"\n\n💾 Full analysis saved to: {output_file}")
        print("\nNext steps:")
        print("1. Review the 'Likely search data endpoints' above")
        print("2. Look for endpoints containing 'search', 'backend-api', 'conversation', etc.")
        print("3. Manually inspect those responses in browser DevTools")
        print("4. Look for JSON containing search queries, URLs, snippets")

        browser.close()


if __name__ == '__main__':
    print("""
    ChatGPT Network Traffic Analyzer
    =================================

    This script will help you discover how ChatGPT's network traffic works.

    Prerequisites:
    - pip install playwright
    - playwright install chromium

    The script will open a browser. You'll need to:
    1. Submit a prompt that triggers web search
    2. Wait for response
    3. Press Enter in terminal

    Ready? Press Enter to start...
    """)
    input()

    try:
        analyze_chatgpt_network()
    except KeyboardInterrupt:
        print("\n\nAnalysis cancelled.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        print("\nMake sure Playwright is installed:")
        print("  pip install playwright")
        print("  playwright install chromium")
