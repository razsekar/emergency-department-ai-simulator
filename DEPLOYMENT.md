# Deployment

## Local (primary)
```
cp .env.example .env        # edit passwords/keys
colima start                # if using Colima (Docker Desktop also works)
docker compose up -d --build
docker compose exec backend pytest -q
```
- Frontend http://localhost:4200, API docs http://localhost:8000/api/docs, Postgres on host port 5433.
- Optional Ollama: `docker compose --profile ollama up -d` (no models are pulled automatically;
  run `ollama pull <model>` yourself).
- Reset everything including data: `docker compose down -v` (deletes the database volume).

## Optional cloud (not yet verified)
Frontend on Vercel, backend on Railway, managed Postgres with pgvector. **pgvector support must be
verified with the chosen provider before deploying.** Details to be completed in Phase 9.
