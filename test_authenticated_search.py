"""
Test authenticated ChatGPT search with login credentials.
"""

from src.network_capture.chatgpt_capturer import ChatGPTCapturer
from src.config import Config
import sys

# Check if credentials are available
if not Config.CHATGPT_EMAIL or not Config.CHATGPT_PASSWORD:
    print("=" * 80)
    print("ChatGPT credentials not found!")
    print("=" * 80)
    print()
    print("Please add to your .env file:")
    print("  CHATGPT_EMAIL=your_email@example.com")
    print("  CHATGPT_PASSWORD=your_password")
    print()
    sys.exit(1)

print("=" * 80)
print("Testing Authenticated ChatGPT Search")
print("=" * 80)
print()

# Create capturer
capturer = ChatGPTCapturer()

try:
    # Start browser (non-headless so we can see and interact if needed)
    print("Starting browser...")
    capturer.start_browser(headless=False)

    # Login with credentials
    print()
    print("Attempting login...")
    success = capturer.authenticate(
        email=Config.CHATGPT_EMAIL,
        password=Config.CHATGPT_PASSWORD
    )

    if not success:
        print("❌ Login failed")
        sys.exit(1)

    print()
    print("=" * 80)
    print("Login successful! Now testing search...")
    print("=" * 80)
    print()

    # Send a prompt with search
    prompt = "What happened in the news today?"
    print(f"Prompt: {prompt}")
    print()

    response = capturer.send_prompt(prompt, "chatgpt-free")

    print()
    print("=" * 80)
    print("Response received!")
    print("=" * 80)
    print()
    print(f"Response text: {response.response_text[:500]}...")
    print()
    print(f"Search queries: {len(response.search_queries)}")
    for query in response.search_queries:
        print(f"  - {query}")
    print()
    print(f"Sources: {len(response.sources)}")
    for source in response.sources[:5]:  # Show first 5
        print(f"  - {source.url}")
    print()
    print(f"Citations: {len(response.citations)}")
    for citation in response.citations[:5]:  # Show first 5
        print(f"  - {citation.url}")

    # Save captured network data for analysis
    print()
    print("=" * 80)
    print("Saving captured network data...")
    print("=" * 80)

    import json

    captured_responses = capturer.browser_manager.get_captured_responses()
    print(f"Total captured responses: {len(captured_responses)}")

    # Save event streams
    event_streams = [r for r in captured_responses
                     if 'event-stream' in r.get('content_type', '')]

    for idx, stream in enumerate(event_streams):
        filename = f'auth_event_stream_{idx + 1}.txt'
        with open(filename, 'w') as f:
            f.write(stream.get('body', ''))
        print(f"  Saved: {filename} ({len(stream.get('body', ''))} bytes)")

    # Save JSON responses
    json_responses = []
    for resp in captured_responses:
        if resp.get('body') and 'json' in resp.get('content_type', ''):
            try:
                data = json.loads(resp['body'])
                json_responses.append({
                    'url': resp['url'],
                    'data': data
                })
            except:
                pass

    for idx, jr in enumerate(json_responses):
        filename = f'auth_json_{idx + 1}.json'
        with open(filename, 'w') as f:
            json.dump(jr, f, indent=2)
        print(f"  Saved: {filename}")

    print(f"  Total event streams: {len(event_streams)}")
    print(f"  Total JSON responses: {len(json_responses)}")

    print()
    print("=" * 80)
    print("Test complete!")
    print("=" * 80)

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

finally:
    # Clean up
    print()
    print("Closing browser...")
    capturer.stop_browser()
