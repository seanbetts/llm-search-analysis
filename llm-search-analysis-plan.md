# LLM Search Analysis - Project Plan

## Project Overview

Build a unified application to monitor and analyze how LLM models from multiple providers (OpenAI, Google, Anthropic, etc.) use web search and tool-calling capabilities. The app will allow interactive prompting and batch analysis to understand:
- What search queries models generate across different providers
- Which sources they fetch vs. which they cite
- How reasoning traces influence search behavior
- Search patterns and model decision-making
- Comparative analysis across different AI platforms and models

## Goals

1. **Multi-Provider Support**: Unified interface for OpenAI, Google (Gemini), Anthropic (Claude), and future providers
2. **Interactive Mode**: Send individual prompts and see detailed breakdowns of search behavior
3. **Batch Analysis**: Programmatically send multiple prompts for large-scale pattern analysis
4. **Cross-Provider Comparison**: Compare search behavior across different AI platforms and models
5. **Search Insights**: Understand search query patterns, source selection, and citation behavior
6. **Data Persistence**: Store all interactions for historical analysis with provider context

## Technology Stack

### Frontend
- **Streamlit** (Python-based web framework)
  - Fast development
  - Great for data visualization
  - Built-in components for expandable sections, JSON display, tables
  - Easy tabbed interfaces

### Backend
- **Python 3.10+**
- **Provider SDKs**:
  - OpenAI Python SDK (Responses API with web_search tool)
  - Google Generative AI SDK (Gemini with search grounding)
  - Anthropic Python SDK (Claude with tool use)
- **SQLAlchemy** (ORM for database operations)
- **Pandas** (for batch analysis and data manipulation)
- **Abstract provider interface** for extensibility

### Database
- **SQLite** (for development/small scale)
- **PostgreSQL** (optional, for production/large scale)

## Architecture

```
┌──────────────────────────────────────────────────┐
│           Streamlit Frontend                     │
│  ┌────────────────────────────────────────────┐  │
│  │ Tab 1: Interactive Prompting               │  │
│  │ Tab 2: Batch Analysis                      │  │
│  │ Tab 3: Query History                       │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│        Provider Abstraction Layer                │
│  • base_provider.py - Abstract interface         │
│  • provider_factory.py - Provider selection      │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│         Provider Implementations                 │
│  • openai_provider.py                            │
│  • google_provider.py                            │
│  • anthropic_provider.py                         │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│           Core Backend                           │
│  • parser.py - Response parsing                  │
│  • database.py - Data storage                    │
│  • analyzer.py - Basic statistics                │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│              Database (SQLite)                   │
│  • providers                                     │
│  • sessions                                      │
│  • prompts                                       │
│  • responses                                     │
│  • search_calls                                  │
│  • sources                                       │
│  • citations                                     │
└──────────────────────────────────────────────────┘
```

## Features Breakdown

### Tab 1: Interactive Prompting

**Input Section:**
- **Model selector** dropdown with latest models:
  - `gpt-5.1` (OpenAI)
  - `claude-sonnet-4.5` (Anthropic)
  - `gemini-3.0` (Google)
- **Prompt** text area
- **Send** button

**Output Display:**
- **Response**: The model's complete response
- **Search Queries**: List of queries the model generated
- **Sources Fetched**: URLs the model consulted (with titles)
- **Citations**: URLs actually cited in the response
- **Summary Stats**:
  - Total searches: X
  - Sources fetched: Y
  - Citations used: Z

### Tab 2: Batch Analysis

**Input:**
- **Prompts** text area (paste multiple prompts, one per line)
- **OR** CSV file upload (with "prompt" column)
- **Model selector** (same as Tab 1)
- **Run** button

**Processing:**
- Progress bar
- Count of completed prompts

**Output:**
- **Summary Stats**:
  - Total prompts: X
  - Total searches: Y
  - Avg sources per prompt: Z
  - Avg citations per prompt: W
- **Top Domains**: Simple bar chart of most common domains
- **Export** button (download results as CSV)

### Tab 3: Query History

**Display:**
- Simple table of past queries
- **Columns**: Timestamp, Prompt (truncated), Model, Searches, Sources, Citations
- **Search** bar to filter by prompt text
- Click a row to view full details
- **Export** button (CSV download)

## Provider API Integration

### OpenAI Integration

**Endpoint:** `/v1/responses`

**Key Configuration:**
```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",  # or "o4-mini" for reasoning
    reasoning={"effort": "medium"},  # low/medium/high
    tools=[{
        "type": "web_search",
        "filters": {
            "allowed_domains": ["example.com", "news.site"]  # optional
        },
        "external_web_access": True  # default, can be False for cache-only
    }],
    tool_choice="auto",  # let model decide when to search
    include=["web_search_call.action.sources"],  # CRITICAL: get all sources
    input="Your prompt here"
)
```

### Response Structure to Parse

**Search Call Item:**
```json
{
    "type": "web_search_call",
    "id": "ws_67c9fa0502748190b7dd390736892e100be649c1a5ff9609",
    "status": "completed",
    "action": {
        "type": "search",
        "query": "positive news story today",
        "domains": ["news.com"],
        "sources": [
            {"url": "https://...", "title": "..."},
            ...
        ]
    }
}
```

**Message Item:**
```json
{
    "id": "msg_67c9fa077e288190af08fdffda2e34f20be649c1a5ff9609",
    "type": "message",
    "status": "completed",
    "role": "assistant",
    "content": [
        {
            "type": "output_text",
            "text": "On March 6, 2025, several news...",
            "annotations": [
                {
                    "type": "url_citation",
                    "start_index": 2606,
                    "end_index": 2758,
                    "url": "https://...",
                    "title": "Title..."
                }
            ]
        }
    ]
}
```

### Important API Details

**Three Types of Web Search:**
1. **Non-reasoning web search**: Fast, simple query passthrough
2. **Agentic search with reasoning**: Model manages search process, can iterate
3. **Deep research**: Extended investigations (o3-deep-research, o4-mini-deep-research)

**Action Types:**
- `search` - web search (includes query and domains)
- `open_page` - page opened (reasoning models)
- `find_in_page` - in-page search (reasoning models)

**Key Fields to Extract:**
- `web_search_call.action.query` - the search query
- `web_search_call.action.sources` - ALL URLs fetched (complete list)
- `message.content[0].annotations` - citations actually used (subset of sources)

**Supported Models:**
- `gpt-5` (with reasoning levels: low/medium/high)
- `o4-mini`, `o3-mini` (reasoning models)
- `gpt-5-search-api` (specialized for search)
- NOT supported: `gpt-5` with minimal reasoning, `gpt-4.1-nano`

### Google (Gemini) Integration

**SDK:** `google-generativeai`

**Key Configuration:**
```python
import google.generativeai as genai
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    tools=[genai.Tool.google_search],  # Enable Google Search grounding
)

response = model.generate_content(
    "Your prompt here",
    generation_config={
        "temperature": 0.7,
        "top_p": 0.95,
    }
)
```

**Key Features:**
- **Google Search Grounding**: Uses Google Search to ground responses
- **Automatic source attribution**: Gemini automatically includes grounding metadata
- **Search queries**: Extracted from grounding chunks
- **Citations**: Found in grounding metadata with URLs and snippets

**Key Fields to Extract:**
- `response.candidates[0].grounding_metadata.grounding_chunks` - sources consulted
- `response.candidates[0].grounding_metadata.search_entry_point.rendered_content` - search queries
- `response.candidates[0].grounding_metadata.grounding_supports` - citations with attribution

**Supported Models:**
- `gemini-2.0-flash` (latest with search grounding)
- `gemini-1.5-pro` (extended context with search)
- `gemini-1.5-flash` (fast with search capabilities)

### Anthropic (Claude) Integration

**SDK:** `anthropic`

**Key Configuration:**
```python
from anthropic import Anthropic
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Define a web search tool
tools = [{
    "name": "web_search",
    "description": "Search the web for current information",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    }
}]

message = client.messages.create(
    model="claude-3.7-sonnet",
    max_tokens=4096,
    tools=tools,
    messages=[{"role": "user", "content": "Your prompt here"}]
)
```

**Key Features:**
- **Tool use capability**: Claude can request tool use via structured outputs
- **Custom tool integration**: Requires external search API (e.g., Brave, Tavily, Perplexity)
- **Extended thinking**: Claude 3.7 Sonnet supports extended thinking mode
- **Citation tracking**: Manual tracking of tool calls and responses

**Key Fields to Extract:**
- `message.content[i].type == "tool_use"` - tool calls (search requests)
- `message.content[i].input.query` - search query
- Tool responses require external API integration
- Citations extracted from final response text

**Supported Models:**
- `claude-3.7-sonnet` (latest with extended thinking)
- `claude-3.5-opus` (most capable)
- `claude-3.5-haiku` (fast and efficient)

**Note:** Anthropic doesn't have native web search, so we'll need to integrate with a search API provider like:
- Brave Search API
- Tavily API
- Perplexity API
- Exa API

## Database Schema

### Tables

**providers**
- id (primary key)
- name (string) - e.g., "openai", "google", "anthropic"
- display_name (string) - e.g., "OpenAI", "Google", "Anthropic"
- api_version (string, nullable)
- is_active (boolean)
- created_at (timestamp)

**sessions**
- id (primary key)
- provider_id (foreign key)
- model_used (string) - e.g., "gpt-5", "gemini-2.0-flash", "claude-3.7-sonnet"
- reasoning_effort (string, nullable)
- created_at (timestamp)

**prompts**
- id (primary key)
- session_id (foreign key)
- prompt_text (text)
- created_at (timestamp)
- response_id (foreign key, nullable)

**responses**
- id (primary key)
- prompt_id (foreign key)
- response_text (text)
- response_time_ms (integer) - for performance comparison
- created_at (timestamp)
- raw_response_json (json)

**search_calls**
- id (primary key)
- response_id (foreign key)
- search_call_id (string) - from API
- action_type (string) - search/open_page/find_in_page
- search_query (text, nullable)
- created_at (timestamp)

**sources**
- id (primary key)
- search_call_id (foreign key)
- url (text)
- title (text, nullable)
- domain (string)
- was_cited (boolean)

**citations**
- id (primary key)
- response_id (foreign key)
- url (text)
- title (text, nullable)
- start_index (integer)
- end_index (integer)
- cited_text (text)

## Project Structure

```
llm-search-analysis/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py                      # Streamlit main app
├── src/
│   ├── __init__.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base_provider.py    # Abstract provider interface
│   │   ├── provider_factory.py # Provider selection logic
│   │   ├── openai_provider.py  # OpenAI implementation
│   │   ├── google_provider.py  # Google/Gemini implementation
│   │   └── anthropic_provider.py # Anthropic/Claude implementation
│   ├── parser.py               # Unified response parsing
│   ├── database.py             # SQLAlchemy models & operations
│   ├── analyzer.py             # Statistical & comparative analysis
│   └── config.py               # Configuration management
├── data/
│   └── llm_search.db           # SQLite database (gitignored)
└── tests/
    ├── __init__.py
    ├── providers/
    │   ├── test_openai_provider.py
    │   ├── test_google_provider.py
    │   └── test_anthropic_provider.py
    ├── test_parser.py
    └── test_database.py
```

## Progress Tracker

- ✅ **Phase 1: Core Backend** - COMPLETE
- ⏳ **Phase 2: Streamlit UI** - In Progress
- ⬜ **Phase 3: Polish & Basic Analytics** - Not Started
- ⬜ **Phase 4: Deploy** - Not Started

## Implementation Steps

### Phase 1: Core Backend ✅ COMPLETE

1. ✅ **Setup project structure**
   - ✅ Initialize git repository
   - ⬜ Create virtual environment (user setup)
   - ✅ Create requirements.txt with all provider SDKs
   - ✅ Setup .env.example for multiple API keys

2. ✅ **Build provider abstraction layer**
   - ✅ `base_provider.py`: Abstract base class with standard interface
     - ✅ `send_prompt()` method
     - ✅ `get_supported_models()` method
     - ✅ `get_provider_name()` method
   - ✅ `provider_factory.py`: Factory pattern for provider selection

3. ✅ **Build provider implementations**
   - ✅ `openai_provider.py`: OpenAI Responses API integration
     - ✅ Handle web_search tool
     - ✅ Parse search queries, sources, citations
   - ✅ `google_provider.py`: Google Gemini integration
     - ✅ Handle Google Search grounding
     - ✅ Extract grounding metadata
   - ✅ `anthropic_provider.py`: Anthropic Claude integration
     - ✅ Basic implementation (search deferred to future)

4. ✅ **Build unified parser module** (`src/parser.py`)
   - ✅ Helper utilities for parsing
   - ✅ Domain extraction
   - ✅ Text formatting

5. ✅ **Build database module** (`src/database.py`)
   - ✅ Define SQLAlchemy models with provider support
   - ✅ CRUD operations for all tables including providers table
   - ✅ Helper functions for saving interactions
   - ✅ Query functions for recent interactions

6. ✅ **Build analyzer module** (`src/analyzer.py`)
   - ✅ Batch statistics calculations
   - ✅ Domain frequency analysis
   - ✅ CSV export formatting

7. ✅ **Build config module** (`src/config.py`)
   - ✅ Environment variable management
   - ✅ API key configuration

8. ✅ **Testing**
   - ✅ Write tests for each provider
   - ✅ Test with mocked API responses
   - ✅ Database and analyzer tests
   - ✅ Provider factory tests

### Phase 2: Streamlit UI ⏳ IN PROGRESS

9. ⬜ **Main app setup** (`app.py`)
   - ⬜ Initialize Streamlit app
   - ⬜ Setup database connection
   - ⬜ Create tab layout

10. ⬜ **Tab 1: Interactive Prompting**
    - ⬜ Model selector dropdown
    - ⬜ Prompt input text area
    - ⬜ Send button with loading state
    - ⬜ Display response and search data
    - ⬜ Save to database

11. ⬜ **Tab 2: Batch Analysis**
    - ⬜ Multi-line text area for prompts
    - ⬜ CSV file upload option
    - ⬜ Model selection
    - ⬜ Progress tracking
    - ⬜ Basic summary statistics
    - ⬜ Simple domain bar chart
    - ⬜ CSV export

12. ⬜ **Tab 3: Query History**
    - ⬜ Simple table with search/filter
    - ⬜ Click to view details
    - ⬜ CSV export

### Phase 3: Polish & Basic Analytics ⬜ NOT STARTED

13. ⬜ **Enhanced visualizations**
    - ⬜ Improve domain bar chart styling
    - ⬜ Add tooltips and interactivity
    - ⬜ Clean table displays

14. ⬜ **Error handling**
    - ⬜ User-friendly error messages
    - ⬜ API key validation
    - ⬜ Rate limiting handling

### Phase 4: Deploy ⬜ NOT STARTED

15. ⬜ **Final polish**
    - ⬜ Loading states and feedback
    - ⬜ UI/UX improvements
    - ⬜ Documentation updates

16. ⬜ **Deployment**
    - ⬜ Test locally: `streamlit run app.py`
    - ⬜ Optional: Deploy to Streamlit Cloud

## Dependencies (requirements.txt)

```
# Web Framework
streamlit>=1.30.0

# AI Provider SDKs
openai>=1.12.0
google-generativeai>=0.3.0
anthropic>=0.18.0

# Database & Data
sqlalchemy>=2.0.25
pandas>=2.1.4

# Utilities
python-dotenv>=1.0.0

# Visualization
plotly>=5.18.0

# Testing
pytest>=7.4.3
```

## Environment Variables (.env)

```
# AI Provider API Keys
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Database
DATABASE_URL=sqlite:///data/llm_search.db
```

## Key Considerations

### API Costs
- Be aware each provider charges differently
- For MVP: just track basic usage (can add cost tracking later)

### Rate Limits
- Handle rate limit errors with simple retry logic
- Show user-friendly error messages

### Data Privacy
- Store API responses locally
- Don't commit .env file or database to git
- Consider encryption for sensitive prompts

### Performance
- Basic database operations (SQLite is fine for MVP)
- Simple error handling

### Provider-Specific Considerations
- **OpenAI**: Native web_search support
- **Google**: Built-in grounding
- **Anthropic**: Requires external search API (defer to future version)

## Success Metrics (MVP)

The beta app should help you understand:

1. What search queries does each model generate?
2. How many sources do they fetch vs. cite?
3. Which domains appear most frequently?
4. Basic comparison between the three models

## Next Steps

1. Set up project structure and virtual environment
2. Install dependencies
3. Implement Phase 1 (Core Backend with provider abstraction)
4. Start with OpenAI and Google providers (native search support)
5. Build basic Streamlit UI (3 tabs)
6. Test and iterate

## Future Enhancements / Backlog

Features deferred from MVP for future versions:

### Tab Enhancements
- **Tab 1**:
  - Reasoning effort slider (for models that support it)
  - Domain filtering (allow/block specific domains)
  - Detailed reasoning traces display
  - Raw API response viewer
  - Character-level citation tracking
- **Tab 2**:
  - Word cloud visualizations
  - Complex citation ratio analysis
  - Estimated time remaining
  - Per-provider batch statistics
- **Tab 3**:
  - Advanced filters (date range, multiple models)
  - Statistical dashboard with time-series charts
  - Search pattern analysis
  - Average reasoning time tracking

### New Features
- **Tab 4: Cross-Provider Comparison**
  - Side-by-side model comparison
  - Multi-model prompt testing
  - Source overlap analysis (Venn diagrams)
  - Radar charts for metric comparison
  - Cost comparison across providers
  - Response time benchmarking

### Provider Support
- **Anthropic/Claude full integration**
  - External search API integration (Brave, Tavily, Perplexity, Exa)
  - Manual citation tracking
  - Tool use monitoring

### Analytics & Insights
- Advanced visualizations:
  - Word clouds for search terms
  - Domain network graphs
  - Search pattern clustering
  - Heat maps for usage patterns
- Cost tracking and analysis
- Provider performance monitoring
- Citation quality metrics
- Time-series trend analysis

### Infrastructure
- PostgreSQL support for production
- Caching layer for performance
- Async operations for concurrent requests
- Provider health monitoring and fallbacks
- Request queuing and rate limiting per provider
- Provider enable/disable toggles
- Docker containerization
- Cloud deployment automation

### Polish
- Export options (JSON in addition to CSV)
- Shareable query links
- User authentication (multi-user support)
- Custom prompt templates
- Saved search configurations
- Dark mode UI theme

## Additional Resources

**Provider APIs:**
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Google Gemini API Docs](https://ai.google.dev/docs)
- [Anthropic API Docs](https://docs.anthropic.com/)

**Frameworks:**
- [Streamlit Documentation](https://docs.streamlit.io/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
