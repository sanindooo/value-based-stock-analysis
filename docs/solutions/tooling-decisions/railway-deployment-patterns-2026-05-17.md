---
title: Railway Deployment Patterns for Monorepo with Postgres
date: 2026-05-17
category: tooling-decisions
module: infrastructure/deployment
problem_type: tooling_decision
component: tooling
severity: medium
applies_when:
  - Deploying a monorepo (frontend + backend + database) to Railway
  - Backend uses SQLAlchemy with both async and sync drivers
  - Railway provides DATABASE_URL without driver-specific prefixes
  - Frontend needs to connect to backend service via internal networking
tags:
  - railway
  - deployment
  - postgres
  - docker
  - monorepo
  - driver-prefix
  - sqlalchemy
related_components:
  - database
  - service_object
---

# Railway Deployment Patterns for Monorepo with Postgres

## Context

This project deploys a monorepo (Next.js frontend + FastAPI backend + Postgres) to Railway. Each service runs in its own container. Railway provides a `DATABASE_URL` environment variable in the format `postgresql://user:pass@host:port/db` — but SQLAlchemy needs driver-specific prefixes (`postgresql+asyncpg://` for async, `postgresql+psycopg2://` for sync). This mismatch caused deployment failures until an auto-fix was implemented.

## Guidance

### Pattern 1: Postgres Driver Prefix Auto-Fix

Railway's `DATABASE_URL` uses the bare `postgresql://` prefix. SQLAlchemy requires driver-specific prefixes. Instead of managing separate env vars or Railway templates, auto-fix at application startup:

```python
from pydantic import model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stockanalyzer"
    database_url_sync: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _fix_db_drivers(self) -> "Settings":
        # Normalize to bare prefix first
        base = (self.database_url
            .replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://"))
        if not base.startswith("postgresql://"):
            base = self.database_url

        # Apply correct driver prefixes
        self.database_url = base.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not self.database_url_sync:
            self.database_url_sync = base.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self
```

This handles three scenarios:
- Railway provides `postgresql://` → auto-adds `+asyncpg` and `+psycopg2`
- Developer provides `postgresql+asyncpg://` locally → normalizes and derives sync URL
- `database_url_sync` explicitly set → doesn't override it

### Pattern 2: Minimal Production Dockerfiles

Keep Dockerfiles simple. Railway handles the build and deployment lifecycle:

**Backend (Python/FastAPI):**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend (Next.js):**
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

Key points:
- No multi-stage builds needed for this scale (simplicity over image size optimization)
- `--no-cache-dir` for pip saves image space
- `package-lock.json*` with glob handles missing lockfile gracefully
- Build happens in the Dockerfile so Railway deploys a ready-to-run image

### Pattern 3: Docker Compose for Local Development

Docker Compose mirrors the Railway setup locally with development conveniences (hot reload, volume mounts):

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: stockanalyzer
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/stockanalyzer
    depends_on:
      - db
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    command: npm run dev
    environment:
      BACKEND_URL: http://backend:8000
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - frontend_modules:/app/node_modules  # Preserve node_modules from build
```

The `frontend_modules` named volume prevents the host's `node_modules` from overwriting the container's installed dependencies.

### Pattern 4: Service-to-Service Communication

In Railway, services communicate via internal networking. The frontend references the backend via an environment variable:

- **Railway**: `BACKEND_URL=http://backend.railway.internal:8000` (internal DNS)
- **Docker Compose**: `BACKEND_URL=http://backend:8000` (Docker service name)
- **Local development**: `BACKEND_URL=http://localhost:8000` (default fallback)

The `backendFetch` helper reads `process.env.BACKEND_URL` once, making all three environments transparent.

### Pattern 5: Environment Variable Strategy

| Variable | Railway | Docker Compose | Local |
|----------|---------|---------------|-------|
| `DATABASE_URL` | Auto-provided by Railway Postgres | Explicit with driver prefix | From `.env` |
| `BACKEND_URL` | Internal Railway URL | Docker service name | `http://localhost:8000` |
| `FMP_API_KEY` | Railway service variable | From `.env` file | From `.env` file |
| `ANTHROPIC_API_KEY` | Railway service variable | From `.env` file | From `.env` file |

The pattern: Railway auto-provides infrastructure URLs; API keys come from Railway service variables (set once in dashboard); local dev uses `.env` file (git-ignored).

## Why This Matters

**The driver prefix issue is subtle**: The app deploys successfully but crashes on first database access with `sqlalchemy.exc.ArgumentError: Could not parse rfc1738 URL`. The auto-fix validator prevents this entirely — no manual Railway config needed.

**Environment parity**: Docker Compose + the driver auto-fix means local development uses the same code paths as production. No "works locally, fails in Railway" surprises.

**Monorepo simplicity**: One repo, three services, one docker-compose for local, Railway watches each service directory. No need for Turborepo, Nx, or workspace tooling at this scale.

## When to Apply

- Deploying to Railway with Postgres (the driver prefix issue is Railway-specific)
- Using SQLAlchemy with multiple drivers (async + sync)
- Monorepo with separate frontend/backend services
- Need local dev parity with production

## Examples

The driver auto-fix handles the most common deployment failure. Before:

```
# Railway provides:
DATABASE_URL=postgresql://user:pass@host:5432/db

# SQLAlchemy errors:
sqlalchemy.exc.ArgumentError: Could not parse rfc1738 URL from string 'postgresql://...'
# (for asyncpg driver which expects postgresql+asyncpg://)
```

After the auto-fix in Settings, it "just works" — no Railway template changes needed.

## Related

- [[backend-cold-start-retry-strategy-2026-05-17]] — handles Railway cold starts at the network level
- `stock-analyzer/backend/app/core/config.py`: Settings with driver auto-fix
- `stock-analyzer/docker-compose.yml`: Local development setup
- Commit `dfd83a2`: Auto-fix Postgres driver prefixes for Railway compatibility
- Commit `95339f9`: Update frontend Dockerfile for production build
