# LLM Search Analysis

A Streamlit application to monitor and analyze how different LLM models (OpenAI, Google, Anthropic) use web search and tool-calling capabilities.

## Features

- **Interactive Prompting**: Test individual prompts and see detailed search behavior
- **Batch Analysis**: Analyze multiple prompts at once with summary statistics
- **Query History**: Browse and export past queries and results

## Supported Models

- `gpt-5.1` (OpenAI)
- `claude-sonnet-4.5` (Anthropic)
- `gemini-3.0` (Google)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd llm-search-analysis
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

5. Run the application:
```bash
streamlit run app.py
```

## Project Structure

```
llm-search-analysis/
├── app.py                      # Main Streamlit application
├── src/
│   ├── providers/              # Provider implementations
│   │   ├── base_provider.py
│   │   ├── provider_factory.py
│   │   ├── openai_provider.py
│   │   ├── google_provider.py
│   │   └── anthropic_provider.py
│   ├── parser.py               # Response parsing
│   ├── database.py             # Database models
│   └── analyzer.py             # Statistics
├── tests/                      # Test files
├── data/                       # SQLite database (gitignored)
└── requirements.txt
```

## Environment Variables

Required environment variables (see `.env.example`):

- `OPENAI_API_KEY`: Your OpenAI API key
- `GOOGLE_API_KEY`: Your Google AI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `DATABASE_URL`: SQLite database path

## Development Status

This is currently a beta/MVP application focused on core functionality. See `llm-search-analysis-plan.md` for the full roadmap and future enhancements.

## License

MIT
