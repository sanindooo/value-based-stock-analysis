---
title: Next.js Tag-Based Cache Revalidation Strategy
date: 2026-05-17
category: architecture-patterns
module: frontend/api-routing
problem_type: architecture_pattern
component: frontend_stimulus
severity: medium
applies_when:
  - Next.js frontend proxies API calls to a separate backend service
  - Backend has cold-start latency (e.g. Railway containers)
  - Data has natural staleness windows (5 minutes to 1 hour)
  - Mutations are identifiable and map cleanly to cache tags
tags:
  - nextjs-16
  - cache-revalidation
  - force-cache
  - revalidate-tag
  - api-routes
  - railway
  - cold-start
related_components:
  - service_object
  - background_job
---

# Next.js Tag-Based Cache Revalidation Strategy

## Context

This project has a Next.js 16 frontend that proxies API calls to a separate FastAPI backend running on Railway. Every client request hits a Next.js API route, which forwards it to the backend and returns the response. Without caching, every request triggers a backend round-trip — exposing users to Railway cold-start latency (3-5s), burning FMP API quota (250 req/day free tier), and making navigation feel sluggish.

Next.js 15+ changed caching from opt-out to opt-in. Routes must explicitly declare `cache: "force-cache"` to cache responses. This implementation uses **tag-based cache invalidation**: GET routes cache with named tags, and mutation routes (POST/PUT/PATCH/DELETE) call `revalidateTag()` to bust specific caches on success.

The sequencing was deliberate (session history): the team upgraded from Next.js 14 to 16 *first*, then implemented caching on top of the new defaults. Caching was not retrofitted onto the older version. The cold-start retry wrapper (`backendFetch` with exponential backoff) was also shipped as a prerequisite — caching stale data from a flaky connection would have been worse than no cache.

## Guidance

### Core Pattern

**GET routes** — cache with named tags and a time-based fallback:

```typescript
import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  const res = await backendFetch("/api/screening/runs", {
    cache: "force-cache",
    next: { tags: ["screening-runs"], revalidate: 300 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

**Mutation routes** — bust the cache on success:

```typescript
import { revalidateTag } from "next/cache"

export async function POST(request: NextRequest) {
  const body = await request.json()
  const res = await backendFetch("/api/screening/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (res.ok) revalidateTag("screening-runs", "max")
  return NextResponse.json(data, { status: res.status })
}
```

The `"max"` parameter means "expire immediately" — don't wait for the TTL.

### Tag Naming Convention

| Pattern | Example | Use |
|---------|---------|-----|
| `resource-name` | `screening-runs`, `research-reports` | List-level caches |
| `resource-${id}` | `screening-run-${runId}`, `stock-${ticker}` | Entity-specific caches |
| `shared-name` | `preferences` | Cross-feature shared data |
| `derived-name` | `screening-highlights` | Aggregated/computed data |

### Revalidation Windows

| TTL | Use case | Examples |
|-----|----------|---------|
| **300s (5 min)** | Frequently-changing lists | `screening-runs`, `research-reports`, `screening-highlights` |
| **3600s (1 hour)** | Slowly-changing data | `preferences`, `stock-${ticker}`, `screening-run-${runId}` |

### Which Routes Cache (and Which Don't)

**Cached routes** (`force-cache` + tags):

| Route | Tag(s) | TTL |
|-------|--------|-----|
| `GET /screening` | `screening-runs` | 5m |
| `GET /screening/[runId]` | `screening-run-${runId}` | 1h |
| `GET /screening/highlights` | `screening-highlights` | 5m |
| `GET /screening/thresholds` | `preferences` | 1h |
| `GET /research` | `research-reports` | 5m |
| `GET /preferences` | `preferences` | 1h |
| `GET /data/stocks/[ticker]` | `stock-${ticker}` | 1h |

**Uncached routes** (`force-dynamic` or `no-store`):

| Route | Why |
|-------|-----|
| `GET /research/active` | Polls for active tasks — must reflect real-time state |
| `GET /research/[id]` (status) | Task status polling — must always hit backend |
| `GET /screening/tasks` | Task list for polling — must be real-time |
| `GET /tasks/[taskId]` | Individual task status — must be current |

### Multi-Tag Invalidation

Some mutations invalidate multiple tags because they affect data at different levels:

```typescript
// PATCH /screening/[runId] — updates a specific run
if (res.ok) {
  revalidateTag(`screening-run-${runId}`, "max")  // the specific run
  revalidateTag("screening-highlights", "max")     // aggregated highlights
}
```

```typescript
// POST /screening/runs/[runId]/recompute — recalculates scores
if (res.ok) {
  revalidateTag(`screening-run-${runId}`, "max")
  revalidateTag("screening-runs", "max")
  revalidateTag("screening-highlights", "max")
}
```

### Conditional Invalidation

The research active-tasks endpoint invalidates the reports cache only when no active tasks remain:

```typescript
export async function GET() {
  const res = await backendFetch("/api/research/active", {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  if (res.ok && Array.isArray(data) && data.length === 0) {
    revalidateTag("research-reports", "max")
  }
  return NextResponse.json(data, { status: res.status })
}
```

This ensures completed reports appear immediately when the last task finishes.

## Why This Matters

**Performance**: Cache hits eliminate the backend round-trip entirely. Backend response time is 100-500ms; cache hit is 0-5ms. With a 5-minute TTL on frequently-accessed lists, ~99% of navigation requests skip the backend.

**Cold-start mitigation**: Railway containers spin down after inactivity. Cached responses avoid the 3-5s cold-start penalty. Even one cache hit per session saves noticeable latency.

**API quota conservation**: FMP's free tier allows 250 requests/day. Caching stock profiles (1h TTL) reduces redundant FMP calls by ~96% in a typical browsing session.

**UX**: List pages load instantly on cache hit. Mutations invalidate stale data immediately, so users see fresh results after actions — no manual refresh needed.

A known limitation (session history): the skeleton loader still flashes on initial load because data fetching runs client-side via `useEffect`. Eliminating this would require server-side data fetching (RSC/SSR), which the team explicitly decided not to pursue at this stage.

## When to Apply

- A frontend proxies calls to an external backend (Next.js → FastAPI, Next.js → any remote API)
- The backend is expensive to call (rate-limited, cold-starts, slow queries, paid API)
- Most data has a natural staleness window (minutes to hours)
- Mutations are identifiable and map cleanly to cache tags

**Not applicable when:**
- The backend is in-process (no network round-trip to save)
- All responses are real-time polling data (use `cache: "no-store"`)
- You're already using a client-side cache library (React Query, SWR) that handles this layer

## Examples

### Before: Every request hits the backend

```typescript
export const dynamic = "force-dynamic"

export async function GET() {
  const res = await backendFetch("/api/screening/runs", {
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

Every navigation, every tab switch, every page reload — full backend round-trip. Cold starts compound. FMP quota burns.

### After: Cached with tag-based invalidation

```typescript
import { revalidateTag } from "next/cache"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  const res = await backendFetch("/api/screening/runs", {
    cache: "force-cache",
    next: { tags: ["screening-runs"], revalidate: 300 },
    headers: { "Content-Type": "application/json" },
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const res = await backendFetch("/api/screening/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (res.ok) revalidateTag("screening-runs", "max")
  return NextResponse.json(data, { status: res.status })
}
```

GET within 5 minutes: instant. POST creates a new run: cache busted, next GET gets fresh data. Backend receives ~1/30th the requests.

### Per-entity caching with dynamic tags

```typescript
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()
  const res = await backendFetch(
    `/api/data/stocks/${ticker}${qs ? `?${qs}` : ""}`,
    {
      cache: "force-cache",
      next: { tags: [`stock-${ticker}`], revalidate: 3600 },
      headers: { "Content-Type": "application/json" },
    }
  )
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

Each ticker's cache is independent. Refreshing AAPL doesn't invalidate GOOGL. This prevents over-invalidation.

## Related

- Commit `571aeea`: Next.js 14 → 16 upgrade (changed caching defaults to opt-in)
- Commit `001047e`: Tag-based cache revalidation added to all proxy API routes
- Commit `d576b83`: `backendFetch` retry wrapper (prerequisite for safe caching)
- `stock-analyzer/frontend/src/lib/backend-fetch.ts`: Retry wrapper used by all API routes
