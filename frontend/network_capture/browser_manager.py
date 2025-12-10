"""Browser management utilities for network capture.

Handles browser lifecycle, session management, and network interception setup.
"""

import json
from typing import Callable, Optional


class BrowserManager:
    """Manager for browser automation and network interception.

    This class provides utilities for:
    - Browser lifecycle management
    - Network traffic interception
    - Session cookie management
    - Request/response filtering
    """

    def __init__(self):
        """Initialize browser manager."""
        self.browser = None
        self.context = None
        self.page = None
        self.intercepted_requests = []
        self.intercepted_responses = []

    def setup_network_interception(
        self,
        page,
        request_filter: Optional[Callable] = None,
        response_filter: Optional[Callable] = None
    ):
        """Set up network traffic interception on a page.

        Args:
            page: Playwright page object
            request_filter: Optional function to filter which requests to capture
            response_filter: Optional function to filter which responses to capture
        """
        def handle_request(request):
            """Handle outgoing requests."""
            if request_filter is None or request_filter(request):
                try:
                    post_data = request.post_data
                except Exception:
                    post_data = None

                self.intercepted_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'headers': request.headers,
                    'post_data': post_data
                })

        def handle_response(response):
            """Handle incoming responses."""
            if response_filter is None or response_filter(response):
                try:
                    body = response.body()
                    self.intercepted_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'headers': response.headers,
                        'body': body.decode('utf-8') if body else None,
                        'body_size': len(body) if body else 0,
                        'content_type': response.headers.get('content-type', '')
                    })
                except Exception as e:
                    # Some responses may not have decodable bodies
                    self.intercepted_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'headers': response.headers,
                        'body': None,
                        'body_size': 0,
                        'content_type': response.headers.get('content-type', ''),
                        'error': str(e)
                    })

        page.on('request', handle_request)
        page.on('response', handle_response)

    def get_captured_responses(self, url_pattern: str = None):
        """Get captured network responses, optionally filtered by URL pattern.

        Args:
            url_pattern: Optional substring to filter URLs

        Returns:
            List of captured response dictionaries
        """
        if url_pattern:
            return [
                resp for resp in self.intercepted_responses
                if url_pattern in resp['url']
            ]
        return self.intercepted_responses

    def clear_captured_data(self):
        """Clear all captured network data."""
        self.intercepted_requests = []
        self.intercepted_responses = []

    def save_session_cookies(self, context, file_path: str):
        """Save browser session cookies to file.

        Args:
            context: Playwright browser context
            file_path: Path to save cookies JSON
        """
        cookies = context.cookies()
        with open(file_path, 'w') as f:
            json.dump(cookies, f)

    def load_session_cookies(self, context, file_path: str):
        """Load browser session cookies from file.

        Args:
            context: Playwright browser context
            file_path: Path to cookies JSON file
        """
        try:
            with open(file_path, 'r') as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False
