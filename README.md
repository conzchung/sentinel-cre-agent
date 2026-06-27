# Sentinel — London Office Market Agent

An AI agent that monitors the London office commercial real estate (CRE) market
for a business team. Sentinel tracks prime/Grade A rents, vacancy &
availability, leasing take-up, the supply pipeline, macro & demand drivers, and
emerging news — answering questions and producing briefings with data charts and
citations through a conversational interface.

> Seed datasets are **illustrative** (anchored to public ranges), not a
> proprietary feed, and are always labelled as such. Nothing here is investment
> advice.

## Features

- **Market Q&A** — Ask about rents, vacancy, take-up, pipeline, or macro drivers and get a grounded answer with citations.
- **Interactive Charts** — The agent renders Plotly line/bar/grouped-bar charts server-side and streams them into the chat (`render_chart`).
- **Data Analysis** — The agent writes and runs pandas in a sandboxed subprocess to produce deterministic tables (`run_analysis`).
- **Semantic Knowledge Search** — RAG over an illustrative analyst-commentary corpus for qualitative drivers (flight-to-quality, ESG/EPC, hybrid working).
- **Live Web Search** — Tavily-backed retrieval for emerging market news.
- **PDF Briefings** — Turn a discussion into a formatted PDF report with charts (`generate_report`, WeasyPrint + matplotlib).
- **Conversation History** — Resume past chats; charts rehydrate interactively.

## Skills (the core idea)

Capabilities live as **skills** — folders under `skills/<id>/` with a `SKILL.md`
(YAML frontmatter + markdown body) and optional `data/*.csv`. Progressive
disclosure: a catalog is injected into the system prompt, and the agent loads a
skill's full instructions and data on demand. Adding a skill is dropping a
folder — no code changes. Discovery lives in `agent/skills_registry.py`.

Current skills: `rent_vacancy_trends`, `supply_pipeline`, `macro_demand`,
`market_news`.

## Workflow-Integrated Agent

The agent follows a structured LangGraph flow rather than acting as a freeform
chatbot:

```
fetch_context → assistant ⇄ tools → suggest_questions → END
```

1. **Context Gathering** — Loads conversation history before responding, ensuring continuity across sessions.
2. **Opt-In Planning** — When a request warrants it, the agent drafts a structured todo plan (`create_plan` tool) to make its reasoning transparent.
3. **Tool-Augmented Action** — Executes via specialized tools (`query_dataset`, `render_chart`, `web_search`, `knowledge_search`, `run_analysis`, `generate_report`), each with built-in error handling.
4. **Adaptive Follow-Up** — Suggests contextual next questions so the user is guided without needing to know what to ask.

The agent streams a tagged protocol (`<PLAN>`, `<ACTION>`, `<RESPONSE>`,
`<SUGGESTION>`, `<CHART>`) that the frontend parses to render plan, actions,
markdown, charts, and suggestion pills.

## Retrieval Modes

Sentinel grounds answers in three complementary ways:

- **`query_dataset`** — Structured figures from illustrative CSV seed data.
- **`knowledge_search`** — Semantic retrieval over an analyst-commentary corpus (Qdrant + Jina embeddings) for qualitative drivers and submarket colour.
- **`web_search`** — Live news and emerging developments via Tavily.

## Architecture

```
┌──────────────────┐       HTTP/REST        ┌──────────────────────┐
│    Next.js        │ ◄──────────────────► │      FastAPI          │
│    Frontend (BFF) │                       │      Backend          │
│                   │                       │                       │
│  - Login          │                       │  - LangGraph Agent    │
│  - Chatbot        │                       │  - Tool Execution     │
│  - Conversations  │                       │  - Skills Registry    │
│  - Streaming UI   │                       │  - RAG / Charts       │
│  - Chat History   │                       │  - Report Generation  │
└──────────────────┘                       └──────────┬───────────┘
                                                       │
                                  ┌────────────┬───────┼───────┬────────────┐
                                  │            │       │       │            │
                             Azure Cosmos  Azure Blob  │    Qdrant      Azure OpenAI
                               (DB)        (Storage)   │   (Vectors)      (LLM)
                                                     Tavily
                                                    (Search)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (App Router) — BFF proxy, see `frontend/` |
| Backend API | FastAPI + uvicorn |
| Agent Framework | LangChain 1.0 + LangGraph 1.0 |
| LLM | Azure OpenAI (GPT-5.4) |
| Vector DB | Qdrant + Jina embeddings |
| Database | Azure Cosmos DB |
| Storage | Azure Blob Storage |
| Search | Tavily API |
| Charts / Reports | Plotly (interactive) · matplotlib + WeasyPrint (PDF) |

## Running with Docker

The full stack (FastAPI backend + Next.js frontend) runs via Docker Compose:

```bash
# Put secrets in a .env file in the repo root (API_KEY, COOKIE_SECRET, and the
# agent's Azure/Tavily/Jina/Qdrant keys — see env.template.json).
docker compose up --build
```

- Frontend: http://localhost:3000 (log in with the demo account configured via `AUTH_USERNAME` / `AUTH_PASSWORD`; defaults to `demo` / `demo`)
- Backend API: http://localhost:8000

The frontend reaches the backend over the compose network (`FASTAPI_URL=http://fastapi:8000`)
and injects `X-API-Key` server-side, so the key never reaches the browser. To build
the images individually:

```bash
docker build -f Dockerfile.fastapi -t sentinel-fastapi .
docker build -f frontend/Dockerfile -t sentinel-frontend ./frontend
```

## Running locally (without Docker)

Requires Python 3.12. Create a virtual environment and install
`requirements-fastapi.txt`, then:

```bash
# API (from project root)
uvicorn main:app --port 8000 --reload
# Web UI (Next.js)
cd frontend && npm install && cp .env.local.example .env.local && npm run dev   # http://localhost:3000
# CLI
python run_agent.py
# Tests
python -m pytest -v
```

## Notes

Seed datasets are illustrative (anchored to public ranges), not a proprietary
feed, and nothing here is investment advice. Built as a technical demonstration.
