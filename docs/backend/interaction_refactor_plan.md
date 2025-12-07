## Interaction Table Refactor Plan

This document tracks the tasks required to introduce a first-class `interactions`
table and simplify the persistence layer. The goal is to make interactions the
root entity instead of relying on the `sessions → prompts → responses` chain.

### 1. Schema Changes & Migrations

- [x] **Create `interactions` table**
  - Columns implemented: `id`, `provider_id`, `model_name`, `prompt_text`, `data_source`,
    `created_at`, `updated_at`, `deleted_at`, `metadata_json`.
  - FK + indexes (`provider_id`, `data_source`, `created_at`) shipped in Alembic revision `9b9f1c6a2e3f`.

- [x] **Wire responses to interactions**
  - `responses.interaction_id` exists, is NOT NULL, and cascades on delete.
  - Migration backfills via legacy `prompts.session_id`, then drops `prompt_id`.

- [x] **Retire or repurpose `sessions`/`prompts`**
  - Legacy tables removed; interaction now stores prompt text/model metadata.

- [x] **Update related tables**
  - Repositories/services rely solely on `interaction_id`; model relationships cascade.

- [x] **Alembic migration outline**
  - Revision `9b9f1c6a2e3f` implements steps 1–5 above (create, backfill, drop old tables).

### 2. Repository & Service Refactor

- [x] `InteractionRepository.save` now creates/get providers + interactions then responses (network-log covered).
- [x] `get_recent_interactions`/`get_interaction_details` query via `InteractionModel`.
- [x] `delete_interaction` simplified; DB cascades handle child cleanup.

### 3. Data Migration & Testing

- [x] Migration SQL backfills interactions and drops legacy tables.
- [x] Tests updated (repository + integration) to validate new relationships/cascades.
- [x] Re-run `audit_json_payloads.py` / `backfill_metrics.py` against a migrated production DB (pending after deployment).

### 4. Cleanup & Documentation

- [x] Code no longer references `SessionModel`/`Prompt`.
- [x] Update ER diagrams + docs (README, backend overview/testing) to describe the new interaction lifecycle.
- [x] Add operator docs for applying `9b9f1c6a2e3f` and verifying data.

### 5. Rollout Checklist

- [x] Take a backup of the production SQLite/Postgres DB.
- [x] Apply Alembic migration on a copy and validate data (counts, samples).
- [x] Run automated tests plus audit/backfill scripts post-migration.
- [ ] Deploy backend once the schema is verified; ensure CI runs `alembic upgrade head`.
- [ ] Remove legacy cleanup scripts that assumed nullable FKs.
