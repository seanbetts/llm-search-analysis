"""
Basic statistics and analysis functions.
"""

from typing import List, Dict
from collections import Counter
import pandas as pd


class Analyzer:
    """Basic statistics analyzer for search data."""

    @staticmethod
    def calculate_batch_stats(results: List[Dict]) -> Dict:
        """
        Calculate summary statistics for batch analysis.

        Args:
            results: List of result dictionaries from batch processing

        Returns:
            Dictionary with summary statistics
        """
        if not results:
            return {
                "total_prompts": 0,
                "total_searches": 0,
                "avg_sources": 0,
                "avg_citations": 0,
            }

        total_prompts = len(results)
        total_searches = sum(len(r.get("search_queries", [])) for r in results)
        total_sources = sum(len(r.get("sources", [])) for r in results)
        total_citations = sum(len(r.get("citations", [])) for r in results)

        return {
            "total_prompts": total_prompts,
            "total_searches": total_searches,
            "avg_sources": round(total_sources / total_prompts, 2) if total_prompts > 0 else 0,
            "avg_citations": round(total_citations / total_prompts, 2) if total_prompts > 0 else 0,
        }

    @staticmethod
    def get_top_domains(results: List[Dict], top_n: int = 10) -> List[tuple]:
        """
        Get the most common domains from batch results.

        Args:
            results: List of result dictionaries
            top_n: Number of top domains to return

        Returns:
            List of tuples (domain, count) sorted by count
        """
        domains = []
        for result in results:
            for source in result.get("sources", []):
                if source.domain:
                    domains.append(source.domain)

        if not domains:
            return []

        domain_counts = Counter(domains)
        return domain_counts.most_common(top_n)

    @staticmethod
    def prepare_export_data(results: List[Dict]) -> pd.DataFrame:
        """
        Prepare results for CSV export.

        Args:
            results: List of result dictionaries

        Returns:
            pandas DataFrame ready for export
        """
        export_data = []

        for result in results:
            export_data.append({
                "prompt": result.get("prompt", ""),
                "model": result.get("model", ""),
                "provider": result.get("provider", ""),
                "num_searches": len(result.get("search_queries", [])),
                "num_sources": len(result.get("sources", [])),
                "num_citations": len(result.get("citations", [])),
                "response_time_ms": result.get("response_time_ms", 0),
                "response_preview": (result.get("response_text", "")[:100] + "...")
                                  if len(result.get("response_text", "")) > 100
                                  else result.get("response_text", ""),
            })

        return pd.DataFrame(export_data)

    @staticmethod
    def format_domain_chart_data(domain_counts: List[tuple]) -> Dict:
        """
        Format domain data for Plotly bar chart.

        Args:
            domain_counts: List of (domain, count) tuples

        Returns:
            Dictionary with x and y data for plotting
        """
        if not domain_counts:
            return {"domains": [], "counts": []}

        domains = [d[0] for d in domain_counts]
        counts = [d[1] for d in domain_counts]

        return {
            "domains": domains,
            "counts": counts
        }
