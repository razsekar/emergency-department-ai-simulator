# Emergency Department Patient Flow Simulator

> **SIMULATION MODE. Synthetic data only.** Every patient, staff member, bed and policy in this project is invented for education.
> It is **not** a clinical tool: it does not diagnose, recommend treatment, or decide clinical priority. The documents in `sample_docs/`
> are **fictional demonstration policies**, not real hospital protocols. The "triage categories" are simulated labels used to demonstrate data handling.

A hands-on demonstration for a Faculty Development Program on Generative AI, Retrieval-Augmented Generation (RAG) and agentic AI.
You change the simulated hospital's data in front of an audience, ask the **same question**, and show that an LLM agent, using real tools and retrieved policies,
gives a different, evidence-grounded answer.

## What is in it

- **Scenario simulator:** Normal Operations, Emergency Surge, Recovery, randomize, manual parameters, reset, history. Applying a scenario rewrites PostgreSQL records in one transaction and increments a `data_version`.
- **Operations screens:** dashboard (metrics calculated from records), patient queue with filters, resource management.
- **RAG knowledge base:** PDF upload, extraction, chunking, local embeddings (`all-MiniLM-L6-v2`, 384 dimensions), pgvector search, citations with page numbers, basic prompt-injection flagging.
- **Agent:** seven approved backend tools, at most five tool executions per request, labelled fallback mode for models without tool calling, citation verification, run history.
- **Demo Mode:** the fixed question asked under Normal, then Surge, then Recovery, saved as Run 1/2/3 and compared side by side.
- **Model playground and comparison:** Anthropic, OpenAI, Gemini and Ollama through LiteLLM; the comparison gives every model the identical data snapshot (a demonstration, not a benchmark).
- **Auth and audit:** signed tokens, roles (viewer, presenter, admin) enforced server-side on every endpoint, audit log, rate limits and login back-off.

Architecture: a strict modular monolith (one FastAPI app, 11 modules, one PostgreSQL). See [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE.md](DATABASE.md), [API.md](API.md),
[DEPLOYMENT.md](DEPLOYMENT.md), and the presenter's run-sheet [DEMO_GUIDE.md](DEMO_GUIDE.md). Progress and open items: [TODO.md](TODO.md).

## Status: read this before a live session

- Verified (2026-11-22, on the working tree that includes the security hardening): the Docker stack starts, migrations apply, and the automated tests pass: **522 backend tests** (in the container) and **148 frontend unit tests**.
- **Not verified: any run against a real LLM.** All agent, demo and comparison behavior has so far been tested only with scripted fake models. Do a full rehearsal with your real provider before the seminar.
- **Security (implemented, local-demo grade):** every `/api` endpoint except `GET /api/health`, `GET /api/health/db` and `POST /api/auth/login` needs a signed token and a role permission, enforced by the backend (the UI login guard is only a convenience). Security events are written to an audit log, expensive endpoints have in-process rate limits, repeated failed sign-ins are backed off, requests over 12 MB are rejected, and CORS is limited to configured origins. Limits: rate-limit and lockout state lives in memory of a single backend process (resets on restart), `X-Forwarded-For` is not trusted, someone who knows a username can lock that user out for up to five minutes, there is no token revocation, and TLS is not provided. Details: [ARCHITECTURE.md](ARCHITECTURE.md) and [API.md](API.md).
- Cloud providers (Anthropic, OpenAI, Gemini) receive the prompt, live metrics and retrieved policy text. Use Ollama if nothing may leave the machine.

## Prerequisites

- Docker with Compose v2. On macOS you can use Colima (`colima start`) or Docker Desktop.
- Several GB of free disk (the backend image includes PyTorch, size not measured here); the small embedding model downloads on first use, so the first RAG call needs internet unless the `hf_models` volume is already populated.
- Node 22 and npm only if you build or test the frontend outside Docker.
- At least one LLM: a provider API key, or Ollama with a model you pulled yourself.

## Quick start

```bash
cp .env.example .env        # then edit .env (next section)
colima start                # skip if Docker is already running
docker compose up -d --build
```

Open http://localhost:4200 (the app) and http://localhost:8000/api/docs (API docs). Postgres is on host port 5433. Migrations run automatically when the backend starts.

### Configure `.env`

You choose all secrets; none are provided.

1. Auth: set `JWT_SECRET` (at least 32 characters, for example `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`) and
   `DEMO_ADMIN_PASSWORD`, `DEMO_PRESENTER_PASSWORD`, `DEMO_VIEWER_PASSWORD`. Without `JWT_SECRET` login fails with `auth_not_configured`.
2. Create the demo users (`demo_admin`, `demo_presenter`, `demo_viewer`):
   ```bash
   docker compose up -d --force-recreate backend   # restart alone does not re-read .env
   docker compose exec backend python -m app.modules.identity.application.seed
   ```
3. At least one provider: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and/or run Ollama. For the cloud providers also set `ANTHROPIC_MODELS`,
   `OPENAI_MODELS`, `GEMINI_MODELS` (comma-separated model IDs you have confirmed with your provider). The app hardcodes no model IDs.
4. After any `.env` change run `docker compose up -d --force-recreate backend` (a plain `restart` keeps the old environment).

### First run

1. Sign in as `demo_presenter` with the password you set.
2. Knowledge Base: click **Load samples** to index the six fictional PDFs.
3. Simulator or Demo Mode: load a scenario.

## Optional: Ollama (local models)

```bash
docker compose --profile ollama up -d          # starts the ollama service; downloads NO models
docker compose exec ollama ollama pull <model> # you choose a model; pick one that supports tool calling for native agent mode
```

Set `OLLAMA_BASE_URL=http://ollama:11434` in `.env` when using this profile (the default points to Ollama on the host, `http://host.docker.internal:11434`),
then `docker compose up -d --force-recreate backend`. Models without tool calling still work through the labelled fallback mode. Ollama model discovery, and these Ollama steps, have not been run end to end.

## Reset

- Data only: use **Reset Database** in the Simulator, or `POST /api/scenarios/reset` (reloads the Normal baseline; the data version still increases). In Demo Mode, **Reset and Replay** clears saved runs and reloads Normal.
- Everything (database and model cache volumes): `docker compose down -v`, then `docker compose up -d --build`, then seed users and load samples again.

## Running the tests

```bash
docker compose exec backend pytest -q          # full backend suite, a few minutes (uses throwaway databases)
cd frontend && npm ci && NG_BUILD_SASS_EMBEDDED=false npx ng test --watch=false
```

Architecture rules (module boundaries, cycles, controller purity) run as part of the backend suite (`backend/tests/architecture`).

## Frontend on macOS 13

Angular's bundled Sass binary needs macOS 14. On macOS 13 run local builds and tests with `NG_BUILD_SASS_EMBEDDED=false`
(for example `NG_BUILD_SASS_EMBEDDED=false npm run build`). Docker builds on Linux are unaffected. For hot-reload development use `npm start`
in `frontend/` (it proxies `/api` to http://localhost:8000).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `Cannot connect to the Docker daemon` | Start the runtime: `colima start` (or open Docker Desktop). |
| New backend routes return 404 or old behaviour after editing code | The file watcher may not see changes through the mounted volume: `docker compose restart backend`. |
| Login returns `auth_not_configured` | `JWT_SECRET` is missing or shorter than 32 characters; set it and recreate the backend (`docker compose up -d --force-recreate backend`). |
| Login returns 401 | Users not seeded, wrong password, or you changed a password after seeding (the seed never modifies existing users). |
| Login or an action returns 429 | Sign-in back-off (5 wrong passwords lock that username for 15 s, doubling up to 5 min) or a per-minute rate limit; wait for `Retry-After`. State is in memory, so restarting the backend clears it. |
| An action returns 403 | Your role lacks the permission (viewers are read-only); sign in as `demo_presenter` or `demo_admin`. |
| Provider call returns 409 `provider_not_configured` | The message names the environment variable to set; set it and recreate the backend (`docker compose up -d --force-recreate backend`). |
| Model list is empty for a cloud provider | Set `<PROVIDER>_MODELS` with IDs you have verified. |
| First RAG search or sample load is slow or fails offline | The embedding model downloads on first use; it is cached in the `hf_models` volume afterwards. |
| Port already in use | The stack uses 4200, 8000, 5433 (and 11434 for Ollama); stop the other process or change the mapping in `docker-compose.yml`. |
| Load samples reports no files | The backend reads `/sample_docs` (mounted from `./sample_docs` by compose); it is not baked into the image. |
| Frontend still shows old UI | Rebuild it: `docker compose up -d --build frontend`. |

## Repository layout

```
backend/    FastAPI modular monolith (app/modules/*, app/platform), Alembic migrations, tests
frontend/   Angular application (nginx image for Docker)
sample_docs/  six fictional demonstration PDFs and the script that generates them
docker-compose.yml, .env.example, *.md documentation
```
