---
title: External API Client Architecture with Postgres-Backed Caching
date: 2026-05-17
category: architecture-patterns
module: backend/services
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - Integrating with external APIs that have rate limits or quotas
  - Data is relatively stable and can be cached for hours
  - Multiple endpoints needed per entity (requiring parallel fetching)
  - Batch operations must respect concurrency limits
tags:
  - api-client
  - rate-limiting
  - postgres-cache
  - staleness-check
  - fmp
  - yahoo-finance
  - concurrency
  - semaphore
related_components:
  - database
  - background_job
---

# External API Client Architecture with Postgres-Backed Caching

## Context

The stock analysis backend integrates with multiple external financial data APIs (FMP, Yahoo Finance, SEC EDGAR, Finnhub) that have different rate limits, cost structures, and reliability characteristics. A screening run of ~150 tickers makes 450+ API calls (3 endpoints per ticker for FMP). Without a strategy, quota is exhausted in a single run, requests fail under load, and the same data is re-fetched unnecessarily.

The solution is a layered API client architecture: Postgres-backed caching with staleness checks, in-memory rate limiting with daily counters, semaphore-controlled concurrency, and graceful degradation on quota exhaustion.

## Guidance

### Architecture Overview

```
Request flow:
  Screener → API Client → [Staleness Check] → DB (cache hit) → return
                                             → External API (cache miss) → upsert DB → return
```

### Pattern 1: Postgres-Backed Staleness Cache

Every API client checks the database before calling the external API. If cached data is fresh enough (within the staleness window), it returns the cached copy — zero API calls:

```python
STALENESS_HOURS = 24

async def fetch_and_cache_ticker(self, client, db, ticker, force=False):
    if not force:
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        existing = result.scalar_one_or_none()
        if existing and existing.last_updated:
            age = datetime.now(timezone.utc) - existing.last_updated.replace(tzinfo=timezone.utc)
            if age < timedelta(hours=STALENESS_HOURS):
                return existing  # Cache hit — no API call

    # Cache miss — fetch from external API
    profile = await self.fetch_profile(client, ticker)
    metrics = await self.key_metrics_ttm(client, ticker)
    ratios = await self.ratios_ttm(client, ticker)

    stock_data = self.map_to_stock(profile, metrics, ratios, ticker)

    # Upsert into DB
    existing = (await db.execute(select(Stock).where(Stock.ticker == ticker))).scalar_one_or_none()
    if existing:
        for key, value in stock_data.items():
            setattr(existing, key, value)
    else:
        db.add(Stock(**stock_data))

    await db.commit()
    return stock
```

### Pattern 2: In-Memory Rate Limiting with Daily Counter

For APIs with daily quotas (FMP: 250 req/day free tier), track usage in-memory with an async lock:

```python
DAILY_LIMIT = 250
RATE_WARN_THRESHOLD = 225

class FMPClient:
    def __init__(self, max_concurrency=5):
        self._daily_requests = 0
        self._day_started = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def _reset_counter_if_new_day(self):
        now = datetime.now(timezone.utc)
        if now.date() > self._day_started.date():
            self._daily_requests = 0
            self._day_started = now

    def _check_rate_limit(self):
        self._reset_counter_if_new_day()
        if self._daily_requests >= DAILY_LIMIT:
            raise RateLimitExceeded("Daily limit reached")
        if self._daily_requests >= RATE_WARN_THRESHOLD:
            logger.warning("Approaching limit: %d/%d", self._daily_requests, DAILY_LIMIT)

    async def _get(self, client, path, params=None):
        async with self._lock:
            self._check_rate_limit()
            self._daily_requests += 1
        # ... make the request
```

### Pattern 3: Semaphore-Controlled Batch Concurrency

Batch operations use `asyncio.Semaphore` to limit concurrent API calls. Each ticker gets its own DB session to avoid `asyncio.gather` concurrent session access:

```python
async def fetch_and_cache_batch(self, client, db, tickers, cancel_check=None):
    from app.db import async_session

    results = []
    rate_limited = False

    async def _fetch_one(ticker):
        nonlocal rate_limited
        if rate_limited:
            return None
        async with self._semaphore:
            try:
                async with async_session() as ticker_db:
                    return await self.fetch_and_cache_ticker(client, ticker_db, ticker)
            except RateLimitExceeded:
                rate_limited = True
                return None
            except (httpx.HTTPStatusError, FMPClientError):
                return None

    batch_size = self._semaphore._value  # Match concurrency to semaphore
    for i in range(0, len(tickers), batch_size):
        if cancel_check and await cancel_check():
            break
        if rate_limited:
            break
        batch = tickers[i:i + batch_size]
        batch_results = await asyncio.gather(*[_fetch_one(t) for t in batch])
        results.extend([s for s in batch_results if s is not None])

    return results
```

### Pattern 4: Graceful Degradation with Data Warnings

When individual endpoints return 402 (paid-tier required), track it per-stock rather than failing the whole operation:

```python
data_warnings: dict[str, int] = {}

try:
    profile = await self.fetch_profile(client, ticker)
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 402:
        data_warnings["profile"] = 402
    else:
        raise

stock_data["data_warnings"] = data_warnings if data_warnings else None
```

The frontend can then show which metrics are missing and why.

### Pattern 5: Thread-Offloaded Sync Libraries

Yahoo Finance uses `yfinance` (synchronous). Wrap in `asyncio.to_thread` for async compatibility:

```python
def _fetch_ticker_sync(ticker: str) -> dict[str, Any]:
    import yfinance as yf
    t = yf.Ticker(ticker)
    info = t.info
    # ... process and return dict

async def fetch_yahoo_ticker(ticker: str) -> dict[str, Any]:
    return await asyncio.to_thread(_fetch_ticker_sync, ticker)
```

### Pattern 6: Response Size Safety Cap

Prevent runaway responses from consuming memory:

```python
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB

resp = await client.get(url, params=params)
resp.raise_for_status()
if len(resp.content) > MAX_RESPONSE_BYTES:
    raise FMPClientError("Response exceeded size limit.")
```

## Why This Matters

**Quota conservation**: FMP's free tier allows 250 req/day. A single screening run of 150 tickers would consume 450 requests (3 endpoints each) without the staleness cache. With 24h caching, a second run on the same day costs zero API calls.

**Reliability under load**: The semaphore prevents overwhelming external APIs. Without it, 150 concurrent requests trigger rate limiting or connection failures.

**Graceful failure**: The `rate_limited` flag in batch processing stops further API calls the moment quota is exhausted, preserving whatever data was already fetched rather than failing the entire batch.

**Observability**: `data_warnings` and `requests_remaining` properties give the frontend visibility into API health without exposing internal state.

## When to Apply

- Integrating any external API with rate limits or daily quotas
- Data that doesn't change faster than your staleness window (financial data: 24h is fine)
- Batch operations over many entities that hit the same API
- Multiple quality tiers of API access (free vs. paid endpoints)

## Examples

The project has four API clients following variations of this pattern:

| Client | Rate Limit | Staleness | Concurrency | Notes |
|--------|-----------|-----------|-------------|-------|
| FMP (`fmp_client.py`) | 250/day | 24h | 5 | Full pattern: daily counter + semaphore + 402 tracking |
| Yahoo (`yahoo_client.py`) | ~2000/hr | 24h | 10 (configurable) | Thread-offloaded sync lib, no daily counter needed |
| EDGAR (`edgar_client.py`) | 10 req/s | N/A | 3 | SEC requires User-Agent with email, rate limit is per-second |
| Finnhub (`news_client.py`) | 60 req/min | N/A | 3 | News is time-sensitive, no staleness cache |

## Related

- [[nextjs-tag-based-cache-revalidation-2026-05-17]] — HTTP-level caching layer built on top of this
- [[backend-cold-start-retry-strategy-2026-05-17]] — frontend retry logic that complements backend caching
- `stock-analyzer/backend/app/services/fmp_client.py`: Primary implementation
- `stock-analyzer/backend/app/services/yahoo_client.py`: Thread-offloaded variant
- Commit `6a45a14`: Initial FMP client with caching and rate limiting
- Commit `31afb53`: Added semaphore-based concurrency control
