# Local development with PyCharm and Docker infrastructure

Docker runs PostgreSQL, Redis, MinIO, Qdrant, database migrations and the
Celery worker. PyCharm runs the FastAPI API and the Vite frontend.

## Start infrastructure

Start Docker Desktop, then run from the repository root:

```powershell
.\start-infrastructure.ps1
```

The first run builds the backend image and creates persistent named volumes.
Subsequent runs reuse the containers and data.

Host endpoints:

- PostgreSQL: `127.0.0.1:5433`
- Redis: `127.0.0.1:6380`
- MinIO API: `http://127.0.0.1:9002`
- MinIO console: `http://127.0.0.1:9003`
- Qdrant API/dashboard: `http://127.0.0.1:6333`

The host-side FastAPI process automatically loads `backend/.env.local` before
`backend/.env`. Infrastructure connection values come from `.env.local`; cloud
LLM and embedding values continue to come from `.env`.

## Start application in PyCharm

Run the existing `FinAgent Full Stack` compound configuration:

- Backend: `uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload`
- Frontend: `npm run dev -- --host 127.0.0.1`

Do not start the `api` or `web` services from the full `docker-compose.yml`
while using PyCharm, because that would create a second application stack.

## Verify

```powershell
Invoke-WebRequest http://127.0.0.1:6333/collections
Invoke-WebRequest http://127.0.0.1:8010/health/ready
Invoke-WebRequest http://127.0.0.1:5173/health/live
```

## Stop infrastructure

```powershell
.\stop-infrastructure.ps1
```

This stops containers without deleting persistent volumes. Do not add `-v`
unless the local PostgreSQL, Redis, MinIO and Qdrant data may be discarded.
