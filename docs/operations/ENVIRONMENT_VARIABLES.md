# Environment Variables Reference

Complete reference for all environment variables used in the LLM Search Analysis application.

## Quick Start

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Add at least one API key
# Edit .env and add your OpenAI, Google, or Anthropic API key

# 3. Run with Docker (recommended)
docker compose up -d
```

---

## Required Variables

### LLM Provider API Keys

At least **one** of these is required for the application to function:

| Variable | Description | Where to Get It |
|----------|-------------|-----------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT models | https://platform.openai.com/api-keys |
| `GOOGLE_API_KEY` | Google API key for Gemini models | https://aistudio.google.com/app/apikey |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models | https://console.anthropic.com/settings/keys |

**Example:**
```bash
OPENAI_API_KEY=sk-proj-abc123...
GOOGLE_API_KEY=AIzaSyABC123...
ANTHROPIC_API_KEY=sk-ant-api03-ABC123...
```

---

## Optional Variables

### Network Capture Mode (ChatGPT)

Required only if you want to use browser automation to capture ChatGPT network traffic:

| Variable | Description | Default |
|----------|-------------|---------|
| `CHATGPT_EMAIL` | ChatGPT account email | (none) |
| `CHATGPT_PASSWORD` | ChatGPT account password | (none) |

**Example:**
```bash
CHATGPT_EMAIL=yourname@example.com
CHATGPT_PASSWORD=your_secure_password
```

**Note:** Leave these blank if you're only using official APIs.

### Application Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name for logs/docs | `LLM Search Analysis API` |
| `VERSION` | Application version | `1.0.0` |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

**LOG_LEVEL Options:**
- `DEBUG` - Verbose logging for development
- `INFO` - Standard operational logging (recommended for production)
- `WARNING` - Only warnings and errors
- `ERROR` - Only errors
- `CRITICAL` - Only critical failures

### Network Capture Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `BROWSER_HEADLESS` | Run browser in headless mode | `true` |
| `CHATGPT_SESSION_FILE` | Path to session persistence file | `./data/chatgpt_session.json` |
| `NETWORK_LOGS_DIR` | Directory for network capture logs | `./data/network_logs` |

**Notes:**
- Set `BROWSER_HEADLESS=false` to see the browser window (helpful for CAPTCHA)
- Session file persists login state between runs

---

## Deployment-Specific Variables

These variables have different defaults depending on how you run the application.

### Docker Compose Deployment (Recommended)

This repo uses a hybrid default: FastAPI runs in Docker, and Streamlit runs locally (so Playwright can launch your local Chrome).

When using `docker compose up -d`, these are **automatically configured for the backend** in `docker-compose.yml`:

| Variable | Docker Value | Purpose |
|----------|--------------|---------|
| `HOST` | `0.0.0.0` | Listen on all network interfaces |
| `PORT` | `8000` | FastAPI backend port |
| `DATABASE_URL` | `sqlite:///./data/llm_search.db` | SQLite database path (persisted in volume) |
| `CORS_ORIGINS` | `["http://localhost:8501"]` | Allowed CORS origins |

Then run Streamlit locally with:

```bash
API_BASE_URL=http://localhost:8000 streamlit run app.py --server.port 8501
```

If you choose to run Streamlit in Docker (the `frontend` service is currently commented out in `docker-compose.yml`), set `API_BASE_URL=http://api:8000` for that container.

### Local Development (Without Docker)

If running backend and frontend manually, add these to your `.env`:

```bash
# Backend server settings
HOST=127.0.0.1
PORT=8000

# Database (relative to backend directory)
DATABASE_URL=sqlite:///./data/llm_search.db

# Frontend API connection
API_BASE_URL=http://localhost:8000

# CORS (allow Streamlit and React)
CORS_ORIGINS=["http://localhost:8501","http://localhost:3000"]
```

**Local Development Startup:**
```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
streamlit run app.py --server.port 8501
```

---

## Database Configuration

The application uses SQLite by default. Database location depends on deployment mode:

### Docker Deployment

```bash
DATABASE_URL=sqlite:///./data/llm_search.db
```

- **Container path:** `/app/data/llm_search.db`
- **Host path:** `./backend/data/llm_search.db` (mounted volume)
- **Persistence:** Data survives container restarts

### Local Development

```bash
DATABASE_URL=sqlite:///./data/llm_search.db
```

- **Path:** `./backend/data/llm_search.db` (from project root)
- **Relative to:** run backend commands from `backend/`
- **Shared:** Backend API and Streamlit/CLI tools read the same file
- **Auto-migration:** The backend now auto-normalizes any legacy
  `sqlite:///../data/llm_search.db` values to `sqlite:///./data/llm_search.db`,
  but you should update your `.env` to avoid the warning.

### Future: PostgreSQL

To migrate to PostgreSQL:

```bash
DATABASE_URL=postgresql://user:password@host:5432/database
```

SQLAlchemy will automatically adapt. No code changes needed.

---

## Security Best Practices

### ✅ DO

- **Use .env file locally** - Never commit `.env` to git
- **Use secrets management in production** - Environment variables in Docker, Render, AWS, etc.
- **Rotate API keys regularly** - Especially if they may be compromised
- **Use read-only API keys** - Where possible (e.g., OpenAI read-only keys)
- **Set DEBUG=false in production** - Prevents sensitive info in error messages

### ❌ DON'T

- **Don't commit .env to git** - It's in `.gitignore`, keep it there
- **Don't share API keys** - Each developer should have their own
- **Don't use production keys locally** - Use separate development keys
- **Don't hardcode secrets** - Always use environment variables

---

## Troubleshooting

### "No API keys configured"

**Problem:** Application can't find any API keys.

**Solution:**
```bash
# 1. Check .env exists
ls -la .env

# 2. Verify API keys are set (not blank)
cat .env | grep API_KEY

# 3. For Docker, restart containers
docker compose down
docker compose up -d

# 4. For local dev, reload environment
source .env  # or restart your terminal
```

### "Connection refused" (Frontend → Backend)

**Problem:** Frontend can't connect to backend API.

**Docker Solution:**
```bash
# Check backend is running
docker compose ps

# Check backend health
curl http://localhost:8000/health

# If running Streamlit locally, point it at the Dockerized backend
export API_BASE_URL=http://localhost:8000
```

**Local Dev Solution:**
```bash
# In .env, uncomment:
API_BASE_URL=http://localhost:8000

# Verify backend is running
curl http://localhost:8000/health
```

### "Database is locked"

**Problem:** SQLite doesn't handle concurrent writes well.

**Solution:**
```bash
# For production, migrate to PostgreSQL:
DATABASE_URL=postgresql://user:password@host:5432/database

# For local dev, ensure only one process accesses DB
```

### "ChatGPT authentication failed"

**Problem:** Network capture mode can't log in.

**Solution:**
```bash
# 1. Verify credentials are correct
echo $CHATGPT_EMAIL
echo $CHATGPT_PASSWORD

# 2. Try with browser visible (CAPTCHA may be needed)
BROWSER_HEADLESS=false

# 3. Delete session file to force re-auth
rm ./data/chatgpt_session.json
```

---

## Environment File Examples

### Minimal Configuration (Docker)

```bash
# .env - Minimal for Docker deployment
OPENAI_API_KEY=sk-proj-abc123...
```

### Full Configuration (Local Development)

```bash
# .env - Full local development setup
OPENAI_API_KEY=sk-proj-abc123...
GOOGLE_API_KEY=AIzaSyABC123...
ANTHROPIC_API_KEY=sk-ant-api03-ABC123...

HOST=127.0.0.1
PORT=8000
DATABASE_URL=sqlite:///./data/llm_search.db
API_BASE_URL=http://localhost:8000
CORS_ORIGINS=["http://localhost:8501","http://localhost:3000"]

DEBUG=true
LOG_LEVEL=DEBUG
```

### Production Configuration (Docker)

```bash
# .env - Production Docker deployment
OPENAI_API_KEY=sk-proj-abc123...
GOOGLE_API_KEY=AIzaSyABC123...
ANTHROPIC_API_KEY=sk-ant-api03-ABC123...

CHATGPT_EMAIL=yourname@example.com
CHATGPT_PASSWORD=your_secure_password

DEBUG=false
LOG_LEVEL=INFO
BROWSER_HEADLESS=true
```

---

## Validation Checklist

Before deploying, verify your configuration:

- [ ] At least one LLM provider API key is set
- [ ] API key(s) are valid (test with curl or in UI)
- [ ] `DEBUG=false` for production
- [ ] `LOG_LEVEL=INFO` for production (or WARNING/ERROR)
- [ ] Database path is correct for deployment mode
- [ ] CORS origins include your frontend URL
- [ ] `.env` file is NOT committed to git
- [ ] Secrets are managed securely (not in code)

---

## Reference Links

- **OpenAI API Keys:** https://platform.openai.com/api-keys
- **Google AI Studio:** https://aistudio.google.com/app/apikey
- **Anthropic Console:** https://console.anthropic.com/settings/keys
- **Pydantic Settings Docs:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **FastAPI Environment Variables:** https://fastapi.tiangolo.com/advanced/settings/
