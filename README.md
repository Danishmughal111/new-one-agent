# AI Company OS

A multi-agent AI company platform. Phase 1 delivers the core operating system: a scalable, production-oriented backend for managing agents, departments, tasks, permissions, workflows, and audit logging.

## Business Divisions (future)

1. **TrendEra** — affiliate product research, market/trend research, content generation, SEO, publishing, marketing automation.
2. **AI Automation Division** — n8n workflows, local AI agent workflows, automation system design, and AI-powered business automations.

## Current Phase (Phase 1)

Phase 1 focuses on the **core operating system** — not on building dozens of agents. The foundational layer includes:

- A centralized task and workflow system
- An agent registry with deterministic (non-LLM) placeholder agents
- A task state machine with validated transitions
- A least-privilege permission system
- Structured + audit logging
- A PostgreSQL-backed persistence layer (SQLite for tests)

### Agent Hierarchy (Phase 1)

```
Human Owner
     ↓
CEO Agent        → strategic decomposition & delegation
     ↓
COO Agent        → task creation & assignment
     ↓
Task System      → centralized workflow
     ↓
Assigned Agent   → deterministic execution
     ↓
QA Review        → approve / reject
     ↓
Completed / Revision Required / Escalated
```

- **Chief of Staff** monitors the entire system.
- **Security Agent** validates permissions and sensitive operations (it never receives or exposes secrets).

## Tech Stack

- Python 3.12+ (Docker image uses 3.12; local dev may use 3.14)
- FastAPI
- PostgreSQL (production) / SQLite (tests only)
- SQLAlchemy 2.0 (async)
- Pydantic v2
- Redis (future infrastructure — not required by Phase 1 execution)
- pytest / pytest-asyncio / httpx
- Alembic (migrations)
- Docker / Docker Compose

## Project Structure

```
.
├── app/
│   ├── main.py
│   ├── core/           # config, database, security, logging, permissions, state machine
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── repositories/   # data access layer
│   ├── services/       # business logic layer
│   ├── agents/         # BaseAgent + registry + concrete agents
│   ├── api/            # FastAPI routers
│   └── orchestration/  # workflow orchestration abstraction
├── tests/
├── alembic/
├── docker/
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Local Setup

### 1. Clone / initialize the repository

```bash
git clone <repo-url>   # if applicable
cd ai-company-os
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY and your PostgreSQL DATABASE_URL
```

> `.env` is git-ignored and must never be committed.

### 5. Database migrations (Alembic)

The application does **not** create its schema automatically. Apply migrations
explicitly:

```bash
alembic upgrade head
```

### 6. Run the application (with Docker)

```bash
docker compose up --build
```

This starts the FastAPI app, PostgreSQL (with migrations applied on startup),
and Redis (reserved for future use).

### 7. Run without Docker (local Postgres required)

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

### 8. Run tests

```bash
pytest
```

Tests use an isolated SQLite database and require **no** external services or API keys.

## Supported Python Version

- **Docker/production:** Python 3.12 (broad dependency wheel support)
- **Local development:** Python 3.14 is usable if the full test suite passes; dependency pins are lower bounds so pip resolves compatible wheels.

## Configuration

All configuration is read from environment variables (see `.env.example`). Secrets must never be hardcoded.

## Phase 1 Status

Phase 1 is under active development. See the task/progress documentation for the current state.