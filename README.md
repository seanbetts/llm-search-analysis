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
- **Dual Data Collection Modes**: API-based (structured data) and Network Capture (browser automation with enhanced metadata)
- **3-Tab Interface**: Interactive prompting, batch analysis, and query history
- **Database Integration**: SQLite-based persistence for all interactions
- **Rank Tracking**: Monitor which search result positions sources come from (1-indexed)
- **Citation Classification**: Distinguish between citations from search results (Sources Used) vs training data (Extra Links)

### Tab 1: Interactive Prompting
- Single-prompt testing with real-time results
- Detailed search queries grouped with their sources
- Sources used (citations from search results) with rank positions
- Extra links (citations from model training data)
- Response metadata: searches, sources found, sources used, average rank, extra links, response time

### Tab 2: Batch Analysis
- **Multi-model comparison**: Test multiple models simultaneously
- Bulk prompt processing (text area or CSV upload)
- Progress tracking: prompts × models = total runs
- Comprehensive metrics: Total Runs, Avg Sources Found, Avg Sources Used, Avg Rank, Avg Extra Links
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

## Deployment

### Option 1: Docker (Recommended)

Docker provides the easiest way to run this application with zero configuration hassle.

#### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (Mac/Windows) or Docker Engine (Linux)
- At least one LLM provider API key

#### Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd llm-search-analysis
```

2. Create `.env` file with your API keys:
```bash
cp .env.example .env
# Edit .env and add your API keys:
# OPENAI_API_KEY=your_key_here
# GOOGLE_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here
```

3. Start the application:
```bash
docker compose up -d
```

4. Access the interface:
- Frontend (Streamlit): http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

5. Stop the application:
```bash
docker compose down
```

#### Docker Architecture

The Docker setup includes:
- **Backend (API)**: FastAPI server on port 8000
- **Frontend**: Streamlit UI on port 8501
- **Database**: SQLite with persistent volume mount
- **Networking**: Isolated Docker network for inter-service communication
- **Data Persistence**: Database and session files persist across container restarts

#### Docker Commands

```bash
# Build and start services
docker compose up --build -d

# View logs
docker compose logs -f

# Stop services (keeps data)
docker compose down

# Stop services and remove volumes (deletes data)
docker compose down -v

# Rebuild a specific service
docker compose build api
docker compose up -d api

# Access a service shell
docker compose exec api bash
docker compose exec frontend bash
```

#### Environment Variables

All environment variables are configured in the `.env` file. Key variables:

**Required:**
- `OPENAI_API_KEY` - OpenAI API key
- `GOOGLE_API_KEY` - Google AI API key
- `ANTHROPIC_API_KEY` - Anthropic API key

**Optional:**
- `BROWSER_HEADLESS=true` - Browser mode for network capture
- `LOG_LEVEL=INFO` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `DEBUG=false` - Enable debug mode

See `.env.example` for complete configuration options.

### Option 2: Local Development

For development work, you can run the services locally without Docker.

#### Prerequisites
- Python 3.11+
- API keys for at least one provider

#### Setup

1. Install backend dependencies:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Install frontend dependencies:
```bash
cd ..  # Back to root
pip install -r requirements.txt
```

3. Create `.env` file (see Docker section above)

4. Start the backend:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Start the frontend (in a new terminal):
```bash
streamlit run app.py --server.port 8501
```

6. Configure frontend to connect to backend:
```bash
export API_BASE_URL=http://localhost:8000
```

## Usage

### Running the Web Interface

**With Docker:**
```bash
docker compose up -d
```
Access at http://localhost:8501

**Without Docker:**
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
- Provides additional metadata not available via API:
  - Internal ranking scores for search results
  - Query reformulations performed by the model
  - Snippet text from search results
  - Citation confidence scores
- Session persistence (stays logged in between runs)
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
├── app.py                        # Streamlit web interface (3 tabs)
├── Dockerfile                    # Frontend Docker image
├── docker-compose.yml            # Multi-container orchestration
├── .env.example                  # Environment variables template
├── .dockerignore                 # Docker build exclusions
├── requirements.txt              # Frontend Python dependencies
│
├── backend/                      # FastAPI backend service
│   ├── Dockerfile                # Backend Docker image
│   ├── .dockerignore             # Backend build exclusions
│   ├── requirements.txt          # Backend Python dependencies
│   ├── .env.example              # Backend env template
│   ├── app/
│   │   ├── main.py               # FastAPI application entry
│   │   ├── config.py             # Settings and configuration
│   │   ├── models/
│   │   │   └── database.py       # SQLAlchemy ORM models
│   │   ├── repositories/
│   │   │   └── interaction_repository.py  # Data access layer
│   │   ├── services/
│   │   │   ├── interaction_service.py     # Business logic
│   │   │   ├── provider_service.py        # LLM provider orchestration
│   │   │   └── providers/                 # Provider implementations
│   │   │       ├── base_provider.py       # Abstract base class
│   │   │       ├── provider_factory.py    # Provider selection
│   │   │       ├── openai_provider.py     # OpenAI Responses API
│   │   │       ├── google_provider.py     # Google Gemini
│   │   │       └── anthropic_provider.py  # Anthropic Claude
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── routes/               # API endpoint routes
│   │   │       └── schemas/              # Pydantic request/response schemas
│   │   └── core/
│   │       ├── database.py               # Database connection
│   │       └── utils.py                  # Utility functions
│   ├── data/                             # Database and session files
│   │   └── llm_search.db                 # SQLite database (auto-created)
│   └── tests/                            # Backend unit tests
│
├── src/                          # Legacy frontend modules (deprecated)
│   └── network_capture/          # Browser automation (experimental)
│       ├── browser_manager.py    # Playwright browser control
│       ├── chatgpt_capturer.py   # ChatGPT interaction capture
│       └── parser.py             # Network log parsing
│
├── tests/                        # Frontend and integration tests
│   ├── verify_providers.py       # API verification script
│   ├── test_rank_feature.py      # Rank tracking validation
│   └── ... (52 passing tests)
│
├── data/                         # Frontend data directory
│   ├── chatgpt_session.json      # ChatGPT session persistence
│   └── network_logs/             # Network capture logs
│
└── README.md                     # This file
```

### Architecture Overview

The application uses a **client-server architecture**:

**Frontend (Streamlit):**
- User interface with 3 tabs (Interactive, Batch, History)
- Communicates with backend via REST API
- Handles browser automation for network capture mode
- Port: 8501

**Backend (FastAPI):**
- RESTful API with automatic OpenAPI docs
- LLM provider integrations (OpenAI, Google, Anthropic)
- Database operations via SQLAlchemy ORM
- Business logic and data validation
- Port: 8000

**Database (SQLite):**
- Persistent storage for all interactions
- Volume-mounted in Docker for data persistence
- Schema supports both API and network capture modes

### Database Schema

**Tables:**
- `providers` - AI provider metadata (OpenAI, Google, Anthropic)
- `sessions` - Provider session information
- `prompts` - User prompts
- `responses` - Model responses with timing data and data source (api/network_log)
- `search_queries` - Search queries generated by models
- `sources` - Sources fetched during search (with rank and metadata)
- `sources_used` - All citations in responses
  - Citations from search results have `rank` (Sources Used)
  - Citations from training data have `rank=NULL` (Extra Links)

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
- Note: ChatGPT may include URLs in its response from two sources:
  1. **Search results** - URLs from web search (displayed as "Sources Used" with ranks)
  2. **Training data** - URLs from model knowledge (displayed as "Extra Links" without ranks)
  Only URLs from the network event stream `search_result_groups` will have rank numbers. The raw event stream is saved in `raw_response_json` for inspection.

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

- **Search Queries**: Number and content of searches performed by the model
- **Sources Found**: Total URLs retrieved from web search results
- **Sources Used**: Citations that came from search results (have rank numbers)
  - Only includes URLs the model found via web search
  - Used to calculate Average Rank
- **Extra Links**: Citations that came from model's training data (no rank numbers)
  - URLs mentioned in response but NOT from search results
  - Indicates model used pre-existing knowledge
  - Counted separately from Sources Used
- **Rank**: Position in search results (1-indexed, where 1 = top result)
- **Average Rank**: Mean position of Sources Used in search results
  - Lower values = model prefers higher-ranked sources
  - Only calculated from Sources Used (excludes Extra Links)
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
