# Deployment Guide

AutoPilot Airlines is a multi-service application made up of four runtime services backed by PostgreSQL and Redis:

| Service        | Tech                          | Port | Image (CI)                                          |
|----------------|-------------------------------|------|-----------------------------------------------------|
| `frontend`     | Next.js 16 / React 19         | 3000 | `ghcr.io/allvapps/autopilotairlines-frontend`       |
| `backend`      | FastAPI + LangGraph AI agent  | 8000 | `ghcr.io/allvapps/autopilotairlines-backend`        |
| `card-service` | FastAPI                       | 8002 | `ghcr.io/allvapps/autopilotairlines-cardservice`    |
| `postgres`     | pgvector/pgvector:pg16        | 5432 | —                                                   |
| `redis`        | redis:7-alpine                | 6379 | —                                                   |

---

## Prerequisites

- Docker + Docker Compose v2 (`docker compose`)
- An LLM provider — either an **OpenAI-compatible API key** or **AWS Bedrock credentials**
- For local (non-Docker) development:
  - [`uv`](https://github.com/astral-sh/uv) for the Python services
  - Node.js 26 + [`pnpm`](https://pnpm.io/) for the frontend

---

## Quick start (Docker Compose)

This is the recommended way to run the full stack.

1. **Create the environment file.** Compose loads the backend's config from `.env.dev`:

   ```bash
   cp .env.example .env.dev
   ```

2. **Set your LLM provider** in `.env.dev` (see [LLM configuration](#llm-configuration) below).

   If you're using **AWS Bedrock**, populate the credential fields *before* starting Compose — the backend reads them from `.env.dev` at container start:

   ```bash
   ./refresh-aws-creds.sh <aws-profile>
   ```

3. **Build and start everything:**

   ```bash
   docker compose up --build
   ```

4. **Access the app:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Card service: http://localhost:8002

The Postgres container initializes both databases (`autopilot` and `cardservice`) and seeds demo data on first boot via the scripts in `infrastructure/postgres/` and `card-service/infrastructure/`. Tables are auto-created/synced by the backend on startup (`_sync_schema` in `main.py`).

**Demo accounts:**
- User: `john@example.com` / `password123`
- Admin: `admin@autopilot.com` / `password123`

---

## LLM configuration

The backend supports two providers. Configure one in `.env.dev`.

### Option A — OpenAI-compatible API

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1
```

`OPENAI_BASE_URL` can point at any OpenAI-compatible endpoint (Azure OpenAI, a local server, etc.).

### Option B — AWS Bedrock

```env
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...          # required for SSO / temporary credentials
BEDROCK_MODEL=global.anthropic.claude-sonnet-4-6
```

`AWS_SESSION_TOKEN` is required for SSO / temporary credentials. Rather than pasting the three credential values by hand, use the helper script — it reads them from a named AWS profile via `aws configure export-credentials` and rewrites the `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` lines in `.env.dev` in place:

```bash
./refresh-aws-creds.sh <aws-profile-name>
# or: AWS_PROFILE=<aws-profile-name> ./refresh-aws-creds.sh
```

Prerequisites: the AWS CLI v2, a configured profile, and an active SSO session. If the script reports `Failed to export credentials` or `No credentials found`, log in first:

```bash
aws sso login --profile <aws-profile-name>
```

**Run the script before `docker compose up`.** The backend reads `.env.dev` when its container starts, so credentials must already be in the file — Compose will not pick up later edits on its own.

SSO session tokens expire (~12h). When they do, the agent starts failing with provider auth errors (401/`ExpiredToken`); refresh and restart the backend:

```bash
./refresh-aws-creds.sh <aws-profile-name>
docker compose restart backend
```

`AWS_REGION` must be a region where your account has access to `BEDROCK_MODEL`, and the model must be enabled for the account. Setting `AWS_REGION` + `AWS_ACCESS_KEY_ID` is what selects Bedrock over the OpenAI-compatible path, so leave the `OPENAI_*` block empty when using Bedrock.

> **Never commit real credentials.** `.env*` files are git-ignored. Treat any keys checked into a working copy as compromised and rotate them.

---

## Environment variables

`.env.example` is the template. Key variables:

| Variable                  | Description                                          | Example                                                            |
|---------------------------|------------------------------------------------------|--------------------------------------------------------------------|
| `DATABASE_URL`            | Async Postgres DSN for the backend                   | `postgresql+asyncpg://autopilot:autopilot@postgres:5432/autopilot` |
| `REDIS_URL`               | Redis connection string                              | `redis://redis:6379`                                               |
| `JWT_SECRET`              | Secret for signing JWTs                              | (random, high-entropy string)                                      |
| `JWT_ALGORITHM`           | JWT signing algorithm                                | `HS256`                                                            |
| `JWT_EXPIRY_HOURS`        | Token lifetime in hours                              | `8760`                                                            |
| `CORS_ALLOW_ORIGINS`      | Allowed CORS origins (comma-separated, or `*`)       | `http://localhost:3000`                                            |
| `OPENAI_API_KEY` …        | LLM provider config — see above                      |                                                                    |
| `CARD_SERVICE_URL`        | Backend → card-service URL (set by Compose)          | `http://card-service:8002`                                         |
| `NEXT_PUBLIC_API_URL`     | Frontend → backend URL (build/runtime arg)           | `http://localhost:8000`                                            |

The full list of toggles (`OAUTH_*`, `MCP_*`, `INPUT_SANITIZATION`, `PII_REDACTION`, `RATE_LIMIT_ENABLED`, `AGENT_*`, `ERROR_DETAIL_LEVEL`, `DEBUG_TOOLS_ENABLED`, …) and their defaults live in `backend/src/config.py`. The repo ships two presets:

- `.env.example` — open/permissive defaults used for local runs.
- `.env.secure` — hardened settings (strict sanitization, scoped MCP/OAuth, short token expiry, rate limiting).

---

## Local development (without Docker)

You'll need Postgres (with the `pgvector` extension) and Redis running locally, plus the two databases `autopilot` and `cardservice` created.

### Backend

```bash
cd backend
uv sync
# point DATABASE_URL/REDIS_URL at your local instances (e.g. via .env)
uv run uvicorn src.main:app --reload --port 8000
```

### Card service

```bash
cd card-service
uv sync
uv run uvicorn src.main:app --reload --port 8002
```

### Frontend

```bash
cd frontend
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev   # http://localhost:3000
```

For a production build:

```bash
pnpm build && pnpm start
```

---

## CI/CD & published images

`.github/workflows/build.yml` runs on pushes to `main`, version tags (`v*`), and PRs:

1. **Test** — runs `pytest` for `backend` and `card-service` against a Postgres service container.
2. **Build & push** — builds multi-arch (`linux/amd64`, `linux/arm64`) images for `backend`, `frontend`, and `card-service`, pushing to GitHub Container Registry (`ghcr.io/allvapps/...`). Images are not pushed on pull requests.

Image tags:

| Trigger              | Tags produced                          |
|----------------------|----------------------------------------|
| Push to `main`       | `dev-<sha>`, `dev-latest`              |
| Tag `vX.Y.Z`         | `X.Y.Z`, `X.Y`, `latest`               |

### Deploying prebuilt images

Pull the desired tag and run the same services as in `docker-compose.yml`, swapping the `build:` directives for `image:` references — for example:

```yaml
backend:
  image: ghcr.io/allvapps/autopilotairlines-backend:dev-latest
frontend:
  image: ghcr.io/allvapps/autopilotairlines-frontend:dev-latest
card-service:
  image: ghcr.io/allvapps/autopilotairlines-cardservice:dev-latest
```

For a non-local deployment, set `NEXT_PUBLIC_API_URL` on the frontend to the publicly reachable backend URL and set `CORS_ALLOW_ORIGINS` on the backend to the frontend's origin.

---

## Health checks & troubleshooting

- **Postgres readiness:** Compose waits on `pg_isready`; the backend and card-service start only after Postgres is healthy.
- **Backend won't start / DB errors:** confirm both `autopilot` and `cardservice` databases exist. On a fresh volume they are created automatically; if you reused an old volume, run `docker compose down -v` to reinitialize.
- **AI agent errors / 401 from provider:** verify the LLM provider block in `.env.dev`. For Bedrock SSO, the session token likely expired — re-run `./refresh-aws-creds.sh`.
- **Frontend can't reach the API:** check `NEXT_PUBLIC_API_URL` and that `CORS_ALLOW_ORIGINS` includes the frontend origin.
- **Reset everything:** `docker compose down -v && docker compose up --build`.
