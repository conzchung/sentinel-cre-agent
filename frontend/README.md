# Sentinel Frontend (Next.js)

Custom chat UI for the Sentinel London office market agent. Replaces the
Streamlit frontend. The FastAPI agent backend is reused unchanged.

## Architecture

Browser → Next.js route handlers (BFF) → FastAPI. Next.js owns login + a signed
httpOnly session cookie and proxies agent calls to FastAPI, injecting the
`X-API-Key` server-side. The browser parses the agent's tagged text stream
(`<PLAN>/<ACTION>/<RESPONSE>/<CHART>/<SUGGESTION>`) and renders plan, actions,
streamed markdown, interactive Plotly charts, and suggestion pills.

## Setup

```bash
cd frontend
cp .env.local.example .env.local   # then edit values
npm install
```

`.env.local`:
- `FASTAPI_URL` — the FastAPI base URL (default `http://localhost:8000`)
- `API_KEY` — the agent API key, must match the backend `API_KEY` (required, no default)
- `COOKIE_SECRET` — secret for signing the session cookie (required, no default)
- `AUTH_USERNAME` / `AUTH_PASSWORD` — the single demo account (default `demo` / `demo`)

## Running (two processes)

```bash
# Terminal 1 — FastAPI (from repo root)
uvicorn main:app --port 8000 --reload

# Terminal 2 — Next.js
cd frontend && npm run dev
```

Open http://localhost:3000. Log in with the demo account configured via
`AUTH_USERNAME` / `AUTH_PASSWORD` in `.env.local` (defaults to `demo` / `demo`).

## Tests

```bash
cd frontend && npm test    # Vitest — pure logic (parser, plan, chart, session, history)
```

## Docker

The frontend is containerized via `frontend/Dockerfile` (Next.js `output:
'standalone'`, non-root). The simplest path is the repo-root `docker-compose.yml`,
which runs it alongside FastAPI:

```bash
docker compose up --build   # from the repo root
```

In compose, `FASTAPI_URL` points at the backend service (`http://fastapi:8000`)
and `API_KEY` / `COOKIE_SECRET` are passed through from the host environment.

## Layout

- `app/` — routes: `/login`, `/` (chat), and `api/*` BFF route handlers.
- `lib/` — framework-free logic (stream parser, plan parser, chart decode,
  session crypto, history rebuild) with unit tests in `lib/__tests__/`.
- `components/` — React UI (sidebar, turn rendering, composer).
