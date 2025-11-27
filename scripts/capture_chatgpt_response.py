"""
Capture actual ChatGPT network response for analysis.

This script submits a prompt programmatically and captures the network traffic.
"""

from playwright.sync_api import sync_playwright
import json
import time


def capture_chatgpt_response():
    """Submit a prompt to ChatGPT and capture network responses."""

    print("Starting ChatGPT network capture...")
    print("=" * 80)

    captured_responses = []
    captured_requests = []

    with sync_playwright() as p:
        # Launch browser (visible for debugging)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Capture network traffic
        def handle_request(request):
            """Capture requests."""
            if 'chatgpt.com' in request.url or 'openai.com' in request.url:
                captured_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'post_data': request.post_data if request.method == 'POST' else None
                })

        def handle_response(response):
            """Capture responses."""
            if 'chatgpt.com' in response.url or 'openai.com' in response.url:
                try:
                    body = response.body()
                    captured_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'method': response.request.method,
                        'body_size': len(body) if body else 0,
                        'content_type': response.headers.get('content-type', ''),
                        'body': body.decode('utf-8') if body and len(body) < 1000000 else '[too large]'
                    })

                    # Print large JSON responses
                    if (response.status == 200 and
                        'json' in response.headers.get('content-type', '') and
                        body and len(body) > 100):
                        print(f"\n📡 Captured JSON response:")
                        print(f"  URL: {response.url}")
                        print(f"  Size: {len(body)} bytes")

                except Exception as e:
                    pass

        page.on('request', handle_request)
        page.on('response', handle_response)

        # Navigate to ChatGPT
        print("\n🌐 Navigating to ChatGPT...")
        page.goto('https://chatgpt.com', wait_until='domcontentloaded')

        print("⏳ Waiting for page to load...")
        time.sleep(5)

        # Look for the textarea
        print("\n🔍 Looking for prompt input...")
        try:
            # Try to find textarea
            textarea = page.locator('textarea').first
            if textarea.count() > 0:
                print("✓ Found textarea")

                # Enter prompt
                test_prompt = "What are the latest news in AI this week?"
                print(f"\n✍️  Typing prompt: {test_prompt}")
                textarea.fill(test_prompt)

                time.sleep(1)

                # Try to find and click submit button
                print("\n🔍 Looking for submit button...")

                # Common patterns for submit buttons
                submit_selectors = [
                    'button[data-testid="send-button"]',
                    'button[aria-label="Send message"]',
                    'button[type="submit"]',
                    'button:has-text("Send")',
                ]

                submitted = False
                for selector in submit_selectors:
                    try:
                        button = page.locator(selector).first
                        if button.count() > 0:
                            print(f"✓ Found button with selector: {selector}")
                            button.click()
                            submitted = True
                            print("✓ Clicked submit button")
                            break
                    except:
                        continue

                if not submitted:
                    # Try pressing Enter
                    print("Trying Enter key instead...")
                    textarea.press('Enter')
                    submitted = True

                if submitted:
                    print("\n⏳ Waiting for response (30 seconds)...")
                    time.sleep(30)

                    print(f"\n\n📊 Capture Summary:")
                    print(f"Requests captured: {len(captured_requests)}")
                    print(f"Responses captured: {len(captured_responses)}")

                    # Find interesting responses
                    print("\n🔍 Large JSON responses (likely containing data):")
                    for resp in captured_responses:
                        if (resp['status'] == 200 and
                            'json' in resp['content_type'] and
                            resp['body_size'] > 500):
                            print(f"\n  URL: {resp['url']}")
                            print(f"  Size: {resp['body_size']} bytes")

                            # Try to parse and show structure
                            if resp['body'] != '[too large]':
                                try:
                                    data = json.loads(resp['body'])
                                    print(f"  Top-level keys: {list(data.keys())[:10]}")

                                    # Look for search-related data
                                    if isinstance(data, dict):
                                        for key in data.keys():
                                            if any(term in key.lower() for term in ['search', 'url', 'source', 'web']):
                                                print(f"    → Interesting key: {key}")
                                except:
                                    pass

                    # Save full data
                    output_file = 'chatgpt_capture.json'
                    with open(output_file, 'w') as f:
                        json.dump({
                            'requests': captured_requests,
                            'responses': captured_responses
                        }, f, indent=2)

                    print(f"\n\n💾 Full capture saved to: {output_file}")

            else:
                print("✗ No textarea found")

        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 80)
        print("Keeping browser open for 10 seconds for inspection...")
        time.sleep(10)

        browser.close()


if __name__ == '__main__':
    try:
        capture_chatgpt_response()
    except KeyboardInterrupt:
        print("\n\nCapture cancelled.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
