# Docstring Standardization Plan

## Goals
- Adopt Google-style docstrings across backend, frontend, and shared utilities to improve readability and tooling support.
- Ensure every module, public class, and function carries a concise description plus contextual sections (`Args`, `Returns`, `Raises`, `Examples`, etc. when applicable).
- Automate enforcement so regressions are caught during local testing and CI.

## Scope
- **Code**: All Python packages under `backend/`, `frontend/`, and project-level scripts; test modules keep scenario docstrings but are otherwise subject to the same rules.
- **Tooling**: Linting (pydocstyle or Ruff), pytest-based structural checks, and project documentation describing the standard.
- **Process**: Branching strategy, CI integration, and developer guidance.

## Implementation Steps
1. **Create Working Branch**
   - Branch from the current development branch (e.g., `git checkout -b feature/docstring-standardization`) to isolate the changes.
2. **Document the Style Guide**
   - Add a “Docstring Style (Google)” section to `README.md` or `CONTRIBUTING.md` covering:
     - Mandatory docstrings for modules/classes/functions.
     - Required sections and when to omit them.
     - Exception handling for simple test helpers or dunder methods.
3. **Add Tooling Configuration**
   - Introduce `.pydocstyle` (or enable `ruff`’s `pydocstyle` rules) with `convention = google`.
   - Update `pyproject.toml`/`requirements-dev.txt` (or `requirements.txt`) to include the chosen tool.
   - Extend existing lint commands (`make lint`, CI workflows) to run the docstring checks.
4. **Add Pytest Enforcement Tests**
   - Backend: new test module (e.g., `backend/tests/test_docstrings.py`) that walks the backend tree via `ast`, asserting module/class/function docstrings exist unless explicitly whitelisted.
   - Frontend: mirror test (e.g., `frontend/tests/test_docstrings.py`) for frontend modules.
   - Maintain small allowlists for intentional omissions (e.g., auto-generated files, fixtures).
5. **Backfill Missing Docstrings**
   - Prioritize high-impact modules: `backend/app/main.py`, `backend/app/config.py`, schema files, dependencies, parsers, repositories, and frontend tab/network parser helpers.
   - Ensure helper closures or nested functions with complex logic get docstrings or inline comments explaining intent.
6. **Validate & Iterate**
   - Run `pydocstyle`/`ruff` and the new pytest suites locally until clean.
   - Update CI pipelines to fail on docstring violations.
   - Review and merge the feature branch once tests pass.

## Timeline & Ownership
| Step | Owner | Notes |
| --- | --- | --- |
| Branch creation & style doc | _TBD_ | Create documentation updates early so reviewers see expectations. |
| Tooling config | _TBD_ | Coordinate with whoever maintains lint tooling. |
| Pytest enforcement | _TBD_ | Consider pairing backend/frontend owners for coverage parity. |
| Docstring backfill | _TBD_ | Split by directory to keep PRs reviewable. |
| CI updates & merge | _TBD_ | Ensure pipelines run new checks before merging. |

## Risks & Mitigations
- **Large diff**: Backfilling docstrings touches many files. Mitigate by batching commits (e.g., backend first, frontend second).
- **False positives**: Auto checks may flag generated files. Maintain explicit skip lists/allowances.
- **Developer friction**: Provide examples and mention tooling commands in docs so new contributors know how to comply.

## Next Actions
1. Assign owners for each step and create the feature branch.
2. Draft the style guide section and tooling config PR.
3. Implement automated checks and begin docstring backfill.
