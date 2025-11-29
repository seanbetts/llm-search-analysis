import json
from pathlib import Path

from src.network_capture.parser import NetworkLogParser


FIXTURE_PATH = Path("data/network_logs/chatgpt_test_20251129_114241.json")


def test_parse_chatgpt_log_fixture():
    """Ensure ChatGPT network log parsing extracts queries, sources, and metadata."""
    fixture = json.loads(FIXTURE_PATH.read_text())

    response = NetworkLogParser.parse_chatgpt_log(
        network_response=fixture,
        model="chatgpt-free",
        response_time_ms=0,
        extracted_response_text=""
    )

    # Model info
    assert "gpt-5" in response.model
    assert response.metadata is not None
    assert response.metadata.get("classifier") is not None

    # Queries
    assert len(response.search_queries) >= 1
    assert response.search_queries[0].query == "today news UK"
    assert response.search_queries[0].order_index == 0

    # Sources
    assert len(response.sources) > 0
    first_source = response.sources[0]
    assert first_source.url
    assert first_source.rank == 1
    assert first_source.pub_date is None or first_source.pub_date.startswith("2025-")

    # Safe URLs captured
    assert isinstance(response.metadata.get("safe_urls"), list)

    # Citations from streamed markers
    assert len(response.citations) > 0
    assert response.metadata.get("citation_ids")
