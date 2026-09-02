# AutoPilot Airlines

A full-stack, AI-agent-driven airline booking application — flight search, booking, check-in, baggage, payments, refunds, and loyalty — built as a **deliberately vulnerable target for API and AI-agent security testing**.

The app is a realistic product on the surface: a Next.js storefront, a FastAPI backend with a LangGraph multi-agent assistant, a separate card/payments microservice, an MCP server, and mock third-party SaaS integrations. Underneath, the security posture is controlled by a single `DIFFICULTY` knob, so the same codebase can be run as a wide-open baseline or as a hardened build.

> [!WARNING]
> **Do not deploy this on the public internet**
> At the default difficulty (`easy`) this application intentionally contains prompt injection, SSRF, IDOR, SQL injection, path traversal, secret leakage, over-permissive agent tooling, and weak auth. It exists to be attacked in a sandbox.

---

## Architecture

| Service        | Tech                                     | Port | Role                                                          |
|----------------|------------------------------------------|------|---------------------------------------------------------------|
| `frontend`     | Next.js 16 / React 19 / Tailwind 4       | 3000 | Customer + admin web UI, agent chat interface                  |
| `backend`      | FastAPI, SQLAlchemy (async), LangGraph   | 8000 | REST API, multi-agent assistant, MCP server, mock SaaS         |
| `card-service` | FastAPI, SQLAlchemy (async), Jinja2      | 8002 | Virtual cards, balances, transactions, settlement, audit UI    |
| `postgres`     | `pgvector/pgvector:pg16`                 | 5432 | `autopilot` + `cardservice` databases; pgvector for agent memory |
| `redis`        | `redis:7-alpine`                         | 6379 | Session / cache layer                                          |

```
frontend (3000) ──▶ backend (8000) ──▶ postgres (5432)
                        │         └──▶ redis (6379)
                        ├──▶ card-service (8002) ──▶ postgres
                        ├──▶ /mcp  (MCP server: tools, resources, prompts)
                        └──▶ mock SaaS: AutoCRM · AutoMail · AutoPay · AutoDocs
```

---

## Quick start

Requires Docker + Docker Compose v2 and an LLM provider (an OpenAI-compatible API key **or** AWS Bedrock credentials).

```bash
cp .env.example .env.dev     # then set your LLM provider in .env.dev
docker compose up --build
```

**Using AWS Bedrock?** Run `./refresh-aws-creds.sh <aws-profile>` to populate `.env.dev` *before* `docker compose up` — see [DEPLOYMENT.md → Option B](DEPLOYMENT.md#option-b--aws-bedrock).

- Frontend — http://localhost:3000
- Backend API + Swagger UI — http://localhost:8000 / http://localhost:8000/docs
- Card service — http://localhost:8002

Postgres creates and seeds both databases on first boot (`infrastructure/postgres/`, `card-service/infrastructure/`); the backend auto-creates and syncs tables at startup. Seed data includes 24 flights, two users, bookings, payment methods, and loyalty accounts.

**Demo accounts**

| Role  | Email                  | Password      |
|-------|------------------------|---------------|
| User  | `john@example.com`     | `password123` |
| Admin | `admin@autopilot.com`  | `password123` |

For LLM provider options, running services without Docker, published container images, and troubleshooting, see **[DEPLOYMENT.md](DEPLOYMENT.md)**.

---

## Difficulty levels

`DIFFICULTY` in `.env.dev` selects a preset in `backend/src/config.py` that drives both the agent system prompts and code-level enforcement. At `intermediate` and `advanced` the preset **locks** its security flags — they cannot be weakened by individual environment variables.

| Level          | Posture                                                                                                                  |
|----------------|--------------------------------------------------------------------------------------------------------------------------|
| `easy` (default) | Everything intentionally broken. Full error traces, secrets in prompts, unauthenticated MCP, unrestricted debug SQL, 1-year JWTs. |
| `intermediate` | Prompt hardening, MCP auth required, SELECT-only SQL for debug tooling, admin role checks, basic input sanitization, rate limiting, 24h JWTs. |
| `advanced`     | All of the above plus debug tools disabled, strict sanitization, PII redaction, audience-validated 8h JWTs, MCP and agent tool scope checks. |

Use this to measure a scanner or red-team tool: it should light up at `easy`, find less at `intermediate`, and find little at `advanced`.

---

## Attack surface

**REST API** (`/api/v1/...`) — `auth` (incl. an OAuth authorize/token flow), `flights`, `bookings`, `payments`, `payment-methods`, `refunds`, `loyalty`, `checkin`, `baggage`, `users`, `memory`, `reports`, `chat`, and a broad `admin` surface (stats, audit logs, user roles, tier/points grants, flight reschedule/cancel, offers, coupons).

**AI agent** (`POST /api/v1/chat`) — a LangGraph supervisor routes to four sub-agents (booking, payment, customer service, admin) over ~35 tools spanning flight search, booking/cancel/reschedule quotes and commits, payments and refunds, loyalty mutation, coupon generation, email, user lookup, pgvector-backed long-term memory, and debug SQL. Injection reaches the agent through user messages, stored memories, policy documents, and tool output.

**MCP server** (mounted at `/mcp`) — tools, resources, and prompt templates, plus an admin router that can register tools and mutate tool schemas at runtime. The registry itself is a target: tool poisoning and schema manipulation are in scope.

**Mock SaaS** (`backend/src/services/saas/`) — AutoCRM (contacts, tickets), AutoMail (outbound email), AutoPay (card processing), AutoDocs (policy documents). Deliberately seeded with planted secrets and indirect-injection payloads.

---

## Repository layout

```
backend/                FastAPI service
  src/routers/          REST endpoints
  src/agents/           LangGraph supervisor, sub-agents, prompts, tools
  src/mcp/server.py     MCP server + runtime tool registry
  src/security/         SQL / content / URL guards (difficulty-gated)
  src/services/saas/    Mock third-party integrations
  src/models/           SQLAlchemy models
  tests/                pytest suite
card-service/           Standalone card + settlement service
frontend/               Next.js app (customer + admin UI, agent chat)
infrastructure/postgres/  DB bootstrap and seed SQL
.github/workflows/      CI: pytest for both Python services, multi-arch image publish
```

---

## Development

```bash
# Backend
cd backend && uv sync --extra test && uv run pytest
uv run uvicorn src.main:app --reload --port 8000

# Card service
cd card-service && uv sync --extra test && uv run pytest
uv run uvicorn src.main:app --reload --port 8002

# Frontend
cd frontend && pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

Python services use [`uv`](https://github.com/astral-sh/uv) (Python ≥ 3.12); the frontend uses [`pnpm`](https://pnpm.io/) on Node 26. Running without Docker requires local Postgres (with `pgvector`) and Redis — see [DEPLOYMENT.md](DEPLOYMENT.md#local-development-without-docker).

`backend/tests/` includes `test_difficulty_security.py` and `test_security_findings.py`, which assert that the `intermediate`/`advanced` presets actually hold — those are the guardrail tests to keep green when changing security-relevant code.
