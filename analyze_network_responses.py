"""
Capture and analyze network responses to understand ChatGPT search data format.
"""

from src.network_capture.chatgpt_capturer import ChatGPTCapturer
import json
import time

print("="*80)
print("Capturing Network Responses for Analysis")
print("="*80)
print()

capturer = ChatGPTCapturer()
capturer.start_browser(headless=False)
capturer.authenticate()

print("✓ Browser launched (Chrome)")
print()

# Enable search and submit prompt
print("🔍 Enabling search...")
capturer._enable_search_toggle()

print("📝 Typing prompt...")
textarea = capturer._find_textarea()
prompt = "What happened in the news today?"
textarea.fill(prompt)

print("📤 Submitting prompt...")
capturer._submit_prompt(textarea)

print("⏳ Waiting for response...")
capturer._wait_for_response_complete(max_wait=90)

print()
print("="*80)
print(f"Captured {len(capturer.browser_manager.intercepted_responses)} network responses")
print("="*80)
print()

# Analyze responses
responses_by_type = {}
for resp in capturer.browser_manager.intercepted_responses:
    url = resp['url']
    content_type = resp.get('content_type', 'unknown')

    # Categorize by URL pattern
    if 'conversation' in url:
        category = 'conversation'
    elif 'backend-anon' in url:
        category = 'backend-anon'
    elif 'search' in url.lower():
        category = 'search'
    elif 'event-stream' in content_type or 'text/event-stream' in content_type:
        category = 'event-stream'
    else:
        category = 'other'

    if category not in responses_by_type:
        responses_by_type[category] = []
    responses_by_type[category].append(resp)

print("Response categories:")
for category, resps in responses_by_type.items():
    print(f"  {category}: {len(resps)} responses")
print()

# Save detailed analysis
analysis = {
    'total_responses': len(capturer.browser_manager.intercepted_responses),
    'categories': {cat: len(resps) for cat, resps in responses_by_type.items()},
    'responses': []
}

# Add detailed info for each response
for idx, resp in enumerate(capturer.browser_manager.intercepted_responses):
    response_info = {
        'index': idx,
        'url': resp['url'],
        'status': resp.get('status'),
        'content_type': resp.get('content_type', 'unknown'),
        'body_size': resp.get('body_size', 0),
        'has_body': resp.get('body') is not None,
        'body_preview': None
    }

    # Add body preview for interesting responses
    if resp.get('body'):
        body = resp['body']
        if len(body) < 1000:
            response_info['body_full'] = body
        else:
            response_info['body_preview'] = body[:500] + '...'

    analysis['responses'].append(response_info)

# Save to file
output_file = 'network_analysis.json'
with open(output_file, 'w') as f:
    json.dump(analysis, f, indent=2)

print(f"✓ Saved analysis to {output_file}")
print()

# Look for event-stream responses (most likely to contain search data)
event_streams = [r for r in capturer.browser_manager.intercepted_responses
                 if 'event-stream' in r.get('content_type', '')]

if event_streams:
    print("="*80)
    print(f"Found {len(event_streams)} event-stream responses")
    print("="*80)
    print()

    for idx, stream in enumerate(event_streams):
        print(f"Event Stream {idx + 1}:")
        print(f"  URL: {stream['url']}")
        print(f"  Size: {stream.get('body_size', 0)} bytes")

        if stream.get('body'):
            # Save event stream to separate file
            stream_file = f'event_stream_{idx + 1}.txt'
            with open(stream_file, 'w') as f:
                f.write(stream['body'])
            print(f"  Saved to: {stream_file}")
        print()

# Look for JSON responses that might contain search data
json_responses = []
for resp in capturer.browser_manager.intercepted_responses:
    if resp.get('body') and resp.get('content_type', '').startswith('application/json'):
        try:
            data = json.loads(resp['body'])
            json_responses.append({
                'url': resp['url'],
                'data': data
            })
        except:
            pass

if json_responses:
    print("="*80)
    print(f"Found {len(json_responses)} JSON responses")
    print("="*80)
    print()

    for idx, jr in enumerate(json_responses):
        print(f"JSON Response {idx + 1}:")
        print(f"  URL: {jr['url']}")

        # Save to file
        json_file = f'json_response_{idx + 1}.json'
        with open(json_file, 'w') as f:
            json.dump(jr['data'], f, indent=2)
        print(f"  Saved to: {json_file}")

        # Print keys to see structure
        if isinstance(jr['data'], dict):
            print(f"  Keys: {list(jr['data'].keys())}")
        print()

print("="*80)
print("Analysis complete!")
print("="*80)
print()
print("Check these files:")
print("  - network_analysis.json (overview)")
print("  - event_stream_*.txt (streaming responses)")
print("  - json_response_*.json (JSON data)")
print()

capturer.stop_browser()
print("✓ Done!")
