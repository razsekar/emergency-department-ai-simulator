# Database

PostgreSQL 16 (`pgvector/pgvector:pg16`), one instance, one schema per module, one coordinated
Alembic history in `backend/migrations/`.

## Implemented (migration 0001)
- Extension `vector`
- Schemas: identity, simulation, patient_queue, resource_management, analytics, knowledge_base,
  rag, ai_orchestration, agent_tools, model_providers, audit

## Planned tables (by owner)
| Schema | Tables |
|---|---|
| identity | users, roles, user_roles, permissions |
| simulation | scenarios, scenario_parameters, scenario_runs, data_state (data_version) |
| resource_management | departments, staff, beds, investigation_facilities |
| patient_queue | patient_visits, investigation_requests |
| knowledge_base | knowledge_documents |
| rag | document_chunks (`vector(384)`, HNSW cosine index) |
| ai_orchestration | chat_sessions, chat_messages, analysis_runs, ai_comparison_runs |
| agent_tools | agent_execution_logs |
| model_providers | model_configurations (env var names only, never secrets) |
| audit | audit_events |

Conventions: UUID primary keys, `created_at`/`updated_at`, FKs only within a schema,
opaque UUIDs across schemas.

Migration commands (in the backend container): `alembic upgrade head`, `alembic downgrade base`.

## Identity and audit (migration 0400, branch label `identity`)
- `identity.users` (username unique, scrypt `password_hash`, `is_active`), `identity.roles`,
  `identity.permissions`, `identity.user_roles`, `identity.role_permissions` (FKs inside the schema only).
- `audit.audit_events` (actor, action, resource, outcome in success/failure/denied, JSONB detail,
  indexes on occurred_at, action, actor).
- Roles and permissions are seeded by the migration (viewer, presenter, admin; 14 permissions).
  The reference matrix lives in `identity/domain/permissions.py`; a test asserts the DB matches it.
- Demo users are created by `python -m app.modules.identity.application.seed`
  (passwords from `DEMO_*_PASSWORD` env vars; existing users are never modified).

## Simulation data (migration 0100, branch label `sim`)
- `resource_management`: `departments` (code, name, capacity = beds allocated, workload_weight), `staff` (ref SIM-DOC-001, role doctor/nurse, status available/busy/off_duty), `beds` (ref SIM-BED-01, status available/occupied), `investigation_facilities` (LAB, XRAY, CT, US; capacity, expected_minutes).
- `patient_queue`: `patient_visits` (visit_ref SIM-VIS-0001, patient_ref SIM-PAT-001, arrival/registered/treatment_started/discharged timestamps, department_code, simulated triage_category, status waiting/in_treatment/discharged, assigned_staff_ref, bed_ref), `investigation_requests` (FK to visit; status pending/completed; requested_at, expected_minutes), `dataset_clock` (singleton reference time).
- `simulation`: `scenarios`, `scenario_parameters` (JSONB defaults), `scenario_runs` (history incl. failed attempts; parameters + validation checks as JSONB), `data_state` (singleton: `data_version`, current scenario, applied_at).
- Cross-schema links are business keys (department_code, bed_ref, staff_ref), never FKs. Waiting durations are measured against `dataset_clock.reference_time` (frozen at apply time) so values do not drift during a demo; "waiting time" = reference time minus arrival for waiting patients.
- Apply flow (one transaction): resolve/validate params -> generate (seeded) -> resource_management and patient_queue replace their own datasets via their public interfaces -> validate what was persisted (exact counts, mean wait within 10%, mean pending-request age within 15%) -> bump `data_version` -> insert `scenario_runs` -> commit. Any failure rolls back; a failed run is then recorded separately.
- Apply to a dev database: `alembic upgrade sim@head` (or `heads` for all branches).

## Knowledge base and RAG (migration 0200, branch label `rag`)
- `knowledge_base.knowledge_documents`: id, name, original_filename, `content_sha256` (UNIQUE, rejects duplicate
  uploads), size_bytes, page_count, status (`processing` | `indexed` | `failed`, CHECK), chunk_count,
  error_message, is_sample, created_at/updated_at.
- `rag.document_chunks`: id, `document_id` (opaque UUID, no cross-schema FK), `document_name` (denormalized
  for citations), page_number, chunk_index (UNIQUE per document), content, `injection_flagged`,
  `injection_signals text[]`, `embedding vector(384)`, timestamps.
- Indexes: `ix_document_chunks_embedding_hnsw` (HNSW, `vector_cosine_ops`), `ix_document_chunks_document_id`.
- Similarity score returned by search = `1 - cosine_distance` (embeddings are L2-normalized).
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384 dims), local and independent of the chat LLM.
  Changing the chat model never requires re-embedding; changing the embedding model requires a migration and re-indexing.
- Apply just this branch: `alembic upgrade rag@head`.
