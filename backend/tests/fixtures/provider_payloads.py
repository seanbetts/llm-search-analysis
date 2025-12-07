"""Sample provider payloads used to test schema validation."""

OPENAI_RESPONSE = {
  "id": "resp_sample_123",
  "model": "gpt-5.1",
  "output": [
    {
      "type": "web_search_call",
      "status": "completed",
      "action": {
        "type": "search",
        "query": "latest ai news",
        "sources": [
          {"type": "url", "url": "https://example.com/one", "title": "Example One"},
          {"type": "url", "url": "https://example.com/two", "title": "Example Two"},
        ]
      }
    },
    {
      "type": "message",
      "status": "completed",
      "content": [
        {
          "type": "output_text",
          "text": "AI summary",
          "annotations": [
            {"type": "url_citation", "url": "https://example.com/one", "title": "Example One"}
          ]
        }
      ]
    }
  ]
}

OPENAI_INVALID = {
  "id": "resp_invalid",
  "model": "gpt-5.1",
  "output": "not-a-list"
}

ANTHROPIC_RESPONSE = {
  "id": "msg_sample_123",
  "model": "claude-sonnet-4-5-20250929",
  "content": [
    {
      "type": "text",
      "text": "Response body",
      "citations": [
        {"url": "https://example.com/article", "title": "Example Article"}
      ]
    },
    {
      "type": "server_tool_use",
      "name": "web_search",
      "input": {"query": "latest ai news"}
    },
    {
      "type": "web_search_tool_result",
      "content": [
        {"url": "https://example.com/article", "title": "Example Article"}
      ]
    }
  ]
}

ANTHROPIC_INVALID = {
  "id": "msg_invalid",
  "content": "not-a-list"
}

GOOGLE_RESPONSE = {
  "text": "Gemini answer",
  "candidates": [
    {
      "grounding_metadata": {
        "web_search_queries": ["query one"],
        "grounding_chunks": [
          {"web": {"uri": "https://example.com/one", "title": "Example One"}}
        ]
      }
    }
  ]
}

GOOGLE_INVALID = {
  "text": "Gemini answer",
  "candidates": "invalid"
}
