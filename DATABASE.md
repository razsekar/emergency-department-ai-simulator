# Database

PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`), one instance, **one schema per module**, one coordinated Alembic
history in `backend/migrations/versions/`. Everything below is taken from those migration files.

All data in the application tables is synthetic. Patient identifiers look like `SIM-PAT-001`.

## Conventions

- UUID primary keys (`gen_random_uuid()`), `created_at` / `updated_at` (`timestamptz`, default `now()`) on most tables.
- Foreign keys exist **only inside one schema**. References across schemas are opaque values (a UUID or a text reference), never
  foreign keys, so each module could be extracted later. Exceptions in practice: none found in the migrations.
- Each module writes only its own schema. Enforced by a regex-based architecture test, not by database privileges.
- Extension: `vector` (created in migration 0001).

## Migration history

One linear base plus seven independent branches, each with `down_revision = 0001`. The backend starts with
`alembic upgrade heads` (note the plural).

| Revision | Branch label | Content |
|---|---|---|
| 0001 | none | `vector` extension and the 11 empty schemas |
| 0100 | `sim` | resource_management, patient_queue, simulation tables |
| 0200 | `rag` | knowledge_documents, document_chunks (vector(384), HNSW) |
| 0300 | `providers` | model_configurations |
| 0400 | `identity` | identity tables and audit_events, plus seeded roles and permissions |
| 0500 | `agent` | agent_execution_logs, analysis_runs, chat_sessions, chat_messages |
| 0600 | `comparison` | ai_comparison_runs, ai_comparison_results |
| 0700 | `demo` | demo_runs |

Downgrading 0001 removes all module schemas (cascade). Tests apply all heads on an empty database and downgrade to base
(`backend/tests/test_migrations.py`).

## Schema ownership

| Schema | Owning module | Tables |
|---|---|---|
| identity | identity | users, roles, permissions, user_roles, role_permissions |
| simulation | simulation | scenarios, scenario_parameters, scenario_runs, data_state |
| resource_management | resource_management | departments, staff, beds, investigation_facilities |
| patient_queue | patient_queue | patient_visits, investigation_requests, dataset_clock |
| analytics | analytics | none (analytics computes read models from other modules' public interfaces) |
| knowledge_base | knowledge_base | knowledge_documents |
| rag | rag | document_chunks |
| model_providers | model_providers | model_configurations |
| ai_orchestration | ai_orchestration | analysis_runs, chat_sessions, chat_messages, ai_comparison_runs, ai_comparison_results, demo_runs |
| agent_tools | agent_tools | agent_execution_logs |
| audit | audit | audit_events |

Note: `audit.audit_events` and the identity tables are created by the same migration (0400).

## resource_management

**departments**: `id`, `code` (unique), `name`, `capacity` int, `workload_weight` float (default 1), timestamps.

**staff**: `id`, `ref` (unique), `role` (`doctor` | `nurse`), `department_id` (FK departments), `status` (`available` | `busy` | `off_duty`), timestamps.
Index `ix_staff_dept_role_status (department_id, role, status)`.

**beds**: `id`, `ref` (unique), `department_id` (FK departments), `status` (`available` | `occupied`), timestamps.
Index `ix_beds_dept_status (department_id, status)`.

**investigation_facilities**: `id`, `code` (unique), `name`, `capacity` int, `expected_minutes` int, timestamps.

## patient_queue

**patient_visits**: `id`, `visit_ref` (unique), `patient_ref`, `arrival_at`, `registered_at`, `department_code` (text, matches a department code by value),
`triage_category` (`critical` | `urgent` | `semi_urgent` | `non_urgent`; simulated, not a clinical priority), `status`
(`waiting` | `in_treatment` | `discharged`), `treatment_started_at`, `assigned_staff_ref`, `bed_ref` (text refs, no FK), `discharged_at`, timestamps.
Indexes on `status`, `department_code`, `arrival_at`, `triage_category`.

**investigation_requests**: `id`, `visit_id` (FK patient_visits, on delete cascade), `facility_code` (text), `investigation_type`, `status`
(`pending` | `completed`), `requested_at`, `completed_at`, `expected_minutes`, timestamps. Indexes on `status`, `visit_id`, `facility_code`.

**dataset_clock**: single-row table (`id = 1`, check constraint) holding `reference_time`. Waiting times are measured against this
stored reference time (set when a scenario is applied) so numbers do not drift during a session.

## simulation

**scenarios**: `id`, `key` (unique), `name`, `description`, `is_builtin`, timestamps.

**scenario_parameters**: `id`, `scenario_id` (FK scenarios, cascade), `parameters` jsonb, `is_default`, timestamps. Index on `scenario_id`.

**scenario_runs** (history, including failed attempts): `id`, `scenario_id` (FK, set null on delete), `scenario_key`, `scenario_name`, `trigger`,
`status` (`applied` | `failed`), `data_version`, `parameters` jsonb, `validation` jsonb, `error`, `record_count`, `duration_ms`, timestamps.
Index on `created_at`.

**data_state**: single-row table (`id = 1`): `data_version` int (starts at 0), `scenario_key`, `scenario_name`, `last_run_id`, `applied_at`, timestamps.
`data_version` is the identifier that analyses are traced to.

Scenario parameters (`ScenarioParams`, `simulation/domain/params.py`): `seed`, `arrival_rate_per_hour`, `beds_available`, `beds_occupied`,
`doctors_on_duty`, `nurses_on_duty`, `waiting_patients`, `avg_wait_minutes`, `pending_investigations`, `investigation_delay_minutes`,
`department_workload` (per department), `window_minutes`.

## knowledge_base and rag

**knowledge_base.knowledge_documents**: `id`, `name`, `original_filename`, `content_sha256` (char 64, unique: duplicate uploads rejected), `size_bytes`,
`page_count`, `status` (`processing` | `indexed` | `failed`), `chunk_count`, `error_message`, `is_sample`, timestamps. Index on `created_at DESC`.

**rag.document_chunks**: `id`, `document_id` (opaque UUID, no FK), `document_name` (denormalised for citations), `page_number`, `chunk_index`, `content`,
`injection_flagged` bool, `injection_signals` text[], `embedding vector(384)`, timestamps; unique `(document_id, chunk_index)`.
Indexes: `document_id`, and **HNSW on `embedding` with `vector_cosine_ops`** (`ix_document_chunks_embedding_hnsw`).

The embedding model is `sentence-transformers/all-MiniLM-L6-v2` (override `RAG_EMBEDDING_MODEL`), dimension fixed to 384 by the column type.
Changing to a model with another dimension needs a migration and re-embedding. Chunk size and overlap default to 700 / 120
(`RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`). The chat model can change without re-embedding.

## model_providers

**model_configurations**: `id`, `provider` (`anthropic` | `openai` | `gemini` | `ollama`), `model_id`, `display_name`, `api_key_env_var`, `api_base_env_var`
(names of environment variables only; secret values are never stored), `enabled`, timestamps; unique `(provider, model_id)`; index on `provider`.

## identity and audit

**identity.users**: `id`, `username` (unique), `display_name`, `password_hash` (scrypt), `is_active`, timestamps.
**identity.roles**: `id`, `name` (unique), `description`. **identity.permissions**: `id`, `code` (unique), `description`.
**identity.user_roles** (`user_id`, `role_id`) and **identity.role_permissions** (`role_id`, `permission_id`): composite primary keys, cascade deletes.
Migration 0400 seeds the roles `viewer`, `presenter`, `admin` and 14 permissions; demo users are created separately by the seed command.

**audit.audit_events**: `id`, `occurred_at`, `actor`, `action`, `resource`, `outcome` (`success` | `failure` | `denied`), `detail` jsonb, `created_at`.
Indexes on `occurred_at`, `action`, `actor`. Records are written in their own transaction so they survive a rolled-back request.

## agent_tools and ai_orchestration

**agent_tools.agent_execution_logs**: `id`, `run_id` (opaque), `sequence`, `tool_name`, `status` (`ok` | `invalid_arguments` | `unknown_tool` | `error` | `refused`),
`arguments` jsonb, `result_summary` jsonb, `error`, `duration_ms`, `data_version`, `created_at`. Indexes `(run_id, sequence)`, `(tool_name, created_at)`.

**ai_orchestration.analysis_runs**: one row per agent or demo run: `run_type` (`agent` | `demo`), `question`, `scenario_key`, `scenario_name`, `data_version`,
`data_version_consistent`, `snapshot_metrics` jsonb, `mode` (`native` | `fallback`), `fallback_reason`, `tools_executed` jsonb, `retrieved_docs` jsonb,
`citation_check` jsonb, `provider`, `model`, `temperature`, `llm_calls`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens`,
`estimated_cost_usd`, `data_disclosure`, `answer`, `status` (`completed` | `failed`), `error`, `created_by`, timestamps.
Indexes on `created_at`, `data_version`, `(run_type, created_at)`.

**chat_sessions**: `id`, `title`, `created_by`, timestamps; index `(created_by, updated_at)`.
**chat_messages**: `id`, `session_id` (FK chat_sessions, cascade), `role` (`user` | `assistant`), `content`, `sources` jsonb, `citation_check` jsonb, `provider`, `model`,
`latency_ms`, token counts, `data_disclosure`, `created_at`; index `(session_id, created_at)`.

**ai_comparison_runs**: `id`, `question`, `scenario_key`, `scenario_name`, `data_version`, `data_version_consistent`, `snapshot_metrics`, `shared_tools`,
`shared_policies` (all jsonb), `context_sha256`, `selections` jsonb, `status` (`completed` | `partial` | `failed`), `created_by`, timestamps.
**ai_comparison_results**: `id`, `comparison_id` (FK, cascade), `position`, `provider`, `model`, `temperature`, `status` (`completed` | `failed` | `not_configured`),
`error`, `answer`, `latency_ms`, token counts, `estimated_cost_usd`, `tool_calling_supported`, `data_disclosure`, `context_sha256`, `scores` jsonb,
`citation_check` jsonb, `created_at`; unique `(comparison_id, position)`.

**demo_runs**: `id`, `session_id`, `run_number`, `run_label` (Run 1/2/3), `analysis_run_id` (opaque link to analysis_runs), `scenario_key`, `scenario_name`,
`data_version`, `patient_record_count`, `metrics_snapshot` jsonb, `verification` jsonb, `tools_executed`, `retrieved_policies`, `question`, `question_sha256`,
`final_answer`, `provider`, `model`, `latency_ms`, token counts, `estimated_cost_usd`, `created_by`, timestamps; unique `(session_id, run_number)`.

## Scenario apply is transactional

`simulation/application/service.py` runs, inside one `unit_of_work()` (commit on success, rollback on any exception): replace the
resource_management dataset, replace the patient_queue dataset (both through those modules' `public.py`), validate what was actually persisted
against the requested parameters (raises on mismatch, rolling everything back), bump `data_version`, persist the run. A failure afterwards is recorded
as a `failed` row in `scenario_runs` in a separate transaction.

## Operational notes

- Reset all data: `docker compose down -v` (removes the `pgdata` volume), then start again; migrations re-run on startup.
- Host access to Postgres: port 5433 (mapped to 5432 in the container).
- Tests create an isolated database per test process and remove it afterwards; the development database is not used by them.
