"""
Tests for analyzer module.
"""

import pytest
import pandas as pd
from unittest.mock import Mock
from src.analyzer import Analyzer
from src.providers.base_provider import SearchQuery, Source, Citation


class TestAnalyzer:
    """Test suite for Analyzer."""

    def test_calculate_batch_stats_empty(self):
        """Test calculate_batch_stats with empty results."""
        stats = Analyzer.calculate_batch_stats([])

        assert stats["total_prompts"] == 0
        assert stats["total_searches"] == 0
        assert stats["avg_sources"] == 0
        assert stats["avg_citations"] == 0

    def test_calculate_batch_stats_single_result(self):
        """Test calculate_batch_stats with single result."""
        results = [{
            "search_queries": [SearchQuery(query="test")],
            "sources": [Source(url="http://example.com", domain="example.com")],
            "citations": [Citation(url="http://example.com")],
        }]

        stats = Analyzer.calculate_batch_stats(results)

        assert stats["total_prompts"] == 1
        assert stats["total_searches"] == 1
        assert stats["avg_sources"] == 1.0
        assert stats["avg_citations"] == 1.0

    def test_calculate_batch_stats_multiple_results(self):
        """Test calculate_batch_stats with multiple results."""
        results = [
            {
                "search_queries": [SearchQuery(query="q1"), SearchQuery(query="q2")],
                "sources": [Source(url="http://ex1.com", domain="ex1.com")],
                "citations": [Citation(url="http://ex1.com")],
            },
            {
                "search_queries": [SearchQuery(query="q3")],
                "sources": [
                    Source(url="http://ex2.com", domain="ex2.com"),
                    Source(url="http://ex3.com", domain="ex3.com")
                ],
                "citations": [],
            },
        ]

        stats = Analyzer.calculate_batch_stats(results)

        assert stats["total_prompts"] == 2
        assert stats["total_searches"] == 3  # 2 + 1
        assert stats["avg_sources"] == 1.5  # (1 + 2) / 2
        assert stats["avg_citations"] == 0.5  # (1 + 0) / 2

    def test_get_top_domains_empty(self):
        """Test get_top_domains with empty results."""
        domains = Analyzer.get_top_domains([])
        assert domains == []

    def test_get_top_domains_single_domain(self):
        """Test get_top_domains with single domain."""
        results = [{
            "sources": [
                Source(url="http://example.com/1", domain="example.com"),
                Source(url="http://example.com/2", domain="example.com"),
            ]
        }]

        domains = Analyzer.get_top_domains(results, top_n=10)

        assert len(domains) == 1
        assert domains[0] == ("example.com", 2)

    def test_get_top_domains_multiple_domains(self):
        """Test get_top_domains with multiple domains."""
        results = [{
            "sources": [
                Source(url="http://a.com", domain="a.com"),
                Source(url="http://b.com", domain="b.com"),
                Source(url="http://a.com/2", domain="a.com"),
                Source(url="http://c.com", domain="c.com"),
                Source(url="http://a.com/3", domain="a.com"),
            ]
        }]

        domains = Analyzer.get_top_domains(results, top_n=2)

        assert len(domains) == 2
        assert domains[0] == ("a.com", 3)  # Most common
        assert domains[1][0] in ["b.com", "c.com"]  # Second most common

    def test_prepare_export_data_empty(self):
        """Test prepare_export_data with empty results."""
        df = Analyzer.prepare_export_data([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_prepare_export_data_single_result(self):
        """Test prepare_export_data with single result."""
        results = [{
            "prompt": "test prompt",
            "model": "gpt-5.1",
            "provider": "openai",
            "search_queries": [SearchQuery(query="q1")],
            "sources": [Source(url="http://ex.com", domain="ex.com")],
            "citations": [Citation(url="http://ex.com")],
            "response_time_ms": 1000,
            "response_text": "test response"
        }]

        df = Analyzer.prepare_export_data(results)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["prompt"] == "test prompt"
        assert df.iloc[0]["model"] == "gpt-5.1"
        assert df.iloc[0]["provider"] == "openai"
        assert df.iloc[0]["num_searches"] == 1
        assert df.iloc[0]["num_sources"] == 1
        assert df.iloc[0]["num_citations"] == 1

    def test_prepare_export_data_long_response(self):
        """Test prepare_export_data truncates long responses."""
        long_text = "a" * 200
        results = [{
            "prompt": "test",
            "model": "gpt-5.1",
            "provider": "openai",
            "search_queries": [],
            "sources": [],
            "citations": [],
            "response_time_ms": 500,
            "response_text": long_text
        }]

        df = Analyzer.prepare_export_data(results)

        response_preview = df.iloc[0]["response_preview"]
        assert len(response_preview) == 103  # 100 chars + "..."
        assert response_preview.endswith("...")

    def test_format_domain_chart_data_empty(self):
        """Test format_domain_chart_data with empty input."""
        chart_data = Analyzer.format_domain_chart_data([])

        assert chart_data["domains"] == []
        assert chart_data["counts"] == []

    def test_format_domain_chart_data(self):
        """Test format_domain_chart_data with domain counts."""
        domain_counts = [
            ("example.com", 5),
            ("test.com", 3),
            ("demo.com", 1),
        ]

        chart_data = Analyzer.format_domain_chart_data(domain_counts)

        assert chart_data["domains"] == ["example.com", "test.com", "demo.com"]
        assert chart_data["counts"] == [5, 3, 1]
