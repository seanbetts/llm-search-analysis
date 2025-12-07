## Interaction Table Refactor Plan

This document tracks the tasks required to introduce a first-class `interactions`
table and simplify the persistence layer. The goal is to make interactions the
root entity instead of relying on the `sessions → prompts → responses` chain.

### 1. Schema Changes & Migrations

1. **Create `interactions` table**
   - Columns: `id`, `provider_id`, `model_name`, `prompt_text`, `data_source`,
     `created_at`, `updated_at`, `deleted_at` (optional), `metadata`.
   - Foreign keys: `provider_id → providers.id` with `ondelete="CASCADE"`.
   - Indexes: `created_at`, `provider_id`, `data_source`.

2. **Wire responses to interactions**
   - Add nullable `interaction_id` column to `responses`.
   - Backfill `interaction_id` by joining through `prompts.session_id`.
   - Set `ondelete="CASCADE"` once data is migrated, then drop `prompt_id` if
     the prompt text migrates into `interactions`.

3. **Retire or repurpose `sessions`/`prompts`**
   - If each interaction maps to one prompt, drop `prompts` and `sessions` after
     moving the text/model metadata.
   - If multi-prompt sessions are needed, keep `prompts` but reference the new
     `interaction_id` instead of `session_id`.

4. **Update related tables**
   - Ensure `search_queries`, `query_sources`, `response_sources`, and
     `sources_used` only depend on `response_id` with cascade deletes.
   - Remove manual cleanup paths in repositories since the DB handles cascades.

5. **Alembic migration outline**
   1. Create `interactions` table.
   2. Add `interaction_id` to `responses`.
   3. Backfill `interaction_id` (SQL script inside migration).
   4. Drop/alter `sessions` & `prompts`.
   5. Enforce new NOT NULL constraints and indexes.

### 2. Repository & Service Refactor

- `InteractionRepository.save`:
  - Replace the `provider → session → prompt → response` flow with
    `provider → interaction → response`.
  - Persist prompt text + metadata on the interaction record.
  - Ensure network-log saves also create interactions with
    `data_source="network_log"`.

- `get_recent_interactions`/`get_interaction_details`:
  - Use `InteractionModel` (new SQLAlchemy class) as the anchor object.
  - Include provider/model prompt info from the interaction instead of
    reconstructing it from prompts/sessions.

- `delete_interaction`:
  - Simplify to a single delete call; rely on DB cascades to remove child rows.

### 3. Data Migration & Testing

- Add migration-time SQL to create interactions for historical rows.
- Handle orphaned `sessions`/`prompts` gracefully (log + skip).
- Update unit/integration tests to assert:
  - `responses.interaction_id` is always set.
  - Deleting an interaction removes prompts/responses/search data.
  - Network-log and API interactions share the same structure.
- Re-run `audit_json_payloads.py` and `backfill_metrics.py` on a migrated DB to
  ensure nothing regresses.

### 4. Cleanup & Documentation

- Remove unused SQLAlchemy models/columns after migration (`SessionModel`,
  `Prompt`, `Response.prompt_id`, etc.).
- Update ER diagrams, README, and `docs/backend/TESTING.md` to reflect the new
  lifecycle (capture prompt text from `interactions`, not `prompts`).
- Document rollout steps (e.g., “apply Alembic revision XYZ, run data backfill”).

### 5. Rollout Checklist

- [ ] Take a backup of the production SQLite/Postgres DB.
- [ ] Apply Alembic migration on a copy and validate data (counts, samples).
- [ ] Run automated tests plus audit/backfill scripts post-migration.
- [ ] Deploy backend once the schema is verified; ensure CI runs `alembic upgrade head`.
- [ ] Remove legacy cleanup scripts that assumed nullable FKs.
