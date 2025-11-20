# LLM Search Analysis

A comparative analysis tool for evaluating web search capabilities across OpenAI, Google Gemini, and Anthropic Claude models.

## Overview

This tool provides an interactive web interface to test and analyze how different LLM providers:
- Formulate search queries from user prompts
- Fetch web sources during the search process
- Cite information in their responses

## Features

- **Multi-Provider Support**: OpenAI (Responses API), Google Gemini (Search Grounding), Anthropic Claude (Web Search Tool)
- **9 Models**: Test across 9 different AI models with varying capabilities
- **Detailed Analytics**: View search queries, sources fetched, citations used, and response times
- **Interactive UI**: Clean Streamlit interface for easy testing and comparison

## Installation

### Prerequisites

- Python 3.8+
- API keys for at least one provider (OpenAI, Google AI, Anthropic)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd llm-search-analysis
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:
```bash
# .env
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

## Usage

### Running the Web Interface

Start the Streamlit app:
```bash
streamlit run app.py
```

The interface will open in your browser at `http://localhost:8501`.

### Using the Interface

1. **Select Provider**: Choose from OpenAI, Google Gemini, or Anthropic Claude
2. **Select Model**: Pick a specific model from the dropdown
3. **Enter Prompt**: Type a question that requires current information
4. **Submit Query**: Click the submit button to get results

### Example Prompts

- "What are the latest developments in artificial intelligence this week?"
- "Who won the 2024 NBA championship?"
- "What are the current stock market trends?"

## Supported Models

### OpenAI
- gpt-5.1
- gpt-5-mini
- gpt-5-nano

### Google Gemini
- gemini-3-pro-preview
- gemini-2.5-flash
- gemini-2.5-flash-lite

### Anthropic Claude
- claude-sonnet-4-5-20250929
- claude-haiku-4-5-20251001
- claude-opus-4-1-20250805

## Project Structure

```
llm-search-analysis/
├── app.py                      # Streamlit web interface
├── src/
│   ├── config.py              # Configuration and API key management
│   ├── providers/
│   │   ├── base_provider.py   # Abstract base class
│   │   ├── openai_provider.py # OpenAI implementation
│   │   ├── google_provider.py # Google Gemini implementation
│   │   ├── anthropic_provider.py # Anthropic Claude implementation
│   │   └── provider_factory.py # Provider factory
│   └── database.py            # Database schema (SQLAlchemy)
├── tests/                     # Unit tests
├── verify_providers.py        # API verification script
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Development

### Running Tests

Run the full test suite:
```bash
pytest tests/ -v
```

Run provider verification:
```bash
python verify_providers.py
```

### Adding a New Provider

1. Create a new provider class in `src/providers/` that inherits from `BaseProvider`
2. Implement required methods: `send_prompt()`, `get_supported_models()`, `get_provider_name()`
3. Add the provider to `ProviderFactory` in `src/providers/provider_factory.py`
4. Add tests in `tests/test_providers/`

## API Documentation

### OpenAI Responses API
- Uses the `/v1/responses` endpoint with `web_search` tool
- Requires `include=["web_search_call.action.sources"]` parameter

### Google Gemini Search Grounding
- Uses the `google-genai` SDK with `Tool(google_search=GoogleSearch())`
- Extracts data from `grounding_metadata`

### Anthropic Claude Web Search
- Uses native `web_search_20250305` tool powered by Brave Search
- Parses `server_tool_use` and `web_search_tool_result` content blocks

## Troubleshooting

### API Key Issues
- Verify your `.env` file is in the project root
- Check that API keys are valid and have sufficient credits
- Ensure no extra spaces or quotes around the keys

### Import Errors
- Run `pip install -r requirements.txt` to ensure all dependencies are installed
- Verify you're using Python 3.8 or later

### Streamlit Issues
- Clear cache: `streamlit cache clear`
- Restart the app: Stop with Ctrl+C and run `streamlit run app.py` again

## Phase Status

✅ **Phase 1: Backend Implementation** - Complete
- Provider abstraction layer
- OpenAI, Google, Anthropic integrations
- Web search functionality
- Unit tests (52 passing)
- API verification (9/9 models working)

✅ **Phase 2: Streamlit UI** - Complete
- Interactive web interface
- Provider and model selection
- Results display with search metadata
- Error handling

🚧 **Phase 3: Data Collection** - Not Started
- Run systematic tests
- Collect comparison data
- Store results in SQLite database

🚧 **Phase 4: Visualization** - Not Started
- Add data visualization
- Compare providers side-by-side
- Generate insights

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
