# AGENTS.md

Instructions for coding agents (and humans) working in this repository.

## Repo Reality (Read First)

- **Hybrid is the default**: FastAPI backend runs in Docker; Streamlit frontend runs locally (Playwright needs local Chrome on ARM Macs).
  - Backend: `docker compose up -d`
  - Frontend: `API_BASE_URL=http://localhost:8000 streamlit run app.py --server.port 8501`
- **Doc paths are case-sensitive** on Linux/GitHub. Use exact filenames like `docs/backend/OVERVIEW.md` and `docs/frontend/NETWORK_CAPTURE.md`.
- Prefer **tracked files** when scanning/reviewing: use `git ls-files` over `find` to avoid vendor dirs (`node_modules/`, `venv/`, caches).

## Standards to Follow

- **Docstrings required** (Google style) for Python code per `CONTRIBUTING.md`. Keep them concise and useful.
- **Linting is mandatory**: keep Ruff clean (`pyproject.toml` is the source of truth).
- **Test-driven approach**: write tests first (or alongside) changes, especially for behavior and contracts.
- **Commit early and often**: keep commits small, descriptive, and push regularly to avoid large diffs.

## Task Checklists (Recommended)

- For any **non-trivial** piece of work, create a small to-do list (3–7 items) and check items off as you complete them.
  - Good checklist items are concrete and verifiable (e.g., “update docs links”, “run `./scripts/run_all_tests.sh`”, “update fixtures”, “verify docker/hybrid commands”).
  - Skip this for tiny changes (single-file, ~10 lines) where a checklist adds overhead.

## How to Work in This Repo

### Quick Commands

- Lint: `make lint` (or `ruff check .` if you’re not using Make)
- Format: `make format`
- Tests (recommended): `./scripts/run_all_tests.sh`
- Backend DB migrations: `cd backend && alembic upgrade head`

### Testing Expectations

- **SDK validation tests must run first** (the helper script enforces this). See `docs/backend/TESTING.md`.
- **E2E tests are opt-in** and may hit real providers. Only run when explicitly requested:
  - `RUN_E2E=1 pytest backend/tests/test_e2e_persistence.py -v`

### Testing Scope (Avoid Overkill)

- Prefer the **smallest test run** that gives confidence:
  - First run tests closest to the change (single file/test module, or a focused directory).
  - Run the full suite (`./scripts/run_all_tests.sh` or `pytest`) when changes affect shared contracts, schemas, providers, services/repos, or multiple call sites.
- For **truly trivial changes** (comments/docstrings/formatting only), a full `pytest` run is usually unnecessary; run lint/format checks instead.

### Provider/Schema Contract Hygiene

- Provider payload shapes are treated as contracts. If SDK behavior changes:
  - Update `backend/tests/fixtures/provider_payloads.py`
  - Re-run `pytest backend/tests/test_provider_payload_schemas.py -v`

### Database & Ops Discipline

- Use Alembic for schema changes; don’t hand-edit DBs.
- Back up before migrations or bulk edits (see `docs/operations/BACKUP_AND_RESTORE.md`).
- Never commit secrets (`.env` stays local). Avoid leaking keys in logs or docs.

### Network Capture Notes

- Network capture uses Playwright + **Chrome** (not Chromium) and may require **non-headless** mode. See `docs/frontend/NETWORK_CAPTURE.md`.
- Keep any new capture features behind explicit user toggles and document limitations clearly.

## “Done” Checklist (Before You Stop)

- Lint passes (`make lint`).
- Tests pass (`./scripts/run_all_tests.sh`), unless explicitly skipped with justification.
- Docs updated if behavior/commands changed (and links use correct casing).
- Changes are committed with a clear message; push if requested or expected by workflow.

## Handoff / Next Step

- After finishing a piece of work, always end with a clear **next action** for the user (e.g., “run X”, “review Y”, “I can also do Z if you want”).

## Pre-Change Plan

- Before implementing any code or doc changes, briefly tell the user what you plan to do (a short checklist is fine), then proceed.
