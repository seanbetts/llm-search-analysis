"""
Capture ChatGPT network response with modal/popup handling.

Handles:
1. Cookie banners
2. Corporate proxy warnings (Netscope)
3. Any other overlays blocking the UI
"""

from playwright.sync_api import sync_playwright
import json
import time


def capture_chatgpt_with_modals():
    """Submit a prompt to ChatGPT with modal handling."""

    print("Starting ChatGPT network capture with modal handling...")
    print("=" * 80)

    captured_responses = []

    with sync_playwright() as p:
        # Launch browser (visible for debugging)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Capture network traffic (simplified to avoid encoding errors)
        def handle_response(response):
            """Capture responses."""
            if 'chatgpt.com' in response.url or 'openai.com' in response.url:
                try:
                    body = response.body()
                    captured_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'body_size': len(body) if body else 0,
                        'content_type': response.headers.get('content-type', ''),
                        'body': body.decode('utf-8') if body and len(body) < 500000 else '[too large]'
                    })

                    # Print large JSON responses
                    if (response.status == 200 and
                        'json' in response.headers.get('content-type', '') and
                        body and len(body) > 100):
                        print(f"\n📡 Captured: {response.url[:80]} ({len(body)} bytes)")

                except Exception as e:
                    pass

        page.on('response', handle_response)

        # Navigate to ChatGPT
        print("\n🌐 Navigating to ChatGPT...")
        page.goto('https://chatgpt.com', wait_until='domcontentloaded')

        print("⏳ Waiting for page to load...")
        time.sleep(3)

        # Take screenshot for debugging
        page.screenshot(path='chatgpt_before_modals.png')
        print("📸 Screenshot saved: chatgpt_before_modals.png")

        # Handle potential modals/overlays
        print("\n🚫 Checking for modals/overlays...")

        # Look for common modal patterns
        modal_selectors = [
            # Cookie banners
            'button:has-text("Accept")',
            'button:has-text("Accept all")',
            'button:has-text("Allow all")',
            'button:has-text("I accept")',
            '[id*="cookie"] button',
            '[class*="cookie"] button',

            # Netscope/Corporate warnings
            'button:has-text("Continue")',
            'button:has-text("Proceed")',
            'button:has-text("I understand")',
            'button:has-text("Acknowledge")',

            # Generic close buttons
            'button[aria-label*="close"]',
            'button[aria-label*="dismiss"]',
            '[role="dialog"] button',
        ]

        for selector in modal_selectors:
            try:
                button = page.locator(selector).first
                if button.count() > 0 and button.is_visible():
                    print(f"✓ Found modal button: {selector}")
                    button.click()
                    print(f"  Clicked!")
                    time.sleep(1)
                    break
            except Exception as e:
                pass

        # Wait a bit more after dismissing modals
        time.sleep(2)

        # Take another screenshot
        page.screenshot(path='chatgpt_after_modals.png')
        print("📸 Screenshot saved: chatgpt_after_modals.png")

        # Now look for the textarea
        print("\n🔍 Looking for prompt input...")
        try:
            # Try different textarea selectors
            textarea_selectors = [
                'textarea[name="prompt-textarea"]',
                'textarea[placeholder*="Ask"]',
                'textarea',
                '#prompt-textarea',
            ]

            textarea = None
            for selector in textarea_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        print(f"✓ Found textarea with selector: {selector}")

                        # Wait for it to be visible
                        elem.wait_for(state='visible', timeout=5000)
                        print("✓ Textarea is visible!")
                        textarea = elem
                        break
                except Exception as e:
                    print(f"  {selector}: Not visible ({str(e)[:50]})")
                    continue

            if not textarea:
                print("\n❌ No visible textarea found.")
                print("\nDumping page text content for debugging:")
                print(page.inner_text('body')[:500])

                print("\n\nKeeping browser open for manual inspection...")
                print("Press Ctrl+C when done")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass

                browser.close()
                return

            # Enter prompt
            test_prompt = "What are the latest news in AI this week?"
            print(f"\n✍️  Typing prompt: {test_prompt}")
            textarea.fill(test_prompt)

            time.sleep(1)

            # Try to submit
            print("\n🔍 Looking for submit button...")

            submit_selectors = [
                'button[data-testid="send-button"]',
                'button[aria-label*="Send"]',
                'button[type="submit"]',
                'button:has-text("Send")',
                'button[aria-label*="Submit"]',
            ]

            submitted = False
            for selector in submit_selectors:
                try:
                    button = page.locator(selector).first
                    if button.count() > 0 and button.is_visible():
                        print(f"✓ Found submit button: {selector}")
                        button.click()
                        submitted = True
                        print("✓ Clicked submit!")
                        break
                except:
                    continue

            if not submitted:
                # Try pressing Enter
                print("Trying Enter key...")
                textarea.press('Enter')
                submitted = True
                print("✓ Pressed Enter")

            if submitted:
                print("\n⏳ Waiting for response (30 seconds)...")
                time.sleep(30)

                print(f"\n\n📊 Capture Summary:")
                print(f"Total responses captured: {len(captured_responses)}")

                # Find interesting responses
                print("\n🔍 Large JSON responses (likely containing data):")
                interesting = []
                for resp in captured_responses:
                    if (resp['status'] == 200 and
                        'json' in resp['content_type'] and
                        resp['body_size'] > 500):
                        interesting.append(resp)
                        print(f"\n  URL: {resp['url']}")
                        print(f"  Size: {resp['body_size']} bytes")

                        # Try to show JSON structure
                        if resp['body'] != '[too large]':
                            try:
                                data = json.loads(resp['body'])
                                print(f"  Keys: {list(data.keys())[:10]}")
                            except:
                                pass

                # Save full capture
                output_file = 'chatgpt_capture.json'
                with open(output_file, 'w') as f:
                    json.dump({
                        'total_responses': len(captured_responses),
                        'interesting_responses': len(interesting),
                        'responses': captured_responses
                    }, f, indent=2)

                print(f"\n\n💾 Full capture saved to: {output_file}")
                print(f"Found {len(interesting)} interesting JSON responses")

                if interesting:
                    print("\n✓ SUCCESS! We captured network data.")
                    print("Next steps:")
                    print("1. Review chatgpt_capture.json")
                    print("2. Look for search queries, URLs, snippets")
                    print("3. Update parser.py with the actual format")
                else:
                    print("\n⚠️  No large JSON responses found.")
                    print("The response might be:")
                    print("- Streaming (not captured by our method)")
                    print("- In a different format")
                    print("- Requires a different network capture approach")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 80)
        print("Keeping browser open for 10 seconds...")
        time.sleep(10)

        browser.close()


if __name__ == '__main__':
    try:
        capture_chatgpt_with_modals()
    except KeyboardInterrupt:
        print("\n\nCapture cancelled.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
