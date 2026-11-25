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

## Phase 6: Agentic AI
- [x] 7 tools, bounded 5-call loop, fallback mode, citation check, run history, demo-run endpoint, chat [302 backend tests pass; scripted fake LLM only]
- [x] /api/agent/* served by the real app after rebuild [401 without token via nginx proxy]
- [x] Real LLM run via Ollama llama3.2:3b, Demo Mode x3 [levels GREEN/RED/GREEN, data-correct, 348/347/415 s]
- [ ] Real run with a cloud model and the Agent screen in a browser: NOT verified
- [ ] Agent Execution screen (frontend)

## Frontend screens (done, verified by agents + 69 unit tests)
- [x] Dashboard, Queue, Resources, Simulator [F1 drove Surge/Baseline in a browser; dashboard matched DB]
- [x] Auth, Knowledge Base, Playground, Assistant, Settings [F2: mocked API in browser; real login untested]
- [ ] Rebuilt Docker frontend viewed by me in a browser; toolbar wraps; bundle 649 kB over 500 kB budget
- [ ] Put routes behind login guard once RBAC wired on backend
## Phase 7: Model comparison
- [x] Backend: shared snapshot/context, per-model answers, scoring heuristics, migration 0600 [370 backend tests pass; scripted fake LLM only]
- [x] Response Comparison screen [mocked API in browser; 128 frontend tests pass]
- [ ] Real multi-model run: NOT verified

## Phase 8: Demonstration mode
- [x] Backend: demo step/session/reset with version + question verification, migration 0700 [tests, incl. mutation check]
- [x] Demo Mode screen, side-by-side Run 1/2/3 [mocked API in browser]
- [ ] Full demo against the real backend with a real LLM: NOT verified (needs JWT secret/demo passwords in .env and a provider)
- [ ] Wire RBAC + audit into simulation/analytics/queue/resource endpoints, then add login guards to routes
- [ ] Rebuilt Docker frontend viewed in a browser by me
## Phase 9: Testing, security, documentation
- [x] RBAC on all endpoints except /api/health* and login; audit events; rate limits; login back-off; body cap; CORS rule [522 backend tests; live server returns 401 unauthenticated, standard 422 envelope]
- [x] Frontend login guard on all routes, 403/401 handling, permission-based UX [148 frontend tests; build 501.98 kB]
- [x] Critical acceptance test over HTTP on the real app (normal->surge->recovery, demo mode, comparison) [scripted fake LLM; stale-cache negative control fails as expected]
- [x] Section 13 gap tests + coverage matrix (tests/e2e, tests/gaps)
- [x] README, ARCHITECTURE, DATABASE, API, DEMO_GUIDE, DEPLOYMENT written (K, O) [auth wording being corrected after hardening]
- [ ] Docs re-checked after hardening (in progress)
- [ ] Clean-start Docker verification (`down -v` then `up`): NOT done
- [ ] Real login + seeded demo users: needs JWT_SECRET and DEMO_*_PASSWORD in .env (user)
- [x] Deterministic escalation level + verified briefing in agent and comparison prompts [582 backend tests pass]
- [x] Ollama context truncation fixed (`OLLAMA_NUM_CTX`), LLM timeout and output cap [tests + real run]
- [ ] Show the computed level in the Demo/Agent screens (backend does not expose it in the API yet)
- [x] Two-model comparison (llama3.2:1b and 3b) and Demo/Agent/Assistant screens run in headless Chrome [2026-11-25]
- [x] nginx proxy timeout raised to 3600 s (UI returned 504 at 300 s) [UI requests of 340-572 s succeeded]
- [x] Comparison accuracy false positives fixed (ratio lines, quoted policy limits) [600 backend tests; 2 saved real answers rescored with no false wrong numbers]
- [x] Uncited paragraphs labelled "No policy citation", headings untagged, comparison disclaimer shown once [150 frontend tests]
- [ ] Browser check of the scorer and label fixes
- [ ] Cloud-model comparison: NOT verified
- [ ] Deployment: unverified on Vercel/Railway; see DEPLOYMENT.md for the fixes needed (PORT, DATABASE_URL scheme, dev deps in image, sample_docs, model cache)

## Notes
- Host is macOS 13: local Angular builds need `NG_BUILD_SASS_EMBEDDED=false`; Docker builds are unaffected.
- Cost estimates use LiteLLM's bundled price map and may be slightly out of date.
- Which provider keys will you have for the seminar? (unanswered)
