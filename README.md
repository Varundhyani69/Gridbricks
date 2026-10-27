# Gridbricks — Wind Forecast Analytics

Scaffold for a UK procurement dashboard using national wind generation data
from Elexon. The current stage provides a React/Vite frontend and a Python
health-check API; forecast analytics are not implemented yet.

## Repository layout

- `backend/` — FastAPI service, Python project configuration, and tests.
- `frontend/` — React + TypeScript + Vite application.
- `docs/` — requirements, architecture, API findings, assumptions, and test plan.
- `scripts/probe_elexon.py` — bounded Elexon history/response probe.
- `tests/fixtures/` — small observed API-shape samples, not a results dataset.
- `docker-compose.yml` — local two-service container configuration.

## Local development

Prerequisites: Python 3.11+, Node.js 20.19+ (or 22.12+), and npm.

In one terminal:

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

The frontend expects the API at `http://localhost:8000`. Configure
`CORS_ORIGINS` for the frontend's exact browser origin when using a non-default
host or port. See `.env.example` for the local configuration names.

## Checks

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

```bash
cd frontend
npm run lint
npm run build
```

The API health endpoint is `GET /api/health`; FastAPI's OpenAPI page is
available at `/docs` while the backend is running.

## Docker

Dockerfiles and Compose configuration are present. Docker is not installed in
the current development environment, so container builds and Compose startup
have not yet been verified.

## Data and deployment status

The observed historical-data verification and its limitations are documented
in [`docs/elexon-api-findings.md`](docs/elexon-api-findings.md). No public
application deployment or demo video has been completed yet.

## AI disclosure

AI assistance (Copilot SDK in VS Code) was used during development.
