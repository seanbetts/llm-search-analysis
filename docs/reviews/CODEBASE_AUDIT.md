# Codebase Audit Instructions for Agent

(Version 1.0 — for FastAPI + SQLite + Python + Streamlit project)

---

## Objective

Perform a one-off, full codebase audit and produce a structured markdown report of the system’s architecture, risks, quality gaps, and improvement recommendations.

The agent must both analyse the repository and write the audit output into `docs/reviews/CODEBASE_AUDIT.md`. Create directories if they do not yet exist.

---

## Preparation Step — Generate Repository View

Before analysing, generate a high-level file tree and include the output near the top of the report:

```bash
tree -L 3 -I '__pycache__|.git|venv|.mypy_cache|.pytest_cache|node_modules|*.pyc|*.db'
```

---

## What to Read & Consider

Use file names and test suites to infer intended behaviour, and at minimum review:

- `README.md`
- `docs/backend/OVERVIEW.md`
- `docs/frontend/OVERVIEW.md`
- `docs/operations/ENVIRONMENT_VARIABLES.md`
- Any API docs or testing docs found in `docs/`

---

## Audit Report Output Structure

The markdown report must follow this outline.

### Codebase Audit Report

#### 1. Architecture & Data Flow Summary

Write 5–8 sentences that cover: FastAPI backend flow, repository/service layering, SQLite storage model, provider integrations, and frontend→backend interaction model.

#### 2. Repository Snapshot

Embed the `tree -L 3 ...` output captured earlier.

#### 3. Top 10 Findings

List the 10 most important issues/improvement opportunities ordered from highest to lowest severity. Each entry must include a short description, impacted files/components, severity (High/Medium/Low), and a one-sentence remediation. A numbered list or a rank table is acceptable.

#### 4. Section Reviews

##### 4.1 Backend (FastAPI)

- Strengths
- Weaknesses / risks
- Suggested improvements

##### 4.2 SQLite Database & Migrations

- Observed schema
- Migration gaps or drift
- Query / indexing risk
- Suggested improvements

##### 4.3 Provider Integrations (Anthropic, OpenAI, Google, factories and validation)

- Strengths
- Weaknesses
- Suggested improvements

##### 4.4 Frontend (Streamlit & frontend package)

- UX / structure findings
- Code organisation risks
- Suggested improvements

##### 4.5 Testing & Quality

- Coverage strength
- Blind spots
- Five specific tests to add next

##### 4.6 Tooling, Docker & Operational Model

- Observations on scripts, compose usage, run lifecycle
- Risks
- Suggested improvements

#### 5. Suggested Improvement Roadmap

Break work into the following phases (each with 3–6 actionable items):

- Phase 1 — Quick Wins (under 1 day)
- Phase 2 — Structural Improvements
- Phase 3 — Nice-to-Haves

#### 6. Appendix

Optional section for endpoint tables, schema notes, diagrams, or other supporting material.

---

## How the Agent Should Perform the Audit

1. [ ] **Build mental model** — Scan docs and the file layout to identify pipelines, service layers, and data flow.
2. [ ] **Backend review** — Walk `backend/app/api`, services, repositories, models, core, and dependencies.
3. [ ] **Database & repositories** — Inspect Alembic migrations and live DB file structure; assess repository patterns.
4. [ ] **Provider abstraction audit** — Trace provider tests to implementations and inspect validation/error handling.
5. [ ] **Frontend review** — Inspect `app.py`, Streamlit entrypoint tabs, `frontend/` components, config, and helpers.
6. [ ] **Tests & coverage** — Inventory coverage and identify missing validation paths.
7. [ ] **Tooling & operational scan** — Analyse Dockerfiles, scripts, and config docs versus reality.
8. [ ] **Generate markdown** — Write findings with the required structure.
9. [ ] **Save output file** — Write the result to `docs/reviews/CODEBASE_AUDIT.md` and return this path as confirmation.

---

## Output Rules

- Be concise, concrete, and reference real file paths where applicable.
- Use markdown headings, bullet lists, tables, and code blocks where they improve clarity.
- Do not output raw commentary in chat — write all audit content to the markdown file.
- The final chat response should contain only: `docs/reviews/CODEBASE_AUDIT.md`
