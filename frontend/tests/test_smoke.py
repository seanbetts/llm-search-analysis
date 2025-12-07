"""
Smoke tests to catch basic import errors.

These tests verify that all modules can be imported without errors.
This catches issues like missing dependencies, circular imports, and
architectural boundary violations (e.g., frontend importing backend code).
"""

import pytest

from frontend.tests.fixtures.send_prompt_responses import (
    api_send_prompt_response_namespace,
    network_log_send_prompt_response_namespace,
)


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
        - Frontend should NOT import from: backend/ (except data models)
        - Exception: frontend/network_capture can import backend data models
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

        # Allowed backend imports: data models for network_capture
        # network_capture runs client-side and needs to produce data in backend format
        allowed_imports = {
            'backend.app',
            'backend.app.services',
            'backend.app.services.providers',
            'backend.app.services.providers.base_provider',
            'backend.app.services.providers.provider_factory',
            'backend.app.api',
            'backend.app.api.v1',
            'backend.app.api.v1.schemas',
            'backend.app.api.v1.schemas.responses',
        }

        disallowed_imports = [imp for imp in backend_imports if imp not in allowed_imports]

        # If this test fails, it means frontend is importing backend services/business logic
        assert len(disallowed_imports) == 0, f"Frontend should only import backend data models. Found disallowed imports: {disallowed_imports}"


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
        response = api_send_prompt_response_namespace()

        metrics = compute_metrics(response.search_queries, response.citations)

        assert metrics['sources_found'] == response.sources_found
        assert metrics['sources_used'] == response.sources_used
        assert metrics['avg_rank'] == response.avg_rank
        assert metrics['extra_links_count'] == response.extra_links_count

    def test_compute_metrics_network_log_fallback(self):
        """Test that compute_metrics falls back to all_sources for network_log mode."""
        from frontend.helpers.metrics import compute_metrics
        response = network_log_send_prompt_response_namespace()

        metrics = compute_metrics(
            response.search_queries,
            response.citations,
            response.all_sources,
        )

        assert metrics['sources_found'] == response.sources_found
        assert metrics['sources_used'] == response.sources_used
        assert metrics['avg_rank'] == response.avg_rank
        assert metrics['extra_links_count'] == response.extra_links_count
