# LLM Search Analysis

LLM Search Analysis is a hybrid Streamlit + FastAPI application that compares how OpenAI, Google Gemini, Anthropic Claude, and ChatGPT (network capture) perform live web search. The backend delivers a consistent API for saving interactions and metrics, while the frontend provides interactive, batch, and history workflows plus experimental browser automation.

## Highlights
- **Multi-provider coverage** with normalized metrics (search queries, sources, citations, average rank).
- **Dual data-collection modes:** official APIs plus Playwright-powered network capture for ChatGPT.
- **SQLite persistence** with Docker volumes, backup/restore scripts, and health checks.
- **High-confidence backend**: FastAPI, 95% test coverage, structured logging, and contract tests.
- **Streamlit UI refactor plan:** ongoing work to keep the UI thin and React-ready.

## Quickstart
### Requirements
- Docker + Docker Compose (recommended path), or Python 3.11 if running locally.
- At least one LLM provider API key in `.env` (see `docs/operations/ENVIRONMENT_VARIABLES.md`).

### Option 1: Docker Compose (macOS/Windows/Linux)
```bash
# Clone and enter
git clone <repository-url>
cd llm-search-analysis

# Configure environment
cp .env.example .env
# edit .env and add API keys / ChatGPT credentials if needed

# Start both services (runs DB migrations automatically)
docker compose up -d

# Verify everything
./scripts/verify-docker-setup.sh
```
- Streamlit UI: http://localhost:8501
- FastAPI backend/OpenAPI: http://localhost:8000/docs
- Maintenance tasks (backups, upgrades, logs) are documented in `docs/operations/BACKUP_AND_RESTORE.md`.

### Option 2: Hybrid Local Development (macOS)
1. Prepare the backend database (inside `backend/`):
   ```bash
   cd backend
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```
2. Install frontend deps: `pip install -r requirements.txt && playwright install chrome`.
3. Run Streamlit UI: `API_BASE_URL=http://localhost:8000 streamlit run app.py`.
4. Network capture requires Chrome, non-headless mode, and the env vars noted in `docs/frontend/network_capture.md`.

### Database migrations
- Apply latest schema: `cd backend && alembic upgrade head`.
- Generate new revisions after model changes: `alembic revision --autogenerate -m "describe change"`.
- For existing SQLite files created before Alembic, run `alembic stamp head` once so migrations start from the current schema.

## Documentation Map
- **Architecture & API** – `docs/backend/overview.md` (links to `docs/backend/API_DOCUMENTATION.md` and `docs/backend/TESTING.md`).
- **Operations** – `docs/operations/ENVIRONMENT_VARIABLES.md`, `docs/operations/BACKUP_AND_RESTORE.md`, plus helper scripts under `scripts/`.
- **Frontend docs** – `docs/frontend/TESTING.md` (UI tests) and `docs/frontend/network_capture.md` (browser automation guide).
- **Research** – `docs/research/LLM_SEARCH_FINDINGS.md` captures the investigative findings that motivated many features.
- **Proposals / future work** – `docs/proposals/LIVE_NETWORK_LOGS_PLAN.md`, `docs/proposals/LANGUAGE_CLASSIFIER_EXTENSION.md`.
- **History / archive** – prior roadmaps live in `docs/archive/` (e.g., `FASTAPI_IMPLEMENTATION_PLAN.md`, `DEVELOPMENT_PLAN.md`).

## Project Structure
```
llm-search-analysis/
├── app.py                      # Streamlit entry point
├── docker-compose.yml          # Backend + frontend services
├── requirements.txt            # Frontend deps (Streamlit + Playwright)
├── backend/                    # FastAPI application
│   ├── app/                    # Routes, services, repositories, models
│   ├── tests/                  # 190+ FastAPI tests
│   └── requirements.txt        # Backend deps
├── docs/
│   ├── backend/                # Backend overview/API/testing docs
│   ├── frontend/               # Streamlit testing + network capture docs
│   ├── operations/             # Environment + backup references
│   ├── proposals/              # In-progress designs
│   ├── research/               # Findings + analysis
│   └── archive/                # Historical plans
├── scripts/                    # verify-docker-setup.sh, backup/restore utilities
├── data/                       # Streamlit data + network log storage
└── FRONTEND_REFACTOR_PLAN.md   # Active refactor plan (Phase 3+)
```

## Active Plans & Next Steps
- **Frontend Refactor Plan** (`FRONTEND_REFACTOR_PLAN.md`) – continuing with Phase 3 to keep Streamlit thin and React-ready.
- **Live Network Logs** (`docs/proposals/LIVE_NETWORK_LOGS_PLAN.md`) – design for streaming ChatGPT capture events to the UI.
- **Network capture enhancements** (`docs/frontend/network_capture.md`) – extend beyond ChatGPT and add richer analytics.

## Contributing & Testing
1. Follow the quickstart above, then run:
   ```bash
   # Backend
   cd backend
   pytest --cov=app

   # Frontend utilities
   cd ..
   pytest frontend/tests -v
   ```
2. SDK validation tests must pass before other backend tests (see `docs/backend/TESTING.md`).
3. File issues/PRs referencing the relevant doc section so future contributors can track context.

## License
MIT
