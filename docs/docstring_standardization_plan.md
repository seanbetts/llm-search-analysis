# Docstring Standardization Plan

## Goals
- Adopt Google-style docstrings across backend, frontend, and shared utilities to improve readability and tooling support.
- Ensure every module, public class, and function carries a concise description plus contextual sections (`Args`, `Returns`, `Raises`, `Examples`, etc. when applicable).
- Automate enforcement so regressions are caught during local testing and CI.

## Scope
- **Code**: All Python packages under `backend/`, `frontend/`, and project-level scripts; test modules keep scenario docstrings but are otherwise subject to the same rules.
- **Tooling**: Ruff with pydocstyle rules, pytest-based structural checks, and project documentation describing the standard.
- **Process**: Branching strategy, CI integration, and developer guidance.

## Current State Assessment

**Coverage** (as of 2025-12-09):
- Module docstrings: ~56% backend, ~90% frontend
- Function/class docstrings: ~75-85% overall
- Style: Google-style already predominant (80%+ of existing docstrings)

**Key Gaps**:
- Module-level docstrings missing in core files (`backend/app/main.py`, `backend/app/config.py`)
- Private/helper methods have inconsistent coverage
- No automated enforcement currently in place

**Key Strengths**:
- Core modules (exceptions, utils, repositories, providers, API client) have excellent coverage
- Existing docstrings largely follow Google-style conventions
- Frontend has better module docstring coverage than backend

**Impact**: This is a refinement and enforcement effort, not a wholesale rewrite.

## Tooling Decision: Ruff (Recommended)

**Recommendation**: Use Ruff's built-in pydocstyle rules (D-series)

**Rationale**:
- Single tool for both linting and docstring checks
- 10-100x faster than standalone pydocstyle
- Active development and modern Python support
- Already widely adopted in Python ecosystem

**Configuration** (add to `pyproject.toml`):
```toml
[tool.ruff.lint]
select = ["D"]  # Enable docstring rules
extend-ignore = [
  "D100",  # Missing docstring in public module (enable gradually)
  "D104",  # Missing docstring in public package
  "D107",  # Missing docstring in __init__
]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

**Alternative**: If pydocstyle is preferred for specific reasons, document the rationale and provide equivalent configuration.

## Implementation Steps

### 1. Create Working Branch
- Branch from `main` (e.g., `git checkout -b feature/docstring-standardization`) to isolate the changes.

### 2. Baseline Assessment
- Run initial docstring coverage report using pytest enforcement tests
- Document current state for comparison (see "Success Metrics" below)
- Identify quick wins (module docstrings) vs. complex refactors (private methods)

### 3. Document the Style Guide
- Add a "Docstring Style (Google)" section to `CONTRIBUTING.md` covering:
  - Mandatory docstrings for modules/classes/functions
  - Required sections (`Args`, `Returns`, `Raises`, `Examples`) and when to omit them
  - **Include specific examples from existing codebase** (e.g., from `api_client.py`, `exceptions.py`, `utils.py`)

- Define exemptions clearly:
  - Test fixtures and simple test helpers
  - Dunder methods (`__repr__`, `__str__`, `__eq__`, etc.)
  - One-line property getters
  - Auto-generated Alembic migration files

- Add docstring quality checklist for reviewers

### 4. Add Tooling Configuration
- Install and configure Ruff with Google-style docstring rules
- Add to `requirements-dev.txt` or `pyproject.toml` dependencies
- Start with **WARNING level**, not ERROR (gradual adoption)
- Create `make docstring-check` command for local development
- Extend existing lint commands to include docstring checks

### 5. Add Pytest Enforcement Tests
- **Backend**: Create `backend/tests/test_docstrings.py` that walks the backend tree via `ast`, asserting module/class/function docstrings exist
- **Frontend**: Create `frontend/tests/test_docstrings.py` for frontend modules
- Include coverage reporting (% of modules/classes/functions documented)
- Start with `@pytest.mark.xfail` decorator for known gaps (gradually remove as backfill progresses)
- Maintain exemption allowlists for auto-generated files, fixtures, and intentional omissions

### 6. Validate Tooling Before Backfill
- Run Ruff and pytest docstring checks on existing well-documented modules
- Ensure no false positives on code that should pass
- Adjust exemptions and allowlists as needed
- Get clean run on a representative subset before proceeding to full backfill
- Document any edge cases or special handling required

### 7. Backfill Missing Docstrings (Phased Approach)

**Phase 1: Module-level docstrings** (Low risk, high visibility)
- `backend/app/main.py` - Application entry point
- `backend/app/config.py` - Configuration module
- Any missing `__init__.py` docstrings in key packages
- **Goal**: Achieve 95%+ module docstring coverage

**Phase 2: Public API surface** (High priority)
- API endpoints (if any are missing docstrings)
- Schema files (`requests.py`, `responses.py`) - ensure all Pydantic models documented
- Service layer public methods
- Repository layer public methods
- Provider implementations
- **Goal**: 95%+ coverage of public functions/classes

**Phase 3: Internal implementation** (Lower priority)
- Private methods with complex logic
- Helper functions and utilities
- Frontend tab internal functions
- Nested functions with non-trivial behavior
- **Goal**: 60%+ coverage of private/internal code (complex logic only)

### 8. Gradual Enforcement Rollout
- Enable Ruff docstring warnings in local development first
- Monitor for 1-2 weeks, gather developer feedback
- Fix any false positives and refine exemptions
- Promote to CI with `--error` level (fail builds on violations)
- Update pre-commit hooks (if used) to run docstring checks
- Document enforcement in developer onboarding materials

## Success Metrics

**Baseline** (current state):
- Module docstrings: 56% backend, 90% frontend
- Function/class docstrings: ~75-85%
- Automated enforcement: 0%
- Google-style consistency: ~80%

**Target** (after implementation):
- Module docstrings: 95%+ (all except auto-generated)
- Public function/class docstrings: 95%+
- Private function docstrings: 60%+ (complex logic only)
- Automated enforcement: 100% (all new code checked in CI)
- CI integration: Passing docstring checks required for merge
- Google-style consistency: 100%

**Tracking**:
- Coverage reports from pytest enforcement tests (run weekly during implementation)
- Ruff violation counts over time (track trend toward zero)
- Developer feedback surveys after 1 month of enforcement
- Code review metrics (docstring-related comments/rejections)

## Timeline & Ownership

| Step | Owner | Estimated Duration | Notes |
| --- | --- | --- | --- |
| Baseline assessment | _TBD_ | 1-2 days | Run coverage reports, document gaps |
| Branch creation & style doc | _TBD_ | 3-5 days | Include examples from codebase |
| Tooling config (Ruff) | _TBD_ | 2-3 days | Coordinate with lint tooling maintainer |
| Pytest enforcement tests | _TBD_ | 3-5 days | Backend and frontend parity |
| Tooling validation | _TBD_ | 2-3 days | Test on existing code, fix false positives |
| Phase 1 backfill (modules) | _TBD_ | 2-3 days | Low risk, quick wins |
| Phase 2 backfill (public APIs) | _TBD_ | 1-2 weeks | Split by directory for reviewable PRs |
| Phase 3 backfill (internals) | _TBD_ | 1-2 weeks | Selective, complex logic only |
| CI integration & enforcement | _TBD_ | 2-3 days | Enable errors, update workflows |
| Monitoring & refinement | _TBD_ | 2-4 weeks | Gather feedback, adjust exemptions |

**Total estimated duration**: 6-8 weeks for full implementation

## Risks & Mitigations

**Risk: Large diff**
- Backfilling docstrings touches many files, making reviews difficult
- **Mitigation**: Phased approach by priority/risk, not by directory. Module docstrings first (small changes), then public APIs, then internals. Keep PRs under 500 lines where possible.

**Risk: False positives**
- Auto checks may flag generated files or intentional omissions
- **Mitigation**: Maintain explicit skip lists in `pyproject.toml`. Start with warnings, not errors. Build exemption allowlists based on actual codebase needs.

**Risk: Developer friction**
- New contributors may not know Google-style conventions
- **Mitigation**: Include concrete examples in `CONTRIBUTING.md`, add pre-commit hook with helpful error messages, create docstring templates/snippets for common patterns, provide "good" vs "bad" examples.

**Risk: Existing good coverage disruption**
- 75% of code already has docstrings; changes might disrupt working code
- **Mitigation**: Audit existing docstrings for Google-style compliance before backfilling new ones. Standardize what exists first. Use `@pytest.mark.xfail` for known gaps during transition.

**Risk: Pytest enforcement brittleness**
- AST walking can be fragile and produce false positives/negatives
- **Mitigation**: Start with simple checks (docstring exists), not complex validation (specific sections present). Use exemption allowlists liberally at first. Refine based on real-world usage.

**Risk: CI pipeline slowdown**
- Adding more checks increases build time
- **Mitigation**: Run docstring checks only on changed files initially (using `git diff`), or as separate non-blocking CI job that reports but doesn't fail. Ruff is fast enough that full checks should add <10 seconds.

**Risk: Inconsistent enforcement during transition**
- Some code enforced, some not, leading to confusion
- **Mitigation**: Clear communication about phased rollout. Use branch protection rules to enforce only after full implementation. Document exemptions prominently.

## Next Actions

**Immediate** (Week 1):
1. ✅ Current state assessed (75-85% coverage, Google-style predominant)
2. ✅ Feature branch created: `feature/docstring-standardization`
3. ✅ Style guide created in `CONTRIBUTING.md` with examples from existing codebase
4. ✅ Ruff configured in `pyproject.toml` with Google-style docstring rules
5. ✅ `Makefile` created with convenient commands (`make lint`, `make docstring-check`, etc.)
6. ✅ Updated `scripts/run_all_tests.sh` to include linting and docstring checks

**Short-term** (Week 2-3):
7. ✅ Phase 1 backfill complete: Added module docstrings to `main.py`, `config.py`, fixed formatting issues
8. ✅ Pytest enforcement tests implemented with AST-based coverage checking and reporting
9. Validate tooling on existing well-documented modules (exceptions, utils, repositories)

**Medium-term** (Week 4-6):
10. Phase 2 backfill: Complete public API docstrings (schemas, services, repositories, providers)
11. Phase 3 backfill: Add docstrings to complex private/internal methods
12. Enable Ruff warnings in local development, gather feedback from team
13. Refine exemptions and allowlists based on feedback

**Long-term** (Week 7-8):
14. Promote to CI enforcement (errors, not warnings) - fail builds on violations
15. Add pre-commit hooks for docstring checks (optional but recommended)
16. Update developer onboarding documentation
17. Conduct retrospective, document lessons learned
18. Merge feature branch to `main`, mark plan as complete

## References

- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Ruff Docstring Rules (D-series)](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
