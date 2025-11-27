"""
Quick test to see if we can access free ChatGPT and what the UI looks like.
"""

from playwright.sync_api import sync_playwright
import time


def test_chatgpt_access():
    """Test accessing ChatGPT and inspecting the page."""

    print("Testing ChatGPT access...")

    with sync_playwright() as p:
        # Launch browser (visible so we can see what happens)
        print("Launching browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to ChatGPT
        print("Navigating to https://chatgpt.com...")
        page.goto('https://chatgpt.com', wait_until='networkidle')

        print("\nPage loaded. Waiting 5 seconds...")
        time.sleep(5)

        # Check page title
        title = page.title()
        print(f"Page title: {title}")

        # Try to find common UI elements
        print("\nLooking for UI elements...")

        # Check for textarea (prompt input)
        textareas = page.locator('textarea').all()
        print(f"Found {len(textareas)} textarea elements")

        # Check for buttons
        buttons = page.locator('button').all()
        print(f"Found {len(buttons)} button elements")

        # Check for input fields
        inputs = page.locator('input').all()
        print(f"Found {len(inputs)} input elements")

        # Try to get page content
        print("\nPage snapshot (first 500 chars):")
        content = page.content()
        print(content[:500])

        print("\n" + "=" * 80)
        print("Browser will stay open for manual inspection.")
        print("Check if:")
        print("1. ChatGPT loads without login requirement")
        print("2. You see a prompt input box")
        print("3. You can submit a prompt")
        print("\nPress Enter when done inspecting...")
        input()

        browser.close()


if __name__ == '__main__':
    try:
        test_chatgpt_access()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
