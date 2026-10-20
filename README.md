# RepoRescue AI

RepoRescue AI is a GitHub Repository Doctor: paste a public GitHub repository URL and get a practical health report for the maintenance basics that make a codebase easier to run and ship.

## What it checks

- README documentation
- Dependency lockfiles
- Tests or test directories
- Dockerfile/container build instructions
- Pinned runtime versions (`.python-version`, `.nvmrc`, `runtime.txt`, and similar)
- `.env.example` or `.env.template`

Each finding includes a severity, explanation, and suggested fix. Demo mode returns a deterministic sample report and does not need a GitHub token.

## Stack

- Frontend: React 19, TypeScript 7, Vite 8
- Backend: Python 3.12.8, FastAPI, Pydantic
- Tests: pytest

## Run from a clean Linux environment

### Prerequisites

- Python 3.12.8 (the version is pinned in `.python-version`)
- Node.js compatible with the installed Vite version
- npm

### Backend

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Health check: `GET /health`.

### Frontend

In a second terminal, from the repository root:

```bash
npm ci
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`. During local development, Vite proxies `/api` and `/health` to the FastAPI server on port 8000. To use another API origin, create `.env.local` with:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

### Demo mode

Click **Try demo** in the dashboard. This uses the backend's built-in sample response and works without network access or a GitHub token.

### Production frontend build

```bash
npm run build
npm run preview
```

The generated static site is in `dist/`. Serve it from a web server configured to reach the FastAPI API, or set `VITE_API_BASE_URL` before building.

## Tests

Run the backend tests:

```bash
python -m pytest -q
```

Run the frontend typecheck and production build:

```bash
npm run build
```

## Optional GitHub token

Public repositories can be inspected without authentication. Set `GITHUB_TOKEN` in your environment or `.env` to increase GitHub API rate limits. Never commit `.env` or a real token.

## Docker

The included `Dockerfile` runs the FastAPI backend:

```bash
docker build -t reporescue-api .
docker run --rm -p 8000:8000 --env-file .env reporescue-api
```

The frontend remains a static Vite build and can be served by a separate static host or web server.
