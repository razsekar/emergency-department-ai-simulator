# API

OpenAPI/Swagger UI: http://localhost:8000/api/docs  (schema: `/api/openapi.json`).
All routes are under `/api`.

## Implemented
| Method | Path | Description |
|---|---|---|
| GET | /api/health | Liveness |
| GET | /api/health/db | DB connectivity and pgvector presence |

Error shape: `{"error": {"code": "...", "message": "..."}}`.
Further endpoints are added per phase.

## Auth and audit
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /api/auth/login | none | `{username, password}` returns bearer token, `expires_in`, user with roles and permissions. Failures are a uniform 401. |
| GET | /api/auth/me | bearer | Current user (roles/permissions re-read from the DB on every request) |
| GET | /api/audit/events | bearer, `audit:read` (admin) | Paginated (`limit` 1-200, `offset`); filters `action` (prefix), `actor`, `outcome` |

Roles: viewer (read-only), presenter (viewer + scenario apply/reset, upload, chat, agent, comparison),
admin (all, incl. models:configure and audit:read). Errors: 401 `unauthenticated`, 403 `forbidden`,
500 `auth_not_configured` (JWT_SECRET missing or shorter than 32 chars; fails closed).

Other modules enforce RBAC via `from app.modules.identity.public import Permission, require_permission`:
`Depends(require_permission(Permission.SCENARIO_APPLY))`. Emit audit records by publishing
`app.platform.audit_events.AuditEvent` on the event bus (or `audit.public.record`).

## Simulation, queue, resources, dashboard (no auth yet)
| Method | Path | Description |
|---|---|---|
| GET | /api/scenarios | Built-in scenarios with parameters; `is_current` flag |
| GET | /api/scenarios/current | Data state: `data_version`, scenario key/name, `applied_at` |
| GET | /api/scenarios/history?limit&offset | Run history incl. failed attempts |
| POST | /api/scenarios/apply | `{scenario_key: normal|surge|recovery|custom, overrides?: {...}}`; any override makes a Custom Scenario; atomic |
| POST | /api/scenarios/randomize | Random valid parameters (retries up to 5 seeds) |
| POST | /api/scenarios/reset | Re-applies the baseline; `data_version` still increases |
| GET | /api/dashboard/metrics?bucket_minutes&window_minutes | All dashboard metrics, computed from records |
| GET | /api/dashboard/resource-utilization | Bed/doctor/nurse utilization, facility load, department capacity |
| GET | /api/patient-queue | Filters: status, department, triage_category, investigation_status, min/max_wait_minutes, arrived_within_minutes; `page`, `page_size` (max 200) |
| GET | /api/patient-queue/waiting-metrics?department&window_minutes | avg/max wait, distribution |
| GET | /api/patient-queue/pending-investigations?department&limit | Pending requests with age and delay |
| GET | /api/resources/beds/availability, /staff/availability, /departments, /facilities | Availability and capacity |
| GET | /api/resources/beds, /api/resources/staff | Paginated lists (filters: department, status, role) |

Scenario validation failures return 422 `{"error": {"code": "scenario_validation_failed", ...}}`.

## Knowledge base and RAG
All routes need a bearer token. Read = `knowledge:read` (viewer+); upload/delete/load-samples = `knowledge:upload` (presenter+).
| Method | Path | Description |
|---|---|---|
| POST | /api/knowledge/documents | Multipart upload (`file`, optional `name`). PDF only, max `KB_MAX_UPLOAD_MB` (default 10). 415 not a PDF, 413 too large, 422 unreadable/no text, 409 duplicate. Returns the document once indexing finished (`status` = indexed/failed). |
| POST | /api/knowledge/documents/load-samples | Ingest the 6 fictional demo PDFs from `KB_SAMPLE_DOCS_DIR` (default `/sample_docs`); already-loaded files are skipped. |
| GET | /api/knowledge/documents?limit&offset | Paginated list (`items`, `total`, `limit`, `offset`). |
| GET | /api/knowledge/documents/{id} | One document. |
| DELETE | /api/knowledge/documents/{id} | Delete document and its chunks (204). |
| POST | /api/rag/search | `{query, k}` (k 1-20) returns `results[]` (document_name, page_number, excerpt, score, injection_flagged/signals), `embedding_model`, and `llm_context` (delimited UNTRUSTED-DATA block; flagged excerpts withheld). |

Config (env): `KB_MAX_UPLOAD_MB`, `KB_MAX_PAGES`, `KB_SAMPLE_DOCS_DIR`, `RAG_CHUNK_SIZE` (700), `RAG_CHUNK_OVERLAP` (120), `RAG_EMBEDDING_MODEL`, `HF_HOME`.
Uploads and deletes publish audit events (`knowledge.document.upload` / `.delete`).

## Model providers (module `model_providers`, migration 0300, branch label `providers`)
All routes need a bearer token. LiteLLM 1.110.x is the only SDK used, and only inside `infrastructure/litellm_gateway.py`.

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | /api/providers/status | models:read | Per provider: `configured`, `cloud`, `data_disclosure`, `detail`. `?probe=true` also checks Ollama reachability. Never returns key values. |
| GET | /api/providers/models | models:read | Models from env (`ANTHROPIC_MODELS`, `OPENAI_MODELS`, `GEMINI_MODELS`, comma separated), DB-registered models, and Ollama (`/api/tags` of `OLLAMA_BASE_URL`). `supports_tools` is `true`/`false` only when LiteLLM knows the model, otherwise `null` (unknown). No model ids are hardcoded. |
| POST | /api/providers/chat | ai:chat | `{provider, model, messages, temperature?, max_tokens?, tools?, tool_choice?}` returns content, `tool_calls` (passed through unvalidated for the agent loop), `usage`, `estimated_cost_usd` (null if LiteLLM cannot price the model), `latency_ms`, `tool_calling_supported`, `cloud`, `data_disclosure`, `temperature_applied`. |
| POST | /api/providers/chat/stream | ai:chat | Same body; Server-Sent Events `start`, `delta`, `done` (carries the full response incl. usage/cost/latency) or `error`. Not-configured/invalid requests fail with a normal HTTP 409/422 before streaming starts. |
| POST | /api/providers/models | models:configure | Register a model id (204). |
| DELETE | /api/providers/models/{provider}/{model_id} | models:configure | Disable a registered model (204; 422 if not registered). |

Errors: 409 `provider_not_configured` (message names the env var to set), 422 `invalid_model`, 502 `provider_error` (generic; provider text is not echoed). Temperature is dropped, with `temperature_applied=false`, only when LiteLLM positively reports it unsupported for the model.
Env: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL`, `*_MODELS`. Ollama is "configured" by default; use `?probe=true` to check it is reachable. Models are never pulled automatically.
Other modules use `app.modules.model_providers.public` (`complete`, `stream`, `list_models`, `provider_status`).

## Agent and chat (agent_tools, ai_orchestration)
All require a bearer token. `agent:run` (presenter, admin) for `/api/agent/*`; `ai:chat` for `/api/chat/*`.

| Method | Path | Description |
|---|---|---|
| GET | /api/agent/tools | The 7 approved tools with simplified JSON schemas |
| GET | /api/agent/demo-question | The fixed demonstration question |
| POST | /api/agent/run | `{question, provider, model, temperature?, mode?}` runs the bounded agent loop |
| POST | /api/agent/demo-run | `{provider, model, temperature?, mode?}`; the question is fixed server-side and cannot be overridden |
| GET | /api/agent/runs | History, newest first. Filters: `run_type` (agent/demo), `scenario_key`, `data_version`; `limit` 1-100, `offset` |
| GET | /api/agent/runs/{id} | Full run, including every tool's arguments and output |
| POST/GET | /api/chat/sessions | Create / list the caller's conversations |
| GET | /api/chat/sessions/{id} | Conversation with messages (owner only; others get 404) |
| POST | /api/chat/sessions/{id}/messages | `{content, provider, model, temperature?, use_rag?, include_live_data?}` |
| POST | /api/chat/sessions/{id}/messages/stream | Same, as Server-Sent Events: `sources`, `delta`*, `done` (or `error`) |

**Run response** carries: `answer`, `status`, `mode` (`native` | `fallback`) and `fallback_reason`, `scenario_key/name`,
`data_version`, `data_version_consistent` (false if the data changed during the run), `snapshot_metrics` (the numbers to check
an answer against), `tools_executed[]` (status, arguments, validated output, duration), `retrieved_policies[]`
(document, page, score, excerpt, flagged), `citation_check` (every `[Source: doc, p.N]` in the answer verified against what
was actually retrieved), `provider`, `model`, `llm_calls`, `latency_ms`, `usage`, `estimated_cost_usd`, `data_disclosure`.

**Agent behaviour.** Native tool calling when the model is known to support it (`mode=auto`); otherwise a labelled deterministic
plan (waiting metrics, beds, staff, pending investigations, then policy retrieval with topics derived from the observed
metrics) followed by one LLM call. At most **5 tool executions** per request; further calls are refused and recorded as
`refused`. Tool failures and invalid arguments are returned to the model as structured errors, never raised. Nothing is cached:
each run takes a fresh snapshot and every tool reads live data. Policy text is wrapped as untrusted data; chunks flagged by the
injection heuristics are withheld from the model. Errors: 409 `provider_not_configured`, 502 `provider_error`,
502 `agent_run_failed` (failed runs are still stored), 404 unknown run/conversation, 422 invalid input.
