"""
Test authenticated ChatGPT search with login credentials.
"""

from src.network_capture.chatgpt_capturer import ChatGPTCapturer
from src.database import Database
from src.config import Config
import sys
import json
from datetime import datetime
from pathlib import Path

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

    # Save raw network logs to file
    print()
    print("=" * 80)
    print("Saving raw network logs...")
    print("=" * 80)

    # Create logs directory if it doesn't exist
    logs_dir = Path("data/network_logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"chatgpt_test_{timestamp}.json"

    # Save raw response
    with open(log_file, 'w') as f:
        json.dump(response.raw_response, f, indent=2, default=str)

    print(f"✓ Raw network logs saved to: {log_file}")
    print(f"  File size: {log_file.stat().st_size / 1024:.1f} KB")

    # Save to database
    print()
    print("=" * 80)
    print("Saving to database...")
    print("=" * 80)

    db = Database()
    db.create_tables()
    db.ensure_providers()

    try:
        interaction_id = db.save_interaction(
            provider_name='openai',
            model='chatgpt-free',
            prompt=prompt,
            response_text=response.response_text,
            search_queries=response.search_queries,
            sources=response.sources,
            citations=response.citations,
            response_time_ms=response.response_time_ms,
            raw_response=response.raw_response,
            data_source='network_log'
        )
        print(f"✓ Saved to database with ID: {interaction_id}")
        print(f"  - Search queries: {len(response.search_queries)}")
        print(f"  - Sources: {len(response.sources)}")
        print(f"  - Citations: {len(response.citations)}")
    except Exception as db_error:
        print(f"✗ Database save failed: {str(db_error)}")
        import traceback
        traceback.print_exc()

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
