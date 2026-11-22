# Architecture

Educational Emergency Department Patient Flow Simulator. **Synthetic data only.**

## Style: strict modular monolith
One FastAPI app, one PostgreSQL (pgvector) database, one Angular SPA. No microservices.

```
Angular SPA (:4200, nginx) --/api--> FastAPI (:8000) --> PostgreSQL + pgvector (:5433 on host)
                                         |--> LLM providers via LiteLLM (Phase 5+)
                                         '--> Ollama (optional profile)
```

## Backend layout
`backend/app/main.py` is the composition root. `backend/app/platform/` is a minimal shared kernel
(config, DB session/unit of work, event bus, errors, health) with **no business logic**.
`backend/app/modules/<name>/{api,application,domain,infrastructure,public.py}` for each of:
identity, simulation, patient_queue, resource_management, analytics, knowledge_base, rag,
ai_orchestration, agent_tools, model_providers, audit.

## Allowed dependency direction
- `api -> application -> domain`; `infrastructure` implements ports. API controllers hold no persistence logic.
- Another module may be imported **only** through `app.modules.<other>.public`.
- The module graph is acyclic. Planned direction:
  `ai_orchestration -> agent_tools -> {analytics, rag, simulation, patient_queue, resource_management}`;
  `rag -> knowledge_base`; `simulation -> {patient_queue, resource_management}`;
  `analytics -> {patient_queue, resource_management}`; `ai_orchestration -> model_providers`.
  Reverse notifications use in-process events. `audit` subscribes to events.
- `platform/` never imports modules.
- Each module owns one PostgreSQL schema and writes only to its own tables. Cross-module
  references are opaque UUIDs (no cross-schema foreign keys).

Enforced by `backend/tests/architecture/test_module_boundaries.py` (AST-based). Currently run
against the empty skeleton; they gain meaning as code lands in each module.

## Scenario apply (Phase 3): one transaction
validate -> open unit of work -> each owning module replaces its own dataset via its `public.py`
-> bump `data_version` -> write scenario_runs -> commit. Any exception rolls everything back.

## Runtime notes
- Backend runs on Python 3.12 in Docker (host Python 3.14 lacks ML wheels).
- Container runtime on this machine is Colima (`colima start`).
- Provider API keys live only in backend env (`.env`), never in the frontend.
