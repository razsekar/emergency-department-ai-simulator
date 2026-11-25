# Deployment

**Status: nothing in this document has been deployed or tested on Vercel, Railway, Neon or Supabase.**
The local Docker Compose path is the only one that has been run. Provider facts below were
checked against public documentation search results on **2026-11-22**; items marked
**UNVERIFIED** could not be confirmed and must be checked before relying on them.

## 1. Local (primary, verified)

```
cp .env.example .env        # then edit: see "Required secrets" below
colima start                # if using Colima (Docker Desktop also works)
docker compose up -d --build
docker compose exec backend pytest -q
```
- Frontend http://localhost:4200, API docs http://localhost:8000/api/docs, Postgres on host port 5433.
- Services: `db` (pgvector/pgvector:pg16), `backend` (FastAPI), `frontend` (nginx serving Angular, proxying `/api/` to `backend:8000`).
- Migrations run automatically on backend start (`alembic upgrade heads`).
- Optional Ollama: `docker compose --profile ollama up -d`. No models are pulled automatically; run
  `ollama pull <model>` yourself (inside the container or on the host).
- Reset everything including data: `docker compose down -v` (deletes the database and model-cache volumes).

### Required secrets (you set them in `.env`; never commit it)
- `JWT_SECRET` (at least 32 characters; `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `DEMO_ADMIN_PASSWORD`, `DEMO_PRESENTER_PASSWORD`, `DEMO_VIEWER_PASSWORD`, then seed users:
  `docker compose exec backend python -m app.modules.identity.application.seed`
- At least one LLM provider: `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`, or a running Ollama.
  Also set the matching `*_MODELS` list to model IDs you have verified.

### Building the frontend on this Mac
The host is macOS 13; Angular's bundled Sass binary needs macOS 14. Locally use
`NG_BUILD_SASS_EMBEDDED=false npm run build` (or `ng serve` / `ng test`). Docker builds on Linux are unaffected.

## 2. Managed PostgreSQL with pgvector (checked 2026-11-22)

The app needs the `vector` extension (migration 0001 runs `CREATE EXTENSION IF NOT EXISTS vector`, so the
database role must be allowed to create it) and uses `vector(384)` columns with an HNSW index.

| Option | pgvector support | How to enable | Source |
|---|---|---|---|
| Neon | Available on all plans per Neon docs | `CREATE EXTENSION IF NOT EXISTS vector;` | https://neon.com/docs/extensions/pgvector , https://neon.com/faqs/enable-pgvector-extension |
| Supabase | Supported; extension name is `vector` | Dashboard: Database > Extensions > search "vector"; or `create extension vector with schema extensions;` | https://supabase.com/docs/guides/database/extensions/pgvector |
| Railway, community pgvector templates | Templates deploy the official `pgvector/pgvector` image on a volume (several variants, PG17/PG18, by different authors; not Railway-maintained as far as found) | Deploy template, copy `DATABASE_URL`, run `CREATE EXTENSION IF NOT EXISTS vector;` | e.g. https://railway.com/deploy/pgvector-1 , https://railway.com/deploy/postgres-with-pgvector-engine |
| Railway, the default "Postgres" service | **UNVERIFIED.** No official statement found either way. | Test with `SELECT * FROM pg_available_extensions WHERE name = 'vector';` before choosing it | n/a |

Notes:
- Enable the extension in **each database** you use; after upgrading a pgvector template run `ALTER EXTENSION vector UPDATE;`.
- Community template caveats (from their pages): you need a volume or each redeploy starts an empty cluster,
  and some have no WAL archiving or scheduled dumps, so back up separately. Their claims on performance and price are unverified marketing.
- This project was tested on `pgvector/pgvector:pg16`. Other Postgres major versions are untested.
- **Verification step after provisioning** (run against the target DB; must return one row):
  ```
  psql "$DATABASE_URL" -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
  ```
  Then after the backend starts: `GET /api/health/db` must return `{"status":"ok","pgvector":true}`.
- The app expects the SQLAlchemy driver form `postgresql+psycopg://user:pass@host:port/db`. Managed providers usually hand out
  `postgresql://...`; edit the scheme yourself when setting `DATABASE_URL`.

## 3. Backend on Railway (not deployed, plan only)

Railway builds from `backend/Dockerfile` (set the service root directory to `backend/`).

Environment variables (server-side only; never in the frontend):
- `DATABASE_URL` (driver form above), `JWT_SECRET`, `JWT_TTL_MINUTES`, `DEMO_*_PASSWORD`
- `CORS_ORIGINS` as a **JSON array string**, e.g. `["https://your-app.vercel.app"]` (the setting is parsed as a list)
- Provider keys and `*_MODELS` lists as needed; `LOG_LEVEL`
- `HF_HOME=/models` if you attach a volume at `/models` (see below)

Start command: the Dockerfile `CMD` already runs `alembic upgrade heads && uvicorn ...`.

**Port and health check** (per Railway docs, https://docs.railway.com/deployments/healthchecks): Railway injects a `PORT`
variable, health checks use it, and the app must listen on it on `0.0.0.0`. The Dockerfile hardcodes `--port 8000` and `EXPOSE` is
informational only. Either set the `PORT` variable to `8000` in the service, or change the CMD to use `${PORT:-8000}`.
Set the health check path to `/api/health`.

**Image size and memory (concern, UNVERIFIED limits):** the image contains CPU-only torch plus sentence-transformers, so it is
large (we have not measured it on Railway). Sources conflict on Railway's build image cap (some reports of a 4 GB limit on
Hobby, a staff reply saying 100 GB), and I found no reliable RAM figures. Check https://docs.railway.com/reference/pricing/plans
and your own dashboard before choosing a plan. Run `docker images` locally to see the real image size first.

**Embedding model:** `all-MiniLM-L6-v2` is downloaded from Hugging Face on first use and cached in `HF_HOME`. In Railway the
container filesystem is ephemeral, so without a volume every redeploy re-downloads it and the first RAG call is slow. Options:
attach a volume at `/models` and set `HF_HOME=/models`, or bake the model into the image (not currently done).

**Single process only:** the demo-step lock is in-process, and migrations run on every start. Run **one replica and one uvicorn
worker**; multiple replicas could race on migrations and bypass the demo lock.

**After first deploy:** seed demo users and load sample documents (`/api/knowledge/documents/load-samples` reads the `sample_docs`
folder, which is mounted in compose but is **not** copied into the backend image by the Dockerfile; upload the six PDFs through the
UI instead, or add them to the image).

## 4. Frontend on Vercel (not deployed, plan only)

How the frontend resolves its API: every call uses a **relative `/api/...` path** (no environment file, no configurable base URL).
Locally nginx (`frontend/nginx.conf`) and `ng serve` (`proxy.conf.json`) proxy `/api` to the backend. On Vercel nothing does that,
so the smallest change that needs no code edit is a `frontend/vercel.json` with rewrites (Vercel docs:
https://vercel.com/docs/routing/rewrites):

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://YOUR-RAILWAY-DOMAIN/api/:path*" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```
Settings: root directory `frontend/`, build `npm run build`, output `dist/ed-sim/browser`. Because requests are proxied same-origin,
CORS is not exercised, but still set `CORS_ORIGINS` correctly on the backend.

Open risks (**UNVERIFIED**, test before a live session):
- **Streaming (SSE) through a Vercel rewrite.** I found no official statement on SSE behavior or buffering for external rewrites.
  Vercel's CDN waits up to 120 s for the origin to start responding (changelog), but whether a long stream is cut is unclear, and a
  community thread reports SSE cut-offs on a free plan. The agent run itself is a normal POST (not SSE), but chat/playground streaming
  may be affected. Fallback: call the Railway domain directly (needs a small frontend change to add an API base URL, and CORS then matters).
- **Caching:** Vercel may cache external rewrite responses according to upstream cache headers (default changed for projects created on or after 2026-04-06).
  The API should send `Cache-Control: no-store` on live-data endpoints; this is not currently verified or set.

## 5. Ollama
With the compose `ollama` profile set `OLLAMA_BASE_URL=http://ollama:11434`. Also see `OLLAMA_NUM_CTX`, `LLM_TIMEOUT_SECONDS` and `AGENT_MAX_OUTPUT_TOKENS` in `.env.example`; CPU inference is slow (minutes per answer).

Ollama is local or separately hosted. **A Railway/cloud backend cannot reach `localhost:11434` on your laptop.** For a cloud
backend either host Ollama on a reachable server and set `OLLAMA_BASE_URL`, or use a cloud provider. Locally in Docker Compose the
default `http://host.docker.internal:11434` reaches an Ollama running on the host (works on Docker Desktop/Colima on macOS; Linux needs an `extra_hosts` mapping).

## 6. Data privacy
Data is synthetic. Still, when a cloud provider (Anthropic, OpenAI, Gemini) is selected, **prompts, operational metrics, and retrieved
document excerpts are sent to that provider.** The UI shows a disclosure for cloud models. Use Ollama if nothing may leave the machine.
Do not upload real patient documents.

## 7. Cost and limits
No prices are stated here because they change; check each provider's pricing page. Things that cost money or hit limits: LLM tokens per
run (the Demo Mode makes 3 agent runs, Comparison makes one call per model), Railway compute/RAM/volume and build limits, Vercel
function/CDN limits, and managed Postgres plan quotas. The estimated cost shown in the app uses LiteLLM's bundled price map and may be out of date.

## 8. Readiness review of current files (reported, not changed)
1. `docker-compose.yml` backend uses `--reload` and bind-mounts `./backend:/app`: development only. Reload also did not always notice file changes through the Colima mount; use `docker compose restart backend`.
2. Compose falls back to the password `edsim` (`${POSTGRES_PASSWORD:-edsim}`) if `.env` is missing; `.env.example` has `change-me-locally` and repeats it inside `DATABASE_URL` (must be kept in sync by hand).
3. Postgres (5433) and backend (8000) ports are published to the host; remove for any shared host.
4. `backend/Dockerfile` installs `requirements-dev.txt` (pytest, httpx) into the runtime image, runs as root, and hardcodes port 8000 (see Railway port note).
5. `backend/Dockerfile` does not copy `sample_docs/`; compose mounts it read-only, a deployed image would not have it.
6. `frontend/nginx.conf` hardcodes `backend:8000` (fine for Compose only). The frontend service has no health check.
7. `ollama/ollama` image is unpinned.
8. No security headers/rate limiting at the proxy; login has no rate limiting or lockout (identity module), and RBAC is not yet enforced on the simulation, analytics, queue and resource endpoints.
