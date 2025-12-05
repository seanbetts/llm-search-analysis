"""
Smoke tests to catch basic import errors.

These tests verify that all modules can be imported without errors.
This catches issues like missing dependencies, circular imports, and
architectural boundary violations (e.g., frontend importing backend code).
"""

import pytest


class TestImports:
    """Test that all modules can be imported successfully."""

    def test_import_app(self):
        """Test that the main app module can be imported."""
        # This catches import errors in the full module chain
        import app
        assert hasattr(app, '__file__')

    def test_import_frontend_tabs(self):
        """Test that all frontend tab modules can be imported."""
        from frontend.tabs import tab_interactive, tab_batch, tab_history
        assert callable(tab_interactive)
        assert callable(tab_batch)
        assert callable(tab_history)

    def test_import_frontend_components(self):
        """Test that all frontend components can be imported."""
        from frontend.components import models, response
        assert hasattr(models, 'get_all_models')
        assert hasattr(response, 'display_response')

    def test_import_frontend_helpers(self):
        """Test that all frontend helpers can be imported."""
        from frontend.helpers.metrics import compute_metrics, get_model_display_name
        assert callable(compute_metrics)
        assert callable(get_model_display_name)

    def test_import_frontend_api_client(self):
        """Test that API client can be imported."""
        from frontend.api_client import APIClient, APINotFoundError, APIClientError
        assert APIClient is not None
        assert APINotFoundError is not None
        assert APIClientError is not None

    def test_no_backend_imports_in_frontend(self):
        """
        Test that frontend doesn't import from backend.

        This enforces the architectural boundary:
        - Frontend should only import from: frontend/, src/
        - Frontend should NOT import from: backend/
        """
        # Import all frontend modules
        import frontend.tabs.interactive
        import frontend.tabs.batch
        import frontend.tabs.history
        import frontend.components.models
        import frontend.components.response
        import frontend.helpers.metrics

        # Check that no backend imports leaked in
        import sys
        backend_imports = [name for name in sys.modules.keys() if name.startswith('backend.') or name.startswith('app.')]

        # The only backend import allowed is through API client (which uses HTTP, not Python imports)
        # If this test fails, it means frontend is directly importing backend Python modules
        assert len(backend_imports) == 0, f"Frontend should not import backend modules. Found: {backend_imports}"


class TestFunctionality:
    """Test that key functions work correctly."""

    def test_get_model_display_name(self):
        """Test that get_model_display_name works correctly."""
        from frontend.helpers.metrics import get_model_display_name

        # Test known models
        assert get_model_display_name('gpt-5-1') == 'GPT-5.1'
        assert get_model_display_name('gpt-5.1') == 'GPT-5.1'
        assert get_model_display_name('chatgpt-free') == 'ChatGPT (Free)'
        assert get_model_display_name('claude-sonnet-4-5-20250929') == 'Claude Sonnet 4.5'

        # Test unknown model fallback
        result = get_model_display_name('unknown-model-name')
        assert result == 'Unknown Model Name'

    def test_compute_metrics(self):
        """Test that compute_metrics works correctly."""
        from frontend.helpers.metrics import compute_metrics
        from types import SimpleNamespace

        # Create test data
        search_queries = [
            SimpleNamespace(
                query='test query',
                sources=[
                    SimpleNamespace(url='https://example.com/1'),
                    SimpleNamespace(url='https://example.com/2'),
                ]
            )
        ]

        citations = [
            SimpleNamespace(rank=1, url='https://example.com/1'),
            SimpleNamespace(rank=2, url='https://example.com/2'),
            SimpleNamespace(rank=None, url='https://example.com/3'),  # Extra link
        ]

        metrics = compute_metrics(search_queries, citations)

        assert metrics['sources_found'] == 2
        assert metrics['sources_used'] == 2
        assert metrics['avg_rank'] == 1.5
        assert metrics['extra_links_count'] == 1

    def test_compute_metrics_network_log_fallback(self):
        """Test that compute_metrics falls back to all_sources for network_log mode."""
        from frontend.helpers.metrics import compute_metrics
        from types import SimpleNamespace

        # Simulate network_log mode: search_queries exist but have no sources
        search_queries = [SimpleNamespace(query='test', sources=[])]

        citations = [
            SimpleNamespace(rank=1, url='https://example.com/1'),
            SimpleNamespace(rank=2, url='https://example.com/2'),
        ]

        all_sources = [
            SimpleNamespace(url='https://example.com/1'),
            SimpleNamespace(url='https://example.com/2'),
            SimpleNamespace(url='https://example.com/3'),
        ]

        # Should use all_sources since search_queries have no sources
        metrics = compute_metrics(search_queries, citations, all_sources)

        assert metrics['sources_found'] == 3  # From all_sources, not 0!
        assert metrics['sources_used'] == 2
        assert metrics['avg_rank'] == 1.5
        assert metrics['extra_links_count'] == 0
