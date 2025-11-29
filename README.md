# LLM Search Analysis

A comparative analysis tool for evaluating web search capabilities across OpenAI, Google Gemini, and Anthropic Claude models.

## Overview

This tool provides an interactive web interface to test and analyze how different LLM providers:
- Formulate search queries from user prompts
- Fetch web sources during the search process
- Cite information in their responses

## Features

### Core Capabilities
- **Multi-Provider Support**: OpenAI (Responses API), Google Gemini (Search Grounding), Anthropic Claude (Web Search Tool)
- **9 Models**: Test across 9 different AI models with varying capabilities
- **Dual Data Collection Modes**: API-based (structured data) and Network Capture (browser automation)
- **3-Tab Interface**: Interactive prompting, batch analysis, and query history
- **Database Integration**: SQLite-based persistence for all interactions
- **Rank Tracking**: Monitor which search result positions sources come from (1-indexed)

### Tab 1: Interactive Prompting
- Single-prompt testing with real-time results
- Detailed search queries grouped with their sources
- Sources used (citations) with rank positions
- Response metadata: searches, sources, sources used, average rank, response time

### Tab 2: Batch Analysis
- **Multi-model comparison**: Test multiple models simultaneously
- Bulk prompt processing (text area or CSV upload)
- Progress tracking: prompts × models = total runs
- Comprehensive metrics: Total Runs, Avg Sources, Avg Sources Used, Avg Rank
- CSV export with full results

### Tab 3: Query History
- Browse all past interactions (last 100)
- Search/filter by keywords
- Sortable columns with average rank tracking
- Detailed interaction view with full metrics
- CSV export functionality

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
# API Keys (for API mode)
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# ChatGPT Credentials (for Network Capture mode - optional)
CHATGPT_EMAIL=your_email@example.com
CHATGPT_PASSWORD=your_password_here
```

### Network Capture Mode Setup (Optional)

For capturing ChatGPT interactions via browser automation:

1. Install Playwright with Chrome browser:
```bash
pip install playwright playwright-stealth
python -m playwright install chrome
```

**Important:** Use Chrome (not Chromium). OpenAI detects Chromium browsers and serves a degraded UI without the Search button.

2. Configure ChatGPT authentication in `.env` file:
```bash
# Required for ChatGPT network capture
CHATGPT_EMAIL=your_email@example.com
CHATGPT_PASSWORD=your_password_here
```

**Session Persistence:**
- Login state is saved to `data/chatgpt_session.json` (single JSON file, ~190KB)
- Subsequent runs skip authentication if session is valid
- Sessions are automatically saved after successful login

3. **Requirements & Notes:**
   - **Chrome Required**: Must use Chrome browser (not Chromium) - Chromium is detected
   - **Non-Headless Only**: Headless mode triggers Cloudflare CAPTCHA
   - **Stealth Mode**: playwright-stealth library required for detection bypass
   - **Authentication**: Requires ChatGPT account credentials in .env file
   - **Search Enablement**: Uses `/search` command + menu fallback (Add → More → Web search)

4. **Current Status:**
   - ✅ Chrome browser bypasses detection successfully
   - ✅ Session persistence with automatic login/restore
   - ✅ Web search enablement via /search command
   - ✅ Fallback menu navigation for search toggle
   - ✅ Response text extraction with inline citations
   - ⚠️ Known Issue: ChatGPT free tier search execution unreliable (platform issue, bug filed)

## Usage

### Running the Web Interface

Start the Streamlit app:
```bash
streamlit run app.py
```

The interface will open in your browser at `http://localhost:8501`.

### Data Collection Modes

The tool supports two data collection modes:

**API Mode (Default)**
- Uses official provider APIs (OpenAI Responses API, Google Gemini, Anthropic Claude)
- Structured data with full search metadata
- Supports all 9 models
- Requires API keys

**Network Capture Mode (Experimental)**
- Browser automation with Playwright
- Captures ChatGPT interactions via network traffic
- Currently limited due to browser detection
- Only supports ChatGPT (Free) model
- Requires Chrome browser (not Chromium)

Toggle between modes in the sidebar: "Data Collection Mode"

### Using the Interface

#### Tab 1: Interactive Prompting
1. **Select Data Mode**: Choose "API" or "Network Log" mode
2. **Select Model**: Choose from 9 models (API mode) or ChatGPT Free (Network mode)
3. **Enter Prompt**: Type a question that requires current information
4. **Send**: Click to get results with detailed search analytics
5. **View Results**: See search queries, sources fetched, sources used, and ranks

#### Tab 2: Batch Analysis
1. **Select Models**: Choose one or more models to compare
2. **Enter Prompts**: Type multiple prompts (one per line) or upload CSV
3. **Run**: Process all prompt × model combinations
4. **Export**: Download results as CSV with full metrics

#### Tab 3: Query History
1. **Browse**: View last 100 interactions with sortable columns
2. **Search**: Filter by keywords in prompts
3. **Details**: Click to view full interaction details
4. **Export**: Download filtered results as CSV

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
├── app.py                      # Streamlit web interface (3 tabs)
├── src/
│   ├── config.py              # Configuration and API key management
│   ├── database.py            # SQLAlchemy models and operations
│   ├── analyzer.py            # Statistical analysis functions
│   ├── providers/
│   │   ├── base_provider.py   # Abstract base class
│   │   ├── provider_factory.py # Provider selection
│   │   ├── openai_provider.py # OpenAI Responses API
│   │   ├── google_provider.py # Google Gemini with search grounding
│   │   └── anthropic_provider.py # Anthropic Claude web search
│   └── network_capture/       # Browser automation (experimental)
│       ├── browser_manager.py # Playwright browser control
│       ├── chatgpt_capturer.py # ChatGPT interaction capture
│       └── parser.py          # Network log parsing
├── tests/                     # Unit tests and validation scripts
│   ├── verify_providers.py   # API verification script
│   ├── test_rank_feature.py  # Rank tracking validation
│   └── ... (52 passing tests)
├── llm_search_analysis.db     # SQLite database (auto-created)
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

### Database Schema

**Tables:**
- `providers` - AI provider metadata (OpenAI, Google, Anthropic)
- `sessions` - Provider session information
- `prompts` - User prompts
- `responses` - Model responses with timing data
- `search_queries` - Search queries generated by models
- `sources` - Sources fetched during search (with rank)
- `sources_used` - Sources actually cited in responses (with rank)

## Development

### Running Tests

Run the full test suite:
```bash
pytest tests/ -v
```

Run provider verification:
```bash
python tests/verify_providers.py
```

Test rank tracking feature:
```bash
python tests/test_rank_feature.py
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

### Network Capture Mode Issues

**Cloudflare CAPTCHA Blocking:**
- Occurs when using headless mode
- Solution: Use non-headless mode (headless=False)
- Note: This is intentional - headless triggers bot detection

**Degraded UI / No Search Button:**
- Cause: Using Chromium browser (detected by OpenAI)
- Solution: Use Chrome browser with `channel='chrome'` parameter
- Install: `python -m playwright install chrome`
- Result: ✅ Chrome successfully bypasses detection - Search button accessible

**Browser Not Found:**
- Install Playwright browsers: `python -m playwright install chrome`
- Verify installation: `playwright show browsers`

**Stealth Mode Not Applied:**
- Install playwright-stealth: `pip install playwright-stealth`
- Ensure using correct Python environment (check with `which python`)

**ChatGPT Search Not Executing:**
- Issue: Web search mode can be enabled, but ChatGPT doesn't always execute searches
- Cause: Platform issue with ChatGPT free tier (bug filed with OpenAI)
- Status: Search mode activation works correctly, but search execution is unreliable
- Workaround: Use API mode with OpenAI Responses API for reliable search functionality

**Authentication Issues:**
- Ensure `CHATGPT_EMAIL` and `CHATGPT_PASSWORD` are set in `.env` file
- Delete `data/chatgpt_session.json` if login fails
- Manual CAPTCHA/2FA verification may be required (browser will pause for user input)

## Phase Status

✅ **Phase 1: Backend Implementation** - Complete
- Provider abstraction layer
- OpenAI, Google, Anthropic integrations
- Web search functionality with rank tracking
- Unit tests (52 passing)
- API verification (9/9 models working)

✅ **Phase 2: Streamlit UI & Database** - Complete
- 3-tab interface (Interactive, Batch, History)
- Database integration with SQLite
- Multi-model batch analysis
- Query history with search and filtering
- Rank tracking and average rank metrics
- CSV export functionality
- Auto-save all interactions

## Key Metrics Tracked

- **Search Queries**: Number and content of searches performed
- **Sources**: Total URLs fetched during search
- **Sources Used**: URLs actually cited in responses
- **Rank**: Position in search results (1-indexed)
- **Average Rank**: Mean rank of cited sources
- **Response Time**: Model response latency (seconds)

## Advanced Features

### Multi-Model Comparison
Run the same prompts across multiple models simultaneously to compare:
- Search query formulation strategies
- Source selection patterns
- Citation behavior differences
- Response time performance
- Rank preference patterns

### Rank Analysis
Track which search result positions models prefer:
- 1-indexed ranking (1 = first result, 2 = second, etc.)
- Average rank per interaction
- Aggregate rank statistics across batches
- Model-specific rank preferences

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
