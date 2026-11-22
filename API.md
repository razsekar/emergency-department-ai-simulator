# API Reference

Educational simulation: all data is synthetic. Base path `/api`. Interactive docs (Swagger UI):
http://localhost:8000/api/docs, schema: http://localhost:8000/api/openapi.json (also reachable through the
frontend proxy at http://localhost:4200/api/...).

The endpoint sections below were generated from the live OpenAPI document (52 operations, checked 2026-11-22) plus the
`require_permission` and `rate_limit` dependencies found in the routers. `*` after a field name means required. Field lists are
summaries; the OpenAPI document is the authority for nested types. OpenAPI does not declare the 401, 403, 413 or 429 responses;
they are described below and in the "Security hardening" section at the end.

## Authentication and access control

- Every endpoint except `GET /api/health`, `GET /api/health/db` and `POST /api/auth/login` requires a bearer token and the
  permission listed under **Access**. Enforcement is server-side (`identity.public.require_permission`); the frontend login guard is
  only a convenience. Checked live on 2026-11-22: anonymous requests to the dashboard, scenarios, patient-queue, resources, knowledge,
  agent, demo, comparison, chat, providers, audit and `auth/me` endpoints each returned 401. The test
  `backend/tests/security/test_rbac_matrix.py` walks the application's OpenAPI document for the same check.
- Sign in with `POST /api/auth/login`; send the returned token as `Authorization: Bearer <token>`.
- Roles and their permissions (source: `backend/app/modules/identity/domain/permissions.py`, seeded by migration 0400):

| Role | Permissions |
|---|---|
| viewer | `dashboard:read`, `queue:read`, `resources:read`, `scenario:read`, `knowledge:read`, `models:read` |
| presenter | viewer + `scenario:apply`, `scenario:reset`, `knowledge:upload`, `ai:chat`, `agent:run`, `comparison:run` |
| admin | all of the above + `models:configure`, `audit:read` |

- Demo users: `demo_admin`, `demo_presenter`, `demo_viewer`. They exist only after you set the `DEMO_*_PASSWORD` variables and run the
  seed command (see README).
- Roles and permissions are re-read from the database on every request.
- Limits: there is no refresh token, token revocation list or multi-factor sign-in; a token stays valid until it expires
  (`JWT_TTL_MINUTES`, default 60).

## Conventions

- **Error envelope:** every error response uses `{"error": {"code": "...", "message": "..."}}`: 401 `unauthenticated`, 403 `forbidden`,
  404 `not_found`, 405 `method_not_allowed`, 413 `payload_too_large`, 422 `validation_error` (field locations and messages only; submitted values are never echoed),
  429 `rate_limited` (with a `Retry-After` header), 500 `internal_error` (always the generic text; details stay in the server log), plus module codes such as
  409 `provider_not_configured` and 502 `provider_error`. 500 `auth_not_configured` means `JWT_SECRET` is missing or shorter than 32 characters.
- **Provider not configured:** HTTP 409 naming the environment variable to set.
- **Pagination:** `limit`/`offset` (most list endpoints) or `page`/`page_size` (patient queue and resource lists); responses carry totals.
- **Streaming:** `/api/providers/chat/stream` and `/api/chat/sessions/{id}/messages/stream` return Server-Sent Events.
- **Uploads:** PDF only; default limit 10 MB (`KB_MAX_UPLOAD_MB`); requests over 12 MB (`MAX_REQUEST_BODY_MB`) are rejected earlier with 413.
- **Rate limits:** endpoints marked with a rate-limit bucket are limited per client (see "Security hardening").
- **Same question, different data:** the demonstration question is fixed in the backend
  (`FIXED_DEMO_QUESTION`, `ai_orchestration/domain/prompts.py`). `/api/demo/step` and `/api/agent/demo-run` never accept a question from the client.

## Endpoints

### agent-tools

#### `GET /api/agent/tools`
- **Access:** `agent:run`
- **Summary:** List Tools
- **200:** `list[ToolDefinition]`

### ai-orchestration

#### `GET /api/agent/demo-question`
- **Access:** `agent:run`
- **Summary:** Demo Question
- **200:** `object`
#### `POST /api/agent/demo-run`
- **Access:** `agent:run` (rate-limit bucket: agent)
- **Summary:** Demo Run
- **Request (application/json):** `DemoRunRequest` — `provider`*: string, `model`*: string, `temperature`: number|null, `mode`: string
- **200:** `AgentRunResponse` — `id`*: string, `run_type`*: string, `question`*: string, `status`*: string, `error`: string|null, `answer`*: string|null, `mode`*: string, `fallback_reason`: string|null, `scenario_key`*: string|null, `scenario_name`*: string|null, `data_version`*: integer|null, `data_version_consistent`*: boolean, `snapshot_metrics`*: object, `tools_executed`*: list[ToolExecutionView], `retrieved_policies`*: list[RetrievedPolicyView], `citation_check`*: object, `provider`*: string, `model`*: string, `temperature`*: number|null, `llm_calls`*: integer, `latency_ms`*: integer, `usage`*: Usage, `estimated_cost_usd`*: number|null, `data_disclosure`*: string|null, `created_by`*: string, `created_at`*: string
#### `POST /api/agent/run`
- **Access:** `agent:run` (rate-limit bucket: agent)
- **Summary:** Run Agent
- **Request (application/json):** `AgentRunRequest` — `question`*: string, `provider`*: string, `model`*: string, `temperature`: number|null, `mode`: string
- **200:** `AgentRunResponse` — `id`*: string, `run_type`*: string, `question`*: string, `status`*: string, `error`: string|null, `answer`*: string|null, `mode`*: string, `fallback_reason`: string|null, `scenario_key`*: string|null, `scenario_name`*: string|null, `data_version`*: integer|null, `data_version_consistent`*: boolean, `snapshot_metrics`*: object, `tools_executed`*: list[ToolExecutionView], `retrieved_policies`*: list[RetrievedPolicyView], `citation_check`*: object, `provider`*: string, `model`*: string, `temperature`*: number|null, `llm_calls`*: integer, `latency_ms`*: integer, `usage`*: Usage, `estimated_cost_usd`*: number|null, `data_disclosure`*: string|null, `created_by`*: string, `created_at`*: string
#### `GET /api/agent/runs`
- **Access:** `agent:run`
- **Summary:** List Runs
- **Parameters:** `limit` (query: integer), `offset` (query: integer), `run_type` (query: ?), `scenario_key` (query: ?), `data_version` (query: ?)
- **200:** `app__modules__ai_orchestration__application__contracts__RunPage` — `items`*: list[RunSummary], `total`*: integer, `limit`*: integer, `offset`*: integer
#### `GET /api/agent/runs/{run_id}`
- **Access:** `agent:run`
- **Summary:** Get Run
- **Parameters:** `run_id` (path, required: string)
- **200:** `AgentRunResponse` — `id`*: string, `run_type`*: string, `question`*: string, `status`*: string, `error`: string|null, `answer`*: string|null, `mode`*: string, `fallback_reason`: string|null, `scenario_key`*: string|null, `scenario_name`*: string|null, `data_version`*: integer|null, `data_version_consistent`*: boolean, `snapshot_metrics`*: object, `tools_executed`*: list[ToolExecutionView], `retrieved_policies`*: list[RetrievedPolicyView], `citation_check`*: object, `provider`*: string, `model`*: string, `temperature`*: number|null, `llm_calls`*: integer, `latency_ms`*: integer, `usage`*: Usage, `estimated_cost_usd`*: number|null, `data_disclosure`*: string|null, `created_by`*: string, `created_at`*: string
#### `GET /api/chat/sessions`
- **Access:** `ai:chat`
- **Summary:** List Sessions
- **Parameters:** `limit` (query: integer), `offset` (query: integer)
- **200:** `list[ChatSessionView]`
#### `POST /api/chat/sessions`
- **Access:** `ai:chat`
- **Summary:** Create Session
- **Request (application/json):** `CreateSessionRequest` — `title`: string
- **201:** `ChatSessionView` — `id`*: string, `title`*: string, `created_at`*: string, `updated_at`*: string
#### `GET /api/chat/sessions/{session_id}`
- **Access:** `ai:chat`
- **Summary:** Get Session
- **Parameters:** `session_id` (path, required: string)
- **200:** `ChatSessionDetail` — `id`*: string, `title`*: string, `created_at`*: string, `updated_at`*: string, `messages`*: list[ChatMessageView]
#### `POST /api/chat/sessions/{session_id}/messages`
- **Access:** `ai:chat` (rate-limit bucket: chat)
- **Summary:** Send Message
- **Parameters:** `session_id` (path, required: string)
- **Request (application/json):** `SendMessageRequest` — `content`*: string, `provider`*: string, `model`*: string, `temperature`: number|null, `use_rag`: boolean, `include_live_data`: boolean
- **200:** `SendMessageResponse` — `user_message`*: ChatMessageView, `assistant_message`*: ChatMessageView, `usage`*: Usage, `estimated_cost_usd`: number|null
#### `POST /api/chat/sessions/{session_id}/messages/stream`
- **Access:** `ai:chat` (rate-limit bucket: chat)
- **Summary:** Stream Message
- **Parameters:** `session_id` (path, required: string)
- **Request (application/json):** `SendMessageRequest` — `content`*: string, `provider`*: string, `model`*: string, `temperature`: number|null, `use_rag`: boolean, `include_live_data`: boolean
- **200:** Successful Response
#### `POST /api/comparison/run`
- **Access:** `comparison:run` (rate-limit bucket: agent)
- **Summary:** Demonstration comparison (not a benchmark): every model answers from the same frozen data and context.
- **Request (application/json):** `ComparisonRunRequest` — `question`: string, `selections`*: list[ModelSelection]
- **200:** `ComparisonRunResponse` — `id`*: string, `label`: string, `scoring_note`: string, `question`*: string, `status`*: string, `data_version_consistent`*: boolean, `identical_context_verified`*: boolean, `shared_context`*: SharedContextView, `results`*: list[ModelResultView], `created_by`*: string, `created_at`*: string
#### `GET /api/comparison/runs`
- **Access:** `comparison:run`
- **Summary:** List Comparison Runs
- **Parameters:** `limit` (query: integer), `offset` (query: integer), `data_version` (query: ?)
- **200:** `ComparisonPage` — `items`*: list[ComparisonSummary], `total`*: integer, `limit`*: integer, `offset`*: integer
#### `GET /api/comparison/runs/{comparison_id}`
- **Access:** `comparison:run`
- **Summary:** Get Comparison Run
- **Parameters:** `comparison_id` (path, required: string)
- **200:** `ComparisonRunResponse` — `id`*: string, `label`: string, `scoring_note`: string, `question`*: string, `status`*: string, `data_version_consistent`*: boolean, `identical_context_verified`*: boolean, `shared_context`*: SharedContextView, `results`*: list[ModelResultView], `created_by`*: string, `created_at`*: string
#### `GET /api/demo/question`
- **Access:** `agent:run`
- **Summary:** Question
- **200:** `object`
#### `GET /api/demo/session`
- **Access:** `agent:run`
- **Summary:** Session
- **200:** `DemoSessionView` — `session_id`*: string|null, `question`*: string, `question_sha256`*: string, `run_count`*: integer, `runs`*: list[DemoRunView], `metric_comparison`*: list[MetricComparisonRow]
#### `POST /api/demo/session/reset`
- **Access:** `scenario:reset`
- **Summary:** Reset
- **200:** `DemoResetResponse` — `cleared_runs`*: integer, `baseline_scenario`*: string, `data_version`*: integer
#### `POST /api/demo/step`
- **Access:** `scenario:apply` AND `agent:run` (rate-limit bucket: agent)
- **Summary:** Step
- **Request (application/json):** `DemoStepRequest` — `scenario`*: string, `provider`*: string, `model`*: string, `temperature`: number|null, `mode`: string
- **200:** `DemoStepResponse` — `run`*: DemoRunView, `run_count`*: integer, `metric_comparison`*: list[MetricComparisonRow]

### audit

#### `GET /api/audit/events`
- **Access:** `audit:read`
- **Summary:** List Events
- **Parameters:** `limit` (query: integer), `offset` (query: integer), `action` (query: ?), `actor` (query: ?), `outcome` (query: ?)
- **200:** `AuditPage` — `items`*: list[AuditRecord], `total`*: integer, `limit`*: integer, `offset`*: integer

### auth

#### `POST /api/auth/login`
- **Access:** public
- **Summary:** Login
- **Request (application/json):** `LoginRequest` — `username`*: string, `password`*: string
- **200:** `TokenResponse` — `access_token`*: string, `token_type`*: string, `expires_in`*: integer, `user`*: UserResponse
#### `GET /api/auth/me`
- **Access:** any signed-in user
- **Summary:** Me
- **200:** `UserResponse` — `id`*: string, `username`*: string, `display_name`*: string, `roles`*: list[string], `permissions`*: list[string]

### dashboard

#### `GET /api/dashboard/metrics`
- **Access:** `dashboard:read`
- **Summary:** Metrics
- **Parameters:** `bucket_minutes` (query: integer), `window_minutes` (query: integer)
- **200:** `DashboardMetrics` — `data_version`*: integer, `scenario_key`*: string|null, `scenario_name`*: string|null, `as_of`*: string|null, `total_visits`*: integer, `patients_waiting`*: integer, `patients_in_treatment`*: integer, `completed_discharges`*: integer, `critical_patients`*: integer, `beds`*: BedSummary, `staff`*: list[StaffSummary], `avg_wait_minutes`*: number, `max_wait_minutes`*: number, `pending_investigations`*: integer, `avg_pending_investigation_age_minutes`*: number, `avg_pending_investigation_delay_minutes`*: number, `department_workload`*: list[DepartmentWorkload], `arrivals_over_time`*: list[ArrivalPoint], `waiting_time_distribution`*: list[WaitBucket], `resource_utilization`*: ResourceUtilization
#### `GET /api/dashboard/resource-utilization`
- **Access:** `dashboard:read`
- **Summary:** Resource Utilization
- **200:** `ResourceUtilization` — `data_version`*: integer, `beds_pct`*: number, `doctors_pct`*: number, `nurses_pct`*: number, `facilities`*: list[FacilityLoad], `departments`*: list[object]

### health

#### `GET /api/health`
- **Access:** public
- **Summary:** Live
- **200:** `LiveResponse` — `status`*: string
#### `GET /api/health/db`
- **Access:** public
- **Summary:** Db Health
- **200:** `DbHealthResponse` — `status`*: string, `pgvector`*: boolean

### knowledge-base

#### `GET /api/knowledge/documents`
- **Access:** `knowledge:read`
- **Summary:** List Documents
- **Parameters:** `limit` (query: integer), `offset` (query: integer)
- **200:** `DocumentPage` — `items`*: list[DocumentOut], `total`*: integer, `limit`*: integer, `offset`*: integer
#### `POST /api/knowledge/documents`
- **Access:** `knowledge:upload` (rate-limit bucket: upload)
- **Summary:** Upload
- **Request (multipart/form-data):** `Body_upload_api_knowledge_documents_post` — `file`*: string, `name`: string|null
- **201:** `DocumentOut` — `id`*: string, `name`*: string, `original_filename`*: string, `size_bytes`*: integer, `page_count`*: integer, `status`*: string, `chunk_count`*: integer, `error_message`*: string|null, `is_sample`*: boolean, `created_at`*: string, `updated_at`*: string
#### `POST /api/knowledge/documents/load-samples`
- **Access:** `knowledge:upload` (rate-limit bucket: upload)
- **Summary:** Load Samples
- **200:** `SampleLoadResult` — `loaded`*: list[string], `skipped`*: list[string]
#### `DELETE /api/knowledge/documents/{document_id}`
- **Access:** `knowledge:upload`
- **Summary:** Delete Document
- **Parameters:** `document_id` (path, required: string)
- **204:** Successful Response
#### `GET /api/knowledge/documents/{document_id}`
- **Access:** `knowledge:read`
- **Summary:** Get Document
- **Parameters:** `document_id` (path, required: string)
- **200:** `DocumentOut` — `id`*: string, `name`*: string, `original_filename`*: string, `size_bytes`*: integer, `page_count`*: integer, `status`*: string, `chunk_count`*: integer, `error_message`*: string|null, `is_sample`*: boolean, `created_at`*: string, `updated_at`*: string

### model-providers

#### `POST /api/providers/chat`
- **Access:** `ai:chat` (rate-limit bucket: chat)
- **Summary:** Chat
- **Request (application/json):** `ChatRequest` — `provider`*: string, `model`*: string, `messages`*: list[ChatMessage], `temperature`: number|null, `max_tokens`: integer|null, `tools`: array|null, `tool_choice`: string|object|null
- **200:** `ChatResponse` — `provider`*: string, `model`*: string, `content`*: string|null, `tool_calls`: list[ToolCall], `finish_reason`: string|null, `usage`: Usage, `estimated_cost_usd`: number|null, `latency_ms`*: integer, `tool_calling_supported`: boolean|null, `cloud`*: boolean, `data_disclosure`: string|null, `temperature_applied`: boolean
#### `POST /api/providers/chat/stream`
- **Access:** `ai:chat` (rate-limit bucket: chat)
- **Summary:** Chat Stream
- **Request (application/json):** `ChatRequest` — `provider`*: string, `model`*: string, `messages`*: list[ChatMessage], `temperature`: number|null, `max_tokens`: integer|null, `tools`: array|null, `tool_choice`: string|object|null
- **200:** Successful Response
#### `GET /api/providers/models`
- **Access:** `models:read`
- **Summary:** Models
- **200:** `list[ModelInfo]`
#### `POST /api/providers/models`
- **Access:** `models:configure`
- **Summary:** Register Model
- **Request (application/json):** `RegisterModelRequest` — `provider`*: string, `model_id`*: string, `display_name`: string|null
- **204:** Successful Response
#### `DELETE /api/providers/models/{provider}/{model_id}`
- **Access:** `models:configure`
- **Summary:** Unregister Model
- **Parameters:** `provider` (path, required: string), `model_id` (path, required: string)
- **204:** Successful Response
#### `GET /api/providers/status`
- **Access:** `models:read`
- **Summary:** Status
- **Parameters:** `probe` (query: boolean)
- **200:** `list[ProviderStatus]`

### patient-queue

#### `GET /api/patient-queue`
- **Access:** `queue:read`
- **Summary:** Queue
- **Parameters:** `status` (query: ?), `department` (query: ?), `triage_category` (query: ?), `investigation_status` (query: ?), `min_wait_minutes` (query: ?), `max_wait_minutes` (query: ?), `arrived_within_minutes` (query: ?), `page` (query: integer), `page_size` (query: integer)
- **200:** `QueuePage` — `items`*: list[QueueRow], `total`*: integer, `page`*: integer, `page_size`*: integer, `as_of`*: string|null
#### `GET /api/patient-queue/pending-investigations`
- **Access:** `queue:read`
- **Summary:** Pending Investigations
- **Parameters:** `department` (query: ?), `limit` (query: integer)
- **200:** `PendingInvestigations` — `as_of`*: string|null, `pending_count`*: integer, `avg_age_minutes`*: number, `max_age_minutes`*: number, `avg_delay_minutes`*: number, `by_facility`*: list[FacilityPending], `items`*: list[PendingInvestigationItem]
#### `GET /api/patient-queue/waiting-metrics`
- **Access:** `queue:read`
- **Summary:** Waiting Metrics
- **Parameters:** `department` (query: ?), `window_minutes` (query: ?)
- **200:** `WaitingMetrics` — `as_of`*: string|null, `waiting_patients`*: integer, `avg_wait_minutes`*: number, `max_wait_minutes`*: number, `distribution`*: list[WaitBucket]

### rag

#### `POST /api/rag/search`
- **Access:** `knowledge:read`
- **Summary:** Search
- **Request (application/json):** `SearchRequest` — `query`*: string, `k`: integer
- **200:** `SearchResponse` — `query`*: string, `embedding_model`*: string, `results`*: list[ChunkOut], `llm_context`*: string

### resources

#### `GET /api/resources/beds`
- **Access:** `resources:read`
- **Summary:** Beds
- **Parameters:** `department` (query: ?), `status` (query: ?), `page` (query: integer), `page_size` (query: integer)
- **200:** `BedPage` — `items`*: list[BedRow], `total`*: integer, `page`*: integer, `page_size`*: integer
#### `GET /api/resources/beds/availability`
- **Access:** `resources:read`
- **Summary:** Bed Availability
- **Parameters:** `department` (query: ?)
- **200:** `BedAvailability` — `total_beds`*: integer, `occupied_beds`*: integer, `available_beds`*: integer, `utilization_pct`*: number, `by_department`*: list[DepartmentBeds]
#### `GET /api/resources/departments`
- **Access:** `resources:read`
- **Summary:** Departments
- **200:** `list[DepartmentCapacity]`
#### `GET /api/resources/facilities`
- **Access:** `resources:read`
- **Summary:** Facilities
- **200:** `list[Facility]`
#### `GET /api/resources/staff`
- **Access:** `resources:read`
- **Summary:** Staff
- **Parameters:** `department` (query: ?), `role` (query: ?), `status` (query: ?), `page` (query: integer), `page_size` (query: integer)
- **200:** `StaffPage` — `items`*: list[StaffRow], `total`*: integer, `page`*: integer, `page_size`*: integer
#### `GET /api/resources/staff/availability`
- **Access:** `resources:read`
- **Summary:** Staff Availability
- **Parameters:** `department` (query: ?), `role` (query: ?)
- **200:** `StaffAvailability` — `on_duty`*: integer, `available`*: integer, `busy`*: integer, `totals_by_role`*: list[RoleTotals], `groups`*: list[StaffGroup]

### scenarios

#### `GET /api/scenarios`
- **Access:** `scenario:read`
- **Summary:** List Scenarios
- **200:** `list[ScenarioInfo]`
#### `POST /api/scenarios/apply`
- **Access:** `scenario:apply`
- **Summary:** Apply
- **Request (application/json):** `ApplyRequest` — `scenario_key`*: string, `overrides`: ScenarioOverrides|null
- **200:** `ApplyResponse` — `state`*: DataState, `run`*: ScenarioRunInfo
#### `GET /api/scenarios/current`
- **Access:** `scenario:read`
- **Summary:** Current State
- **200:** `DataState` — `data_version`*: integer, `scenario_key`*: string|null, `scenario_name`*: string|null, `applied_at`*: string|null, `last_run_id`*: string|null
#### `GET /api/scenarios/history`
- **Access:** `scenario:read`
- **Summary:** History
- **Parameters:** `limit` (query: integer), `offset` (query: integer)
- **200:** `app__modules__simulation__application__schemas__RunPage` — `items`*: list[ScenarioRunInfo], `total`*: integer, `limit`*: integer, `offset`*: integer
#### `POST /api/scenarios/randomize`
- **Access:** `scenario:apply`
- **Summary:** Randomize
- **200:** `ApplyResponse` — `state`*: DataState, `run`*: ScenarioRunInfo
#### `POST /api/scenarios/reset`
- **Access:** `scenario:reset`
- **Summary:** Reset
- **200:** `ApplyResponse` — `state`*: DataState, `run`*: ScenarioRunInfo

---

## Appendix: behavior notes per module

Written by the module authors against their code at commit `adf9552`. If a table here disagrees with the generated
endpoint reference above, the generated reference (live OpenAPI) wins. Not independently re-verified by running the endpoints.

### Simulation, queue, resources, dashboard
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

### Knowledge base and RAG
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

### Model providers (module `model_providers`, migration 0300, branch label `providers`)
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

### Agent and chat (agent_tools, ai_orchestration)
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

### Demonstration mode (same question, different data)
Fixed question is a backend constant (clients cannot change it). Steps are serialized (one at a time).

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | /api/demo/question | `agent:run` | The fixed demonstration question |
| POST | /api/demo/step | `agent:run` + `scenario:apply` | `{scenario: normal\|surge\|recovery, provider, model, temperature?, mode?}`. Applies the scenario atomically through the simulation module, verifies the data version and metrics changed, asks the fixed question on live data (no caching), saves it as the next "Run N". Returns the run, `run_count` and `metric_comparison`. |
| GET | /api/demo/session | `agent:run` | Saved runs with scenario name, data version, patient record count, metrics, tools executed, retrieved policies, final answer, provider/model, latency, tokens, per-run `verification`, plus `metric_comparison` (per metric: values per run, `differs`, deltas vs previous run, derived from data) |
| POST | /api/demo/session/reset | `scenario:reset` | Reloads the Normal baseline (data_version still increases) and deletes the saved demo runs so the demo can be replayed |

A step refuses to continue (409 `demo_verification_failed`) if the data version did not change after applying the
scenario, or if the agent run did not use the fixed question on that data version. A failed step saves no demo run;
if the scenario was already applied it stays applied (its data_version advanced). If the scenario is already loaded,
the step still advances the version and reports `metrics_changed: false` with a note. Audit actions: `demo.step`, `demo.reset`.

### Model comparison (Phase 7)
**Demonstration comparison, not a formal benchmark.** One scenario snapshot, one set of tool results and one
retrieved policy context are computed first; every selected model then answers from the byte-identical frozen prompt
(`context_sha256`, recorded per model and verified equal). Models answer sequentially. Permission: `comparison:run`
(presenter, admin). Each run publishes a `comparison.run` audit event.

| Method | Path | Description |
|---|---|---|
| POST | /api/comparison/run | `{question?, selections:[{provider, model, temperature?}]}` with 2-6 unique selections. `question` defaults to the fixed demonstration question. |
| GET | /api/comparison/runs | Paginated history (`limit` 1-100, `offset`, `data_version` filter), newest first |
| GET | /api/comparison/runs/{id} | One full run |

Response: `label`, `scoring_note`, `status` (`completed` / `partial` / `failed`), `data_version_consistent`,
`identical_context_verified`, `shared_context` (scenario, data_version, snapshot_metrics, tools_executed,
retrieved_policies, context_sha256) and `results[]` per selection: status (`completed` / `failed` / `not_configured`),
answer, latency_ms (same wall-clock measure for all), usage, estimated_cost_usd (null when unknown, never guessed),
tool_calling_supported, data_disclosure, scores, citation_check.

- Unconfigured models are reported (`not_configured` with the env var to set), never silently dropped; one model
  failing does not fail the run. If none can be used: 409 `no_model_available`.
- If the data changes while the shared context is being prepared: 409 `data_changed_during_comparison`, no model is
  called. If it changes while models answer, the run is stored with `data_version_consistent=false`.
- Scoring (heuristics documented in `domain/comparison_scoring.py`): `accuracy` (8 key metrics compared with the true
  snapshot; wrong numbers listed), `completeness` (5 sections + citation + scenario/version stated), `relevance`
  (6 topic groups, minus 0.25 for clinical-advice terms), `citation_correctness` (verified / total against what was
  actually retrieved; null when nothing is cited) and `overall_demo_score` (mean of the available scores).
  The scores cannot judge reasoning quality and can miss unusual phrasings of a correct number.

---

## Security hardening: RBAC, rate limits, error hygiene

Every `/api` endpoint except `GET /api/health`, `GET /api/health/db` and `POST /api/auth/login` requires a bearer token.
Authorization is enforced server-side by `identity.public.require_permission`; the frontend is only a convenience.
`tests/security/test_rbac_matrix.py` walks the real application's OpenAPI document and fails if any other route
answers an anonymous request with something other than 401.

Roles: **viewer** (read-only), **presenter** (viewer + scenario apply/reset, upload, chat, agent, comparison),
**admin** (everything, including `models:configure` and `audit:read`). Permission sets live in
`backend/app/modules/identity/domain/permissions.py`.

| Endpoint | Permission | viewer | presenter | admin |
|---|---|:-:|:-:|:-:|
| `GET /api/scenarios`, `/current`, `/history` | `scenario:read` | yes | yes | yes |
| `POST /api/scenarios/apply`, `/randomize` | `scenario:apply` | no | yes | yes |
| `POST /api/scenarios/reset` | `scenario:reset` | no | yes | yes |
| `GET /api/dashboard/metrics`, `/resource-utilization` | `dashboard:read` | yes | yes | yes |
| `GET /api/patient-queue`, `/waiting-metrics`, `/pending-investigations` | `queue:read` | yes | yes | yes |
| `GET /api/resources/beds`, `/beds/availability`, `/staff`, `/staff/availability`, `/departments`, `/facilities` | `resources:read` | yes | yes | yes |
| `GET /api/knowledge/documents`, `/{id}`; `POST /api/rag/search` | `knowledge:read` | yes | yes | yes |
| `POST /api/knowledge/documents`, `/load-samples`; `DELETE /api/knowledge/documents/{id}` | `knowledge:upload` | no | yes | yes |
| `GET /api/providers/status`, `/models` | `models:read` | yes | yes | yes |
| `POST /api/providers/models`; `DELETE /api/providers/models/{provider}/{model_id}` | `models:configure` | no | no | yes |
| `POST /api/providers/chat`, `/chat/stream`; all `/api/chat/sessions...` | `ai:chat` | no | yes | yes |
| `POST /api/agent/run`, `/demo-run`; `GET /api/agent/demo-question`, `/runs`, `/runs/{id}`, `/tools` | `agent:run` | no | yes | yes |
| `GET /api/demo/question`, `/session` | `agent:run` | no | yes | yes |
| `POST /api/demo/step` | `agent:run` and `scenario:apply` | no | yes | yes |
| `POST /api/demo/session/reset` | `scenario:reset` | no | yes | yes |
| `POST /api/comparison/run`; `GET /api/comparison/runs`, `/runs/{id}` | `comparison:run` | no | yes | yes |
| `GET /api/audit/events` | `audit:read` | no | no | yes |
| `GET /api/auth/me` | any signed-in user | yes | yes | yes |

Errors: 401 `unauthenticated`, 403 `forbidden` (also recorded as an `authz.denied` audit event naming the missing permission).

### Audit events added
`scenario.apply`, `scenario.reset`, `scenario.randomize` (success or failure, with actor, scenario and data version; randomize
is audited once, not once per internal retry), `authz.denied`, `auth.lockout`, `ratelimit.exceeded`. Calls made by demo mode
through the simulation public interface carry no actor and are audited by the demo step itself.

### Rate limiting (in-process, sliding window, 429)
A rejected call returns HTTP 429 `{"error": {"code": "rate_limited", ...}}` with a `Retry-After` header. State is in memory, which
matches the documented single-process deployment; it resets on restart. The client key is the peer address plus a hash of the
`Authorization` header (X-Forwarded-For is not trusted because clients can forge it), so different signed-in users behind the nginx
proxy get separate buckets.

| Bucket | Applies to | Default | Env var |
|---|---|---|---|
| agent | `/api/agent/run`, `/api/agent/demo-run`, `/api/demo/step`, `/api/comparison/run` | 30 / min | `RATE_LIMIT_AGENT_PER_MINUTE` |
| chat | `/api/providers/chat`, `/chat/stream`, `/api/chat/sessions/{id}/messages[/stream]` | 60 / min | `RATE_LIMIT_CHAT_PER_MINUTE` |
| upload | `POST /api/knowledge/documents`, `/load-samples` | 20 / min | `RATE_LIMIT_UPLOAD_PER_MINUTE` |

`0` disables one bucket; `RATE_LIMIT_ENABLED=false` disables all. Defaults sit far above what a presenter does in a live demo.

**Login back-off** (per client address + username, including unknown usernames so it cannot be used to probe for valid names):
after `LOGIN_MAX_FAILURES` (5) consecutive failures within `LOGIN_FAILURE_WINDOW_SECONDS` (300) the pair is locked for
`LOGIN_LOCKOUT_BASE_SECONDS` (15) doubling per further failure up to `LOGIN_LOCKOUT_MAX_SECONDS` (300). While locked, even the correct
password gets 429 and the lock is not extended. A success clears the counter. Trade-off: someone who knows a username can lock that
user out for up to five minutes by guessing wrongly; accepted for a single-room demo, and the lock expires on its own.

### Request size, error hygiene, CORS
- `MAX_REQUEST_BODY_MB` (default 12) rejects any request whose `Content-Length` exceeds it with 413 before the body is parsed.
  Chunked requests without a Content-Length are not covered by that check; the upload handler still reads at most `KB_MAX_UPLOAD_MB` (default 10) + 1 bytes
  and validates extension, `%PDF` content and page count.
- Validation errors (422), unknown routes (404), wrong methods (405) and unexpected failures (500) all use the
  `{"error": {"code", "message"}}` envelope. 422 lists field locations and messages only and never echoes submitted values;
  500 is always the generic "Internal server error" and the details stay in the server log.
- Failed scenario runs store the error text only when it is one of our own domain errors; any other exception is stored as
  "Unexpected internal error (see server logs)" so SQL or connection details cannot reach `GET /api/scenarios/history`.
- CORS allows only the origins in `CORS_ORIGINS`, the methods GET/POST/PUT/PATCH/DELETE and the headers Authorization and Content-Type, with no
  credentials. A `*` origin is refused at startup.
