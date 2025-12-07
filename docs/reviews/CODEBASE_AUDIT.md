Codebase Audit Instructions for Agent

(Version 1.0 — for FastAPI + SQLite + Python + Streamlit project)

⸻

🎯 Objective

Perform a one-off, full codebase audit and produce a structured markdown report of the system’s architecture, risks, quality gaps and improvement recommendations.

The agent must both analyse the repository and write the audit output into:

docs/reviews/CODEBASE_AUDIT.md

(Create directories if they do not exist.)

⸻

🔍 Preparation Step — Generate Repository View

Before analysing, the agent must generate a high-level file tree using:

tree -L 3 -I '__pycache__|.git|venv|.mypy_cache|.pytest_cache|node_modules|*.pyc|*.db'

Insert this tree output near the top of the audit report for reference.

⸻

🧭 What to Read & Consider

The agent should review:
	•	README.md
	•	docs/backend/OVERVIEW.md
	•	docs/frontend/OVERVIEW.md
	•	docs/operations/ENVIRONMENT_VARIABLES.md
	•	Any API docs or testing docs found in docs

Use file names and test suites to infer intended behaviour.

⸻

📌 Audit Report Output Structure

The markdown report must follow this outline:

⸻

Codebase Audit Report

1. Architecture & Data Flow Summary

5–8 sentences describing:
	•	FastAPI backend flow
	•	Repository/service layering
	•	SQLite storage model
	•	Provider integrations
	•	Frontend→backend interaction model

⸻

2. Repository Snapshot

(Insert tree -L 3 ... output here)

⸻

3. Top 10 Findings

Ranked issues or improvement opportunities, each with a one-sentence remediation.

⸻

4. Section Reviews

4.1 Backend (FastAPI)
	•	Strengths
	•	Weaknesses / risks
	•	Suggested improvements

4.2 SQLite Database & Migrations
	•	Observed schema
	•	Migration gaps or drift
	•	Query / indexing risk
	•	Suggested improvements

4.3 Provider Integrations

(Anthropic, OpenAI, Google, factories and validation)
	•	Strengths
	•	Weaknesses
	•	Suggested improvements

4.4 Frontend (Streamlit & frontend package)
	•	UX / structure findings
	•	Code organisation risks
	•	Suggested improvements

4.5 Testing & Quality
	•	Coverage strength
	•	Blind spots
	•	5 specific tests to add next

4.6 Tooling, Docker & Operational Model
	•	Observations on scripts, compose usage, run lifecycle
	•	Risks
	•	Suggested improvements

⸻

5. Suggested Improvement Roadmap

Break into three phases:

Phase 1 — Quick Wins (under 1 day)

(3–6 items)

Phase 2 — Structural Improvements

(3–6 items)

Phase 3 — Nice-to-Haves

(3–6 items)

⸻

6. Appendix

(Optional endpoint table, schema notes, diagrams)

⸻

⸻

🏗️ How the Agent Should Perform the Audit

Step 1 — Build mental model

Scan docs + file layout, identify pipelines, service layers and data flow.

Step 2 — Backend review

Walk backend/app/api, services, repositories, models, core, dependencies.

Step 3 — Database & repositories

Inspect Alembic migrations and live DB file structure, assess repository patterns.

Step 4 — Provider abstraction audit

Trace provider tests to implementation; inspect validation and error handling.

Step 5 — Frontend review

Inspect app.py Streamlit entrypoint + frontend/ components, config, helpers, network capture and tabs.

Step 6 — Tests & coverage

Inventory coverage and identify missing validation paths.

Step 7 — Tooling & operational scan

Analyse Dockerfiles, scripts, config docs vs reality.

Step 8 — Generate markdown

Write findings using the required structure.

Step 9 — Save output file

Write the result as:

docs/reviews/CODEBASE_AUDIT.md

Return this path as final confirmation.

⸻

📌 Output Rules
	•	Be concise, concrete and reference real file paths where applicable.
	•	Use bullet points, headings and tables where helpful.
	•	Do not output raw commentary in chat — write to the markdown file.
	•	Final message should contain only:
docs/reviews/CODEBASE_AUDIT.md