---
title: Backend Cold-Start Retry Strategy
date: 2026-05-17
category: architecture-patterns
module: frontend/api-routing
problem_type: architecture_pattern
component: frontend_stimulus
severity: medium
applies_when:
  - Frontend connects to a backend deployed on a container platform with cold starts (Railway, Fly.io, etc.)
  - Backend spins down after inactivity and takes 3-5 seconds to wake
  - Connection errors are transient and resolve after the container starts
tags:
  - railway
  - cold-start
  - retry
  - exponential-backoff
  - backend-fetch
  - resilience
related_components:
  - service_object
---

# Backend Cold-Start Retry Strategy

## Context

The FastAPI backend runs on Railway and spins down after inactivity. When a user hits the frontend after idle time, the first backend request fails with connection errors (`ETIMEDOUT`, `ECONNREFUSED`, `ECONNRESET`, `UND_ERR_CONNECT_TIMEOUT`) because the container hasn't started yet. Without retry logic, users see a blank error page on their first visit.

This pattern wraps all backend calls in a retry-with-backoff helper that absorbs cold-start latency transparently. It was implemented as a prerequisite before adding caching — caching stale data from a flaky connection would be worse than no cache.

## Guidance

A single `backendFetch` helper replaces direct `fetch()` calls to the backend. It retries only on network-level errors (not HTTP status codes) with exponential backoff:

```typescript
// stock-analyzer/frontend/src/lib/backend-fetch.ts
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

const RETRYABLE_CODES = new Set([
  "ETIMEDOUT",
  "ECONNREFUSED",
  "ECONNRESET",
  "UND_ERR_CONNECT_TIMEOUT"
])
const MAX_RETRIES = 4
const BASE_DELAY_MS = 1000

function isRetryable(error: unknown): boolean {
  if (error instanceof TypeError && error.message === "fetch failed" && error.cause) {
    const cause = error.cause as { code?: string }
    return cause.code != null && RETRYABLE_CODES.has(cause.code)
  }
  return false
}

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${BACKEND_URL}${path}`
  let lastError: unknown

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fetch(url, init)
    } catch (error) {
      lastError = error
      if (attempt < MAX_RETRIES && isRetryable(error)) {
        await new Promise((r) => setTimeout(r, BASE_DELAY_MS * 2 ** attempt))
        continue
      }
      throw error
    }
  }

  throw lastError
}
```

### Key Design Decisions

1. **Only retries network errors, not HTTP errors.** A 500 from the backend is a real error. `ECONNREFUSED` means the container isn't ready — retrying will succeed.

2. **Exponential backoff: 1s, 2s, 4s, 8s.** Total worst-case wait: 15 seconds. Railway containers typically start in 3-5s, so most requests succeed on retry 2 or 3.

3. **Error detection via `TypeError` + `cause.code`.** Node.js wraps network errors in a `TypeError("fetch failed")` with the actual error code on `.cause`. This is the reliable way to distinguish network failures from application errors.

4. **4 retries maximum.** If the backend hasn't started after 15 seconds of total backoff, something is genuinely broken — surface the error rather than spinning indefinitely.

5. **Transparent to callers.** API routes call `backendFetch(path, init)` exactly like they'd call `fetch()`. The retry logic is invisible; callers get either a successful `Response` or a thrown error.

## Why This Matters

Without this, the first request after any idle period fails. Users see errors, hit refresh manually, and lose trust. With it, cold starts are absorbed with a brief delay that feels like "slow loading" rather than "broken app."

This is also the foundation for the caching layer — `backendFetch` is the single point through which all backend communication flows, making it easy to add `cache` and `next` options for tag-based revalidation.

## When to Apply

- Backend is on a platform that spins down containers (Railway, Fly.io, Cloud Run with scale-to-zero)
- You can identify a specific set of error codes that mean "container not ready"
- Total acceptable wait time fits within user patience (15s max in this case)

**Not applicable when:**
- Backend is always-on (no cold starts)
- You need retries on HTTP-level errors (use a different pattern with status code checks)
- The latency budget is tight (WebSocket connections, real-time feeds)

## Examples

All API routes use `backendFetch` instead of raw `fetch`:

```typescript
// Before (fragile)
const res = await fetch(`${process.env.BACKEND_URL}/api/screening/runs`)

// After (resilient)
import { backendFetch } from "@/lib/backend-fetch"
const res = await backendFetch("/api/screening/runs", {
  cache: "force-cache",
  next: { tags: ["screening-runs"], revalidate: 300 },
})
```

The retry wrapper composes cleanly with Next.js caching options — they're just part of the `init` parameter passed through.

## Related

- [[nextjs-tag-based-cache-revalidation-2026-05-17]] — the caching layer built on top of this
- Commit `d576b83`: Initial implementation of retry logic
- `stock-analyzer/frontend/src/lib/backend-fetch.ts`: The implementation file
