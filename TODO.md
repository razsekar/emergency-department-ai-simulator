# TODO

Items are checked only when implemented AND verified (evidence in brackets).

## Phase 1: Foundation
- [x] Repo hygiene, .env.example
- [x] docker-compose: db (pgvector), backend, frontend, optional ollama profile [stack up, backend/db healthy, frontend 200]
- [x] FastAPI skeleton, health endpoints [GET :4200/api/health and /api/health/db via nginx proxy OK, pgvector true]
- [x] Alembic: baseline + 4 module branches, `upgrade heads` [4 heads applied]
- [x] Architecture tests [fail on deliberate violations; pass on real code]
- [x] Angular shell, 10 stub routes, SIMULATION MODE banner [agent: build + 4 tests + docker build pass]
- [ ] Visually confirm status chips in a browser (not yet looked at)
- [ ] Commit

## Phase 2: Database and synthetic data
- [x] Schema + migration 0100, deterministic seeds [233-test suite; targets 12/15.0/5, 38/75.0/28, 9/18.0/4]
- [x] Normal / Surge / Recovery validated after seeding

## Phase 3: Simulation engine (backend)
- [x] Atomic apply/reset/randomize/manual overrides, data_version, history [tests incl. rollback]
- [x] Dashboard metrics, queue, resources endpoints
- [ ] Verify against the running app over HTTP (not just tests)
- [ ] Wire RBAC and audit events into these endpoints
- [ ] Frontend screens (dashboard, queue, resources, simulator)

## Phase 4: RAG (backend)
- [x] 6 fictional sample PDFs, ingestion, chunking, MiniLM embeddings, pgvector search, injection flagging [tests]
- [ ] Upload over HTTP with a real login
- [ ] Frontend knowledge-base screen with citations

## Phase 5: Generative AI
- [x] LiteLLM provider layer, status, discovery, chat + SSE [mocked tests only]
- [ ] Real call to at least one provider (needs your API key or Ollama)
- [ ] Chat/playground frontend

## Identity / Audit
- [x] Login, JWT, RBAC, audit log [tests]
- [ ] Set JWT_SECRET and DEMO_*_PASSWORD in .env, run seed (user action)
- [ ] Login rate limiting

## Phase 6: Agentic AI (pending)
- Tools must call module public interfaces; send targeted RAG queries per finding (the broad fixed question retrieves poorly).
## Phase 7: Model comparison (pending)
## Phase 8: Demonstration mode, fixed question, side-by-side (pending)
## Phase 9: Testing and documentation (pending)

## Notes
- Host is macOS 13: local Angular builds need `NG_BUILD_SASS_EMBEDDED=false`; Docker builds are unaffected.
- Cost estimates use LiteLLM's bundled price map and may be slightly out of date.
- Which provider keys will you have for the seminar? (unanswered)
