# Stock Analyzer

Value-based stock screening, research, and valuation pipeline. Screens ~900 tickers against Buffett/Graham-style thresholds, then runs AI-powered deep research on the best candidates using SEC filings, financial news, and Claude.

## Architecture

```
frontend/          Next.js 14, Tailwind CSS       Port 3000
backend/           FastAPI, SQLAlchemy (async)     Port 8000
docker-compose.yml Postgres 16, backend, frontend
```

**Production**: Railway (Postgres + backend + frontend). Auto-deploys from `main` branch.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development outside Docker)
- Python 3.12+ (for running execution scripts)

### 1. Environment variables

```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, FINNHUB_API_KEY, FMP_API_KEY, SITE_SECRET
```

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | Claude API for research agent |
| `FINNHUB_API_KEY` | Yes | Financial news for research |
| `FMP_API_KEY` | Yes | Financial Modeling Prep (ticker universe) |
| `SITE_SECRET` | Yes | Session signing |
| `USER_EMAIL` | No | SEC EDGAR identity header |

### 2. Start everything

```bash
docker compose up
```

This starts Postgres, the backend (with hot reload), and the frontend (with hot reload). Visit `http://localhost:3000`.

### 3. Run database migrations

On first startup or after pulling new migration files:

```bash
docker exec stock-analyzer-backend-1 alembic upgrade head
```

## Common Tasks

### Run a stock screen

Visit `http://localhost:3000/screening` and click "Run New Screen". This fetches data from Yahoo Finance for ~900 tickers, scores them against value investing thresholds, and returns the top matches.

### Research a stock

From the screening results, click "Research" on any stock. This triggers the AI research agent which:
1. Pulls the latest 10-K/10-Q from SEC EDGAR
2. Fetches recent financial news via Finnhub
3. Sends everything to Claude for analysis
4. Produces a buy/hold/sell verdict with confidence level

### Refresh conviction scores

Click "Refresh scores" in the screening toolbar to recompute conviction data with the latest thresholds. This also applies fallback calculations (e.g., PEG from P/E and earnings growth).

### Create a new migration

```bash
docker exec stock-analyzer-backend-1 alembic revision --autogenerate -m "description of change"
```

Then apply it:

```bash
docker exec stock-analyzer-backend-1 alembic upgrade head
```

## Data Sync (Local <-> Production)

Sync data between local Docker Postgres and Railway production. Requires the Railway CLI (`brew install railway`) and `psql` installed locally.

### First-time setup

From the **repo root** (not `stock-analyzer/`):

```bash
cd /path/to/value-based-stock-analysis
python3 -m venv .venv
source .venv/bin/activate
pip install python-dotenv
```

### Sync commands

All commands must be run from the **repo root** with the venv activated:

```bash
source .venv/bin/activate

# Preview what would sync (no changes)
python execution/sync_db.py local-to-prod --dry-run

# Push local data to production
python execution/sync_db.py local-to-prod

# Pull production data to local
python execution/sync_db.py prod-to-local
```

The sync uses `ON CONFLICT DO NOTHING` — existing rows with matching primary keys are preserved, only new rows are added.

## Railway Deployment

Production is on Railway at `stocks.granite-automations.app`. Deploys automatically when `main` is pushed.

### Manual operations

```bash
# Check service status
railway service list --json

# View logs
railway logs --service backend --lines 50
railway logs --service frontend --lines 50

# Build logs (if deploy fails)
railway logs --service backend --build --lines 50

# Run migrations on production
railway run --service backend alembic upgrade head
```

### Service configuration

| Service | Builder | Root Dir | Sleep |
|---------|---------|----------|-------|
| backend | Dockerfile | `stock-analyzer/backend` | 15 min idle |
| frontend | Dockerfile | `stock-analyzer/frontend` | 5 min idle |
| Postgres | Managed | - | Always on |

Backend auto-runs `alembic upgrade head` before each deploy (pre-deploy command).

## Project Structure

```
stock-analyzer/
  backend/
    app/
      api/            API route handlers (screening, research, data, preferences)
      core/           Config, settings
      models/         SQLAlchemy models (Stock, ScreeningResult, ResearchReport, etc.)
      schemas/        Pydantic request/response schemas
      services/       Business logic
        screener.py       Screening engine (thresholds, conviction, scoring)
        scorer.py         Composite scoring with category weights
        yahoo_client.py   Yahoo Finance data fetcher with fallback calculations
        research_agent.py AI research pipeline (EDGAR + Finnhub + Claude)
        edgar_client.py   SEC EDGAR filing fetcher
        news_client.py    Finnhub news client
        fmp_client.py     Financial Modeling Prep client (ticker universe)
        ticker_universe.py  Screening universe (~900 tickers)
    alembic/          Database migrations
    tests/            Pytest test suite
  frontend/
    src/
      app/            Next.js pages and API route proxies
      components/     React components (stock cards, conviction bars, etc.)
      contexts/       React contexts (TaskContext for screening state)
      lib/            Shared utilities (API client)
  docker-compose.yml
  .env.example
```

## Thresholds

Default screening thresholds (Buffett/Graham-style):

| Metric | Threshold | Direction |
|--------|-----------|-----------|
| P/E | <= 20 | Lower is better |
| PEG | <= 1.0 | Lower is better |
| P/B | <= 1.5 | Lower is better |
| D/E | <= 0.5 | Lower is better |
| Current Ratio | >= 1.5 | Higher is better |
| ROE | >= 12% | Higher is better |
| Gross Margin | >= 25% | Higher is better |
| Net Margin | >= 8% | Higher is better |
| Beta | <= 1.0 | Lower is better |

Thresholds are configurable via preferences (`/settings`).
