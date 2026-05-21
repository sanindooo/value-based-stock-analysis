---
title: Research Status Stuck After Background Task Completion
date: 2026-05-17
category: ui-bugs
module: full-stack/research-pipeline
problem_type: ui_bug
component: background_job
symptoms:
  - Screening results show "researching" stage after research retries complete successfully
  - Research reports table does not populate until manual page refresh
  - Stage badges stuck on "retry required" despite reports being visible on research page
root_cause: async_timing
resolution_type: code_fix
severity: high
tags:
  - cache-invalidation
  - background-tasks
  - polling
  - stale-data
  - nextjs-cache
  - research-pipeline
related_components:
  - frontend_stimulus
  - service_object
---

# Research Status Stuck After Background Task Completion

## Problem

After research retries completed successfully (reports generated and visible on the research page), the screening results page still showed stocks as "researching" or "retry required". Users had to manually refresh to see updated stages. The research reports table also didn't auto-populate when individual tasks finished.

## Symptoms

- Screening result rows displayed "researching" badge indefinitely after successful research completion
- "Retry" buttons remained visible despite research already being done
- Research reports page showed stale (empty) list until manual browser refresh
- Database contained correct `stage = "researched"` values, but the UI served cached stale responses

## What Didn't Work

- Relying solely on tag-based cache invalidation via mutation routes (POST/PATCH). Background tasks mutate the database directly without going through the Next.js API layer, so `revalidateTag()` never fires for their state changes.
- Only invalidating the `research-reports` cache when all active tasks were complete (`data.length === 0`). Individual task completions created reports that remained invisible until the final task finished.

## Solution

Three coordinated changes across frontend and backend:

**1. Poll parameter to bypass server-side cache** (`frontend/src/app/api/screening/[runId]/route.ts`):

```typescript
// Before: pollStages() hit the cached 1h-TTL endpoint
const fetchOptions: RequestInit = {
  cache: "force-cache",
  next: { tags: [`screening-run-${runId}`], revalidate: 3600 },
}

// After: poll=1 signals "bypass cache for real-time polling"
const poll = searchParams.get("poll")
const fetchOptions: RequestInit = poll
  ? { cache: "no-store", headers: { "Content-Type": "application/json" } }
  : { cache: "force-cache", next: { tags: [`screening-run-${runId}`], revalidate: 3600 }, headers: { "Content-Type": "application/json" } }
```

The client adds `poll=1` to the URLSearchParams when calling `pollStages()`, which the API route strips before forwarding to the backend.

**2. Always invalidate reports cache during active polling** (`frontend/src/app/api/research/active/route.ts`):

```typescript
// Before: only invalidated when all tasks done
if (res.ok && Array.isArray(data) && data.length === 0) {
  revalidateTag("research-reports", "max")
}

// After: always invalidate — background tasks create reports without touching the cache layer
if (res.ok) {
  revalidateTag("research-reports", "max")
}
```

**3. Revert stage on research failure** (`backend/app/services/research_agent.py`):

```python
except Exception as exc:
    # ... mark task as failed ...
    await db.execute(
        update(ScreeningResult)
        .where(
            ScreeningResult.stock_ticker == ticker,
            ScreeningResult.stage == "researching",
        )
        .values(stage="screened")
    )
    await db.commit()
    raise
```

Without this, failed research left stocks permanently stuck in "researching" — they couldn't be retried because the retry logic only picks up stocks in the "screened" stage.

## Why This Works

The root cause is a **cache layer mismatch**: Next.js tag-based cache invalidation relies on mutations flowing through API routes that call `revalidateTag()`. But background tasks (FastAPI `BackgroundTasks`) mutate the database directly — they don't make HTTP requests through the Next.js layer. This means:

1. Backend changes `stage: "researching" -> "researched"` in Postgres
2. Next.js still serves the cached response showing `stage: "researching"`
3. No mutation route was called, so no `revalidateTag()` fires

The `poll` parameter pattern solves this by letting polling requests opt out of the cache entirely. Non-polling requests (normal page loads, navigation) still benefit from caching. The always-invalidate on active-check ensures the reports list refreshes as individual tasks complete rather than waiting for all to finish.

## Prevention

- **Pattern**: When background tasks mutate data that a cached endpoint serves, the polling path for that data must bypass the cache. Use a query parameter (e.g., `poll=1`) to signal "real-time mode" vs "cacheable mode" on the same route.
- **Pattern**: When background tasks can fail, always implement a stage rollback so the entity returns to a retryable state. Test the failure path explicitly.
- **Pattern**: Prefer aggressive cache invalidation during active polling over conservative invalidation. The cost of an extra backend hit during a 3-second polling window is negligible compared to showing stale data.

## Related Issues

- [[nextjs-tag-based-cache-revalidation-2026-05-17]] — the caching architecture this bug exposed a gap in
- [[background-task-lifecycle-management-2026-05-17]] — the task system whose DB mutations bypassed the cache
- Commit `de04984`: Fix merged to main
