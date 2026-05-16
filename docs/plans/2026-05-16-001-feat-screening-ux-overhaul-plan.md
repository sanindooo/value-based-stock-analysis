---
title: "feat: Screening & Research UX Overhaul"
type: feat
status: active
date: 2026-05-16
origin: docs/brainstorms/screening-ux-overhaul-requirements.md
---

# feat: Screening & Research UX Overhaul

## Summary

Implements the 22-requirement UX and reliability overhaul across 4 phases: backend infrastructure (TaskStatus expansion, cancel, limits, run management), data completeness (missing metrics, FMP 402 tracking, parallelization), screening frontend (React Context for task persistence, layered progress, grid/list toggle, stock identity), and research + polish (research filtering, traffic-light metrics, skeleton loaders, metrics reference page, mobile overhaul). Backend changes land first so the frontend has the APIs it needs.

---

## Problem Frame

The screening pipeline produces useful results but the experience around it is fragile — navigating away loses progress visibility, failed runs accumulate with no cleanup, the results page lacks view modes and stock identity, and the research page has no filtering. See origin for the full pain narrative (see origin: `docs/brainstorms/screening-ux-overhaul-requirements.md`).

---

## Requirements

- R1. Screening progress persists across page navigation
- R2. Layered progress display (stage, elapsed time, counts, activity log)
- R3. Cancel button — graceful stop, saves partial results
- R4. Configurable limits: max stocks to examine, max matches to collect
- R5. Each run displays the filter settings that produced it
- R6. All runs visible with status badges (completed, failed, partial, running)
- R7. Delete any run from the list
- R8. FMP free-tier warning indicator on affected stocks
- R9. Grid/list view toggle on screening results with detail modal
- R10. Full company name + optional website alongside ticker
- R11. Exceptional stock visual highlighting in results
- R12. Exceptional stocks surfaced on dashboard
- R13. Research progress displayed on frontend (existing backend stages)
- R14. Research filtering (recommendation, confidence, sector, date) + ticker search
- R15. Research grid/list view toggle with detail modal
- R16. Research report deduplication
- R17. Skeleton loaders across the app
- R18. Mobile/responsive layout overhaul
- R19. Metrics reference page
- R20. Traffic-light color coding on research report metric sidebar
- R21. Screener evaluates all 15 canonical metrics
- R22. External API calls batched/parallelized where possible

**Origin actors:** Single user (A1) — the value investor running screens and reviewing research.
**Origin flows:** F1 (Run and monitor a screen), F2 (Browse and triage results), F3 (Browse and search research reports).
**Origin acceptance examples:** AE1 (R1 — navigation persistence), AE2 (R3/R6 — cancel partial), AE3 (R4 — limits), AE4 (R8 — 402 warning), AE5 (R9 — list view modal).

---

## Scope Boundaries

- No WebSocket/SSE — polling is sufficient and already working
- No backend task system rearchitecture (no Celery/Redis)
- No changes to the scoring algorithm weights or category structure
- Research pipeline feature changes deferred per origin

### Deferred to Follow-Up Work

- Scoring algorithm tuning (e.g., adjusting category weights, normalization ranges)
- Advanced charting or data visualization beyond the metrics reference page
- Multi-user auth and access control
- Research pipeline improvements (separate brainstorm after evaluation)

---

## Context & Research

### Relevant Code and Patterns

- **Backend service pattern**: Plain functions/classes in `app/services/`, async DB via `async_session()`, each service handles its own error boundary
- **Background task pattern**: `TaskStatus` row created → `BackgroundTasks.add_task()` → worker updates `progress` field → `status = "completed"` on finish → frontend polls every 3s
- **Frontend proxy pattern**: All API calls go through Next.js API routes (`src/app/api/`) which proxy to FastAPI backend. Single `apiFetch<T>()` utility in `src/lib/api.ts`
- **Frontend state**: Pure React `useState` + `useCallback` + `useEffect` — no external state management. Each page manages its own state independently
- **Stock model**: `company_name` already populated from FMP profile. `website` field absent. 6 growth metrics always NULL (FMP free tier limitation)
- **Screening loop**: `screener.py:262-286` — single `for stock in stocks` loop, commits all results in one batch at end, no cancellation check, no incremental saves
- **FMP client**: 3 requests per ticker (profile, key-metrics-ttm, ratios-ttm), sequential, 250 req/day limit with in-memory counter

### External References

- FMP stable API docs for available endpoints and batch support (user confirmed: no native batch, must manually parallelize within rate limits)
- User's canonical 15 metrics list defines the authoritative set for screening evaluation

---

## Key Technical Decisions

- **React Context for task state persistence** — lightest option that survives navigation without adding a dependency. A `TaskContext` provider wraps the app layout and holds in-progress task IDs, polling state, and progress data. Pages subscribe to it instead of managing their own polling. (vs. Zustand/Redux — adds dependency for a single-user app's simple state needs)
- **Extend TaskStatus with a JSON `progress_data` column** — keeps the existing `progress` string field for backward compatibility while adding structured data (counts, activity log entries). Single model, single polling endpoint. (vs. separate TaskProgress table — overkill for single-user, adds join overhead)
- **Cancel via DB flag polling** — the screening loop checks `TaskStatus.status == "cancelling"` every 10 stocks. Simple, no async task cancellation complexity. DB query cost is negligible per 10 stocks. (vs. asyncio.Task.cancel() — requires in-memory task references, lost on restart)
- **Incremental result saves** — commit ScreeningResult rows in batches of 10 during the loop instead of one batch at end. Enables cancel to preserve partial results without data loss. (vs. single commit at end — current approach, but cancel would lose everything in progress)
- **Research dedup at query level** — `DISTINCT ON (stock_ticker)` ordered by `created_at DESC` returns the latest report per ticker. Preserves history (no schema constraint preventing re-research). Frontend shows latest by default with option to view history. (vs. unique constraint — prevents legitimate re-research of the same stock)
- **Shared ViewToggle and StockDetailModal components** — used by both screening results and research reports pages for consistency. Grid/list preference stored in localStorage per page.
- **Exceptional stock threshold: composite_score >= 80** — derived from the 0-100 scoring range. Configurable in preferences later if needed, hardcoded initially. Stocks meeting this threshold get a gold border/badge in results and a highlights section on the dashboard. **Validation note:** After the first 3 screening runs, check the actual score distribution. If most passing stocks score above 80 (section always full) or below 80 (always empty), adjust the threshold.
- **Metric set: additive, not replacement** — The canonical 15 metrics define what appears on the /learn page and gets traffic-light treatment. The scorer keeps all existing 22 metrics AND adds 7 new ones. No metrics are removed. This preserves current scoring behavior while expanding coverage.
- **Backend threshold endpoint** — A `GET /screening/thresholds` endpoint serves the canonical thresholds and direction flags. Frontend reads from this rather than maintaining a duplicate TypeScript map. Eliminates cross-language sync burden.
- **Orphaned task recovery on startup** — FastAPI `lifespan` context manager marks all `status in ("pending", "running")` tasks as `"failed"` with message "Server restarted during execution." Safe for single-user app.
- **Concurrent screen guard** — `POST /screening/run` checks for any `TaskStatus` with `task_type="screening"` and `status in ("pending", "running")`. Returns 409 if found. Prevents FMP budget exhaustion from duplicate runs.

---

## Open Questions

### Resolved During Planning

- **How to implement cancel?** DB-flag polling every 10 stocks in the screening loop. See Key Technical Decisions.
- **How to persist progress across navigation?** React Context wrapping the app layout. See Key Technical Decisions.
- **What defines an "exceptional" stock?** Composite score >= 80 initially. Configurable later.
- **How to handle research deduplication?** Query-level DISTINCT ON, preserving history.
- **Cancel during FMP fetch phase (0 results)?** Allowed — marks run as "partial" with 0 results, shows message explaining no stocks were filtered.
- **Cancel race with completion?** If status is already "completed" when cancel arrives, cancel is a no-op — return completed results.
- **Run Screen while another is running?** Blocked — 409 Conflict with message "A screen is already running."
- **Navigation from runs list back to running task?** Store `task_id` on `ScreeningRun` model so the list page can link to `/screening/task-{taskId}` for in-progress runs.

### Resolved by Doc Review

- **Limits UI placement?** Inline expandable "Advanced options" below Run Screen button. Collapsed by default, persists collapse state in localStorage.
- **Delete running run?** Block with 409 "Cancel the run before deleting." Delete and cancel are separate explicit actions.
- **Focus trap approach?** DIY `useFocusTrap` hook (~30 lines). Reused by StockDetailModal and hamburger drawer. No new dependency.
- **Traffic-light threshold source?** Backend serves via `GET /screening/thresholds`. No frontend duplication.
- **TaskContext scope?** Screening tasks only. Research keeps its existing polling; R13 is satisfied by swapping the spinner with ProgressPanel.
- **Metric reconciliation?** Keep existing 22 + add 7 new = 29 total in scorer. Canonical 15 are the authoritative set for /learn page and traffic-light coloring.
- **Cancel DB check?** Use column expression `select(TaskStatus.status)` to bypass SQLAlchemy identity map.
- **FMP rate counter race?** Add `asyncio.Lock` around check-and-increment in `_get()`.
- **Dashboard exceptional stocks query?** Dedicated `GET /screening/highlights` backend endpoint (not frontend multi-hop).
- **Research dedup ordering?** Subquery pattern — inner DISTINCT ON, outer ORDER BY created_at DESC.

### Deferred to Implementation

- Exact FMP endpoints for missing metrics (BETA, Book Value, Debt-to-EBITDA, Dividend Payout, Projected Earnings Growth Rate, Analyst Rating, 12-month trading range) — need to test against FMP stable API during implementation. If an endpoint requires a paid plan, mark the metric as tier-blocked in data_warnings.
- Optimal batch size for FMP parallelization (start with 5 concurrent requests, tune based on rate limit behavior)
- Exact exceptional stock badge/border design — implement a visible gold treatment, refine visually during frontend work
- Exceptional stock threshold validation — after first 3 screening runs, check distribution and adjust 80 if needed
- Mobile nav hamburger menu breakpoint and animation — follow standard Tailwind responsive patterns, left-anchored drawer
- Human-readable label mapping for data_warnings keys (e.g., `key_metrics_ttm` → "Key Metrics (TTM)") — define once in a shared constant, used by both U10 tooltip and U12 coloring

---

## Phased Delivery

### Phase 1: Backend Infrastructure (U1–U4)

Backend changes that the frontend depends on. No UI changes yet.

### Phase 2: Data & Performance (U5–U6)

Missing metrics and FMP improvements. Can overlap with late Phase 1.

### Phase 3: Screening Frontend (U7–U10)

All screening UI improvements. Depends on Phase 1 backend APIs.

### Phase 4: Research & App-Wide Polish (U11–U14)

Research page, skeleton loaders, metrics reference, dashboard, mobile. Depends on Phase 3 shared components.

---

## Implementation Units

### U1. TaskStatus model expansion + orphaned recovery + concurrent guard

**Goal:** Extend TaskStatus to support structured progress data, recover from server restarts, and prevent concurrent screening runs.

**Requirements:** R1, R2, R6

**Dependencies:** None

**Files:**
- Modify: `stock-analyzer/backend/app/models/task.py`
- Modify: `stock-analyzer/backend/app/models/screening.py`
- Create: `stock-analyzer/backend/alembic/versions/XXX_add_progress_data_and_task_id.py`
- Modify: `stock-analyzer/backend/app/main.py`
- Modify: `stock-analyzer/backend/app/api/screening.py`
- Modify: `stock-analyzer/backend/app/schemas/screening.py`

**Approach:**
- Add `progress_data` JSON column to `TaskStatus` (holds `{stage, stocks_examined, matches_found, total_stocks, log_entries: [{timestamp, message}]}`)
- Add `"cancelling"` and `"cancelled"` as valid status values
- Add `task_id` integer column to `ScreeningRun` (nullable FK to `task_status.id`) so the runs list can link back to the progress view for in-progress runs
- Add `"partial"` as valid status for `ScreeningRun`
- Write Alembic migration for both model changes
- Add `on_startup` hook in `main.py` that marks orphaned `status in ("pending", "running")` tasks as `"failed"`
- Add concurrent guard in `start_screening_run`: query for active screening tasks, return 409 if found
- Update `TaskStatusOut` schema to include `progress_data`

**Patterns to follow:**
- Existing `TaskStatus` model structure in `app/models/task.py`
- Existing Alembic migration pattern in `alembic/versions/`
- FastAPI `lifespan` async context manager (current recommended approach: `@asynccontextmanager async def lifespan(app): ... yield ...` passed as `FastAPI(lifespan=lifespan)`)

**Test scenarios:**
- Happy path: TaskStatus created with progress_data JSON, progress_data readable via polling endpoint
- Happy path: ScreeningRun stores task_id, retrievable via runs list query
- Edge case: Startup hook transitions "running" tasks to "failed" with error message
- Edge case: Startup hook is idempotent — running twice doesn't double-fail tasks
- Error path: POST /screening/run returns 409 when a screening task is already pending/running
- Error path: POST /screening/run succeeds when only completed/failed tasks exist

**Verification:**
- Migration runs cleanly against the existing schema
- Polling endpoint returns structured progress_data
- Server restart transitions orphaned tasks to failed
- Cannot start two concurrent screening runs

---

### U2. Cancel support in backend

**Goal:** Enable graceful cancellation of in-progress screening runs with incremental result saving.

**Requirements:** R3

**Dependencies:** U1

**Files:**
- Modify: `stock-analyzer/backend/app/services/screener.py`
- Modify: `stock-analyzer/backend/app/api/screening.py`
- Modify: `stock-analyzer/backend/app/services/fmp_client.py`
- Modify: `stock-analyzer/backend/app/schemas/screening.py`

**Approach:**
- Add `POST /screening/tasks/{task_id}/cancel` endpoint that sets `TaskStatus.status = "cancelling"`
- Modify `run_screening()` loop to check cancellation flag every 10 stocks — use `await db.execute(select(TaskStatus.status).where(TaskStatus.id == task_id))` (column expression, not entity) to bypass SQLAlchemy's identity map and read the current DB value. Entity-level queries return the cached in-session object which never reflects external writes.
- Before entering the stock loop, `await db.commit()` the ScreeningRun (not just flush) so it is visible to other sessions — this is required for incremental commits to make sense and for the results endpoint to find the run mid-screen.
- Change from single batch commit to incremental commits every 10 results (flush + commit partial batch)
- On cancel detection: set `ScreeningRun.status = "partial"`, `TaskStatus.status = "cancelled"`, commit final state
- Add cancellation check in `fetch_and_cache_batch()` too — check between tickers during FMP fetch phase
- Handle race: if cancel arrives after completion, return the completed results (cancel is no-op)

**Patterns to follow:**
- Existing `_update_task()` helper in `screener.py`
- Existing error handling pattern in `_run_screening_task()`

**Test scenarios:**
- Covers AE2. Happy path: Cancel after 15 matches found → run status is "partial", 15 results saved, task status is "cancelled"
- Happy path: Cancel endpoint returns task status immediately (doesn't block)
- Edge case: Cancel during FMP fetch phase (0 matches) → run status "partial", 0 results, task "cancelled"
- Edge case: Cancel when task already completed → no-op, returns completed status
- Edge case: Double cancel request → second request is idempotent
- Error path: Cancel with invalid task_id → 404
- Integration: Incremental saves survive cancel — results committed every 10 stocks are not lost

**Verification:**
- Cancelling a running screen stops processing within ~10 stock iterations
- Partial results are persisted and accessible via the results endpoint
- FMP fetch phase is also cancellable

---

### U3. Configurable limits + run settings display + run management

**Goal:** Add max_examined/max_matches limits, store and display filter settings on runs, and enable run deletion.

**Requirements:** R4, R5, R6, R7

**Dependencies:** U1 (coordinate with U2 on shared file edits to `screener.py` and `screening.py`)

**Files:**
- Modify: `stock-analyzer/backend/app/schemas/screening.py`
- Modify: `stock-analyzer/backend/app/api/screening.py`
- Modify: `stock-analyzer/backend/app/services/screener.py`

**Approach:**
- Add `max_examined` (optional int) and `max_matches` (optional int) to `ScreeningRunRequest` schema
- Pass both limits into `run_screening()`, enforce in the stock loop: count examined stocks and matches, break when either limit reached
- `ScreeningRun.filter_config` already stores the config as JSON — ensure limits are included alongside thresholds
- Add `GET /screening/{run_id}` endpoint returning the full `ScreeningRun` (including `filter_config`) for the results page header
- Add `DELETE /screening/runs/{run_id}` endpoint with application-level cascade (existing FK has no `ondelete='CASCADE'`): first delete `ScreeningResult` rows, then `ScreeningRun`, then associated `TaskStatus`. If the run is currently running, return 409 with message "Cancel the run before deleting."
- Add `GET /screening/highlights?min_score=80&limit=5` endpoint — queries the latest completed/partial run and returns top results above the threshold (used by dashboard U14)
- Update `list_screening_runs` to include `filter_config` in response so the list page can show settings

**Patterns to follow:**
- Existing `ScreeningRunRequest` schema in `app/schemas/screening.py`
- Existing cascade pattern: `ScreeningResult` has FK to `ScreeningRun`

**Test scenarios:**
- Covers AE3. Happy path: max_matches=25, max_examined=500 → screen stops at whichever limit hit first
- Happy path: No limits provided → screen runs through all stocks (backward compatible)
- Happy path: DELETE /screening/runs/{id} removes run + results + task
- Happy path: Run details include filter_config with thresholds and limits
- Edge case: max_matches=0 → immediately stops, "partial" with 0 results
- Edge case: Delete a running run → returns 409 "Cancel the run before deleting"
- Error path: DELETE non-existent run → 404

**Verification:**
- Limits enforce correctly, run stops early when either limit hit
- Deleted runs are fully cleaned up (no orphan results or tasks)
- Filter config is retrievable per run

---

### U4. FMP 402 error tracking + data_warnings field

**Goal:** Record which FMP API calls fail with 402 (free-tier limitation) per stock so the frontend can show targeted warnings.

**Requirements:** R8

**Dependencies:** None (can parallel with U1–U3, but must complete before U5–U6)

**Files:**
- Modify: `stock-analyzer/backend/app/models/stock.py`
- Create: `stock-analyzer/backend/alembic/versions/XXX_add_data_warnings.py`
- Modify: `stock-analyzer/backend/app/services/fmp_client.py`

**Approach:**
- Add `data_warnings` JSON column to `Stock` model (e.g., `{"key_metrics_ttm": 402, "ratios_ttm": 402}`)
- In `fetch_and_cache_ticker()`, catch `httpx.HTTPStatusError` per endpoint (profile, key-metrics-ttm, ratios-ttm) and record the status code in `data_warnings` instead of silently continuing
- Clear `data_warnings` on successful fetch (so stale warnings don't persist after tier upgrade)
- Pass `data_warnings` through to `ScreeningResult.metric_snapshot` so the frontend can distinguish "null because free tier blocked it" from "null because company doesn't report it"

**Patterns to follow:**
- Existing error handling in `fetch_and_cache_batch()` at `fmp_client.py:350-352`
- Existing `map_to_stock()` pattern for building Stock data dicts

**Test scenarios:**
- Covers AE4. Happy path: PG returns 402 on key-metrics-ttm → Stock.data_warnings = {"key_metrics_ttm": 402}, other metrics from profile/ratios still saved
- Happy path: Stock with no 402s → data_warnings is empty/null
- Edge case: Multiple endpoints return 402 for same ticker → all recorded
- Edge case: Previously-blocked ticker succeeds on re-fetch → data_warnings cleared
- Integration: ScreeningResult.metric_snapshot includes data_warnings alongside metric values

**Verification:**
- 402 errors are recorded per-endpoint per-stock
- Frontend can distinguish tier-blocked metrics from genuinely unavailable ones

---

### U5. Missing metrics + Stock model expansion

**Goal:** Add the missing canonical metrics (BETA, Book Value, Debt-to-EBITDA, Dividend Payout, Projected Earnings Growth Rate, Analyst Rating, 12-month trading range) and the website field to the Stock model.

**Requirements:** R10, R21

**Dependencies:** U4

**Files:**
- Modify: `stock-analyzer/backend/app/models/stock.py`
- Create: `stock-analyzer/backend/alembic/versions/XXX_add_missing_metrics.py`
- Modify: `stock-analyzer/backend/app/services/fmp_client.py`
- Modify: `stock-analyzer/backend/app/services/scorer.py`
- Modify: `stock-analyzer/backend/app/services/screener.py`

**Approach:**
- Add columns to Stock: `website`, `beta`, `book_value_per_share`, `debt_to_ebitda`, `dividend_payout`, `projected_earnings_growth`, `analyst_rating`, `trading_range_12m`
- Research FMP stable API during implementation to find which endpoints provide each metric — FMP profile returns `beta` and `website`, other metrics may require `financial-growth`, `analyst-estimates`, or `key-metrics` endpoints
- Update `FMPProfile` Pydantic model to capture `website` and `beta` from profile response
- Add new Pydantic models for any additional FMP endpoints needed
- Update `map_to_stock()` to populate new fields
- Update `CATEGORY_METRICS` and `METRIC_RANGES` in scorer to include new metrics in appropriate categories. **Metric reconciliation:** The existing scorer has 22 metrics across 4 categories (value: pe, peg, pb, ps, price_to_cash, price_to_fcf; growth: 5 eps/sales fields; financial_health: current_ratio, quick_ratio, debt_to_equity, lt_debt_to_equity; profitability: roe, roa, roi, gross/operating/net margin, dividend_yield). The canonical 15 overlaps with 8 of these and adds 7 new ones. **Decision:** Keep all existing metrics in the scorer (no removal — preserves current scoring behavior per scope boundary). Add the 7 new metrics to appropriate categories: BETA → value, Book Value → value, Debt-to-EBITDA → financial_health, Dividend Payout → profitability, Projected Earnings Growth → growth, Analyst Rating → value, 12-month trading range → value. The canonical 15 are the authoritative set for the /learn reference page and traffic-light coloring.
- Update `DEFAULT_THRESHOLDS` and `_metric_label()` in screener for the new metrics
- For metrics unavailable on FMP free tier: record in `data_warnings` and leave as NULL (consistent with existing growth metrics pattern)
- **R21 success criterion reframed:** "Attempt all 15 canonical metrics via FMP stable API. Surface unavailability clearly via `data_warnings`. The scorer handles NULLs gracefully (excluded from category average). If a metric is permanently unavailable on the free tier, it is still defined in `METRIC_RANGES` and `DEFAULT_THRESHOLDS` so it activates automatically if the user upgrades their FMP plan."

**Execution note:** Research FMP endpoints first before writing code — the exact availability of each metric on the free tier determines the implementation. FMP profile likely provides `beta` and `website`. Check `financial-growth`, `analyst-estimates`, and `stock-price-change` endpoints for the rest. If an endpoint requires a paid plan, record that in the plan's Open Questions and mark the metric as tier-blocked.

**Patterns to follow:**
- Existing `map_to_stock()` mapping pattern in `fmp_client.py`
- Existing `METRIC_RANGES` normalization in `scorer.py`
- Existing `DEFAULT_THRESHOLDS` in `screener.py`

**Test scenarios:**
- Happy path: Stock model stores all 15 canonical metrics when available from FMP
- Happy path: Website field populated from FMP profile
- Happy path: Scorer includes new metrics in composite score calculation
- Edge case: New metric unavailable on free tier → stored as NULL, recorded in data_warnings
- Edge case: Existing stocks without new columns → migration adds nullable columns, NULL values handled gracefully by scorer

**Verification:**
- All 15 canonical metrics have corresponding Stock model columns
- Scorer handles the full set (NULLs excluded from category average as before)
- FMP client fetches and maps all available metrics

---

### U6. FMP API parallelization + concurrent request handling

**Goal:** Speed up FMP data fetching by parallelizing requests within rate limits.

**Requirements:** R22

**Dependencies:** U4, U5

**Files:**
- Modify: `stock-analyzer/backend/app/services/fmp_client.py`

**Approach:**
- Replace sequential ticker-by-ticker fetching in `fetch_and_cache_batch()` with concurrent batches using `asyncio.gather()` or `asyncio.Semaphore`
- Use a semaphore to limit concurrency (start with 5 concurrent requests)
- Each ticker still makes 3 sequential requests (profile → key-metrics → ratios) to avoid tripling concurrency
- **Rate counter thread-safety:** Add `self._lock = asyncio.Lock()` to FMPClient. Wrap the check-and-increment in `_get()` inside `async with self._lock:` — the current pattern has a TOCTOU gap where multiple coroutines read the counter, all pass the check, then all increment past the limit. The lock ensures the counter is accurate regardless of concurrency level.
- Add cancellation check between batches (supports cancel during FMP phase)
- **Rate-limit truncation handling:** When the rate limit stops the fetch phase early, record `total_stocks_available` vs `stocks_actually_fetched` in the task's `progress_data`. Mark the run as `"partial"` (not `"completed"`) with a specific reason. The results page header (U10) surfaces this: "Screened X of Y available stocks (FMP rate limit reached)."

**Patterns to follow:**
- Existing `fetch_and_cache_ticker()` for per-ticker logic
- Existing rate limit checking in `_get()`

**Test scenarios:**
- Happy path: Batch of 80 tickers completes faster than sequential (verify with timing)
- Edge case: Rate limit hit mid-batch → remaining tickers skipped, partial results returned
- Edge case: Semaphore correctly limits to N concurrent requests
- Error path: One ticker fails → others continue (existing behavior preserved)

**Verification:**
- FMP fetch phase is measurably faster than current sequential approach
- Rate limit is never exceeded
- All existing tests pass (behavior unchanged, only speed improved)

---

### U7. Global task state (React Context) + layered progress component

**Goal:** Create a React Context that holds screening task polling state across page navigation, and build the reusable layered progress display component.

**Requirements:** R1, R2

**Dependencies:** U1 (backend progress_data API)

**Files:**
- Create: `stock-analyzer/frontend/src/contexts/TaskContext.tsx`
- Create: `stock-analyzer/frontend/src/components/ProgressPanel.tsx`
- Modify: `stock-analyzer/frontend/src/app/layout.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/[runId]/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/page.tsx`

**Approach:**
- `TaskContext` wraps the root layout, holds a map of `taskId → {status, progress_data, taskType}`. **Scoped to screening tasks only** — the research page keeps its existing working polling loop (it already calls `GET /research/active` every 3s); R13 is satisfied by swapping the research page's spinner with the shared `ProgressPanel` component, not by rerouting through TaskContext.
- Context starts polling when a task is registered (via `registerTask(taskId, type)`) and stops when completed/failed/cancelled
- Polling interval: 3s (matches current behavior)
- **Cold-start recovery:** On mount, TaskContext calls `GET /api/screening/tasks?status=running,pending` (list active screening tasks endpoint from U1). If an active task is found, register it and begin polling. If none found, context is idle. During the recovery fetch, subscribers render a brief skeleton. If a task in context is returned as completed by the endpoint, transition immediately rather than waiting for the next poll cycle.
- **Poll-failure resilience:** If a poll request fails (network error), retain last-known progress data and show a subtle "Connection lost, retrying..." indicator. Do not blank the panel. Resume normal display when the next poll succeeds.
- `ProgressPanel` component renders the layered progress: stage name, elapsed time (computed from `created_at` vs now, with "Unknown duration" fallback if `created_at` is unavailable), counts (examined/matched/total), and a scrollable activity log
- Screening list page reads context to show "running" indicator and link to progress view
- `[runId]/page.tsx` subscribes to context instead of managing its own polling

**Patterns to follow:**
- Existing polling pattern in `[runId]/page.tsx` (migrate from local state to context)
- Existing `apiFetch<T>()` utility for API calls

**Test scenarios:**
- Covers AE1. Happy path: Start screen → navigate to Dashboard → return to Screening → progress panel shows current stage, elapsed time, counts
- Happy path: Progress panel updates every 3 seconds with new data
- Happy path: Task completes while on different page → context updates, screening list shows "completed"
- Edge case: Multiple task types (screening + research) tracked simultaneously
- Edge case: Browser tab closed and reopened → context re-initializes, checks for active tasks on mount
- Edge case: Task fails while user is on different page → context updates to failed state

**Verification:**
- Navigating away from a running screen and returning shows live progress
- Progress panel displays stage, elapsed time, stock counts, and activity log
- Context cleanup: completed/failed tasks stop polling

---

### U8. Cancel UI + configurable limits UI

**Goal:** Add the cancel button to the screening progress view and the limit configuration to the "Run Screen" flow.

**Requirements:** R3, R4

**Dependencies:** U2, U3, U7

**Files:**
- Modify: `stock-analyzer/frontend/src/app/screening/[runId]/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/page.tsx`
- Create: `stock-analyzer/frontend/src/app/api/screening/tasks/[taskId]/cancel/route.ts`

**Approach:**
- Add "Cancel Screen" button next to the progress panel, visible only when task is running
- Button calls `POST /api/screening/tasks/{taskId}/cancel` via the Next.js proxy route
- **Cancelling state:** On cancel click, disable the button, show spinner + "Cancelling, saving results..." text. Freeze the activity log (no new entries). Cap the wait at 30s — if status hasn't transitioned to "cancelled" by then, navigate to results regardless (the backend may have completed in the gap). Navigate to results page once status transitions to "cancelled" or "completed".
- **Limits UI (inline expandable):** Below the "Run Screen" button, add a collapsed "Advanced options" disclosure section (▸ toggle). When expanded, show two numeric inputs: "Max stocks to examine" (placeholder: "All") and "Max matches to collect" (placeholder: "Unlimited"). Empty inputs mean no limit. Validation: positive integers only; 0 treated as no limit. Collapsed state persists in localStorage.
- Pass limits in the POST /screening/run request body
- Disable "Run Screen" button when a screen is already running (reads from TaskContext)

**Patterns to follow:**
- Existing `startRun()` in `screening/page.tsx`
- Existing Next.js API route proxy pattern

**Test scenarios:**
- Happy path: Click cancel → button shows "Cancelling..." → navigates to results with partial badge
- Happy path: Set max_matches=30, run screen → screen stops at 30 matches
- Edge case: Cancel button disabled after clicking (prevent double-cancel)
- Edge case: Run Screen button disabled when task is active (from context)
- Edge case: Cancel during FMP fetch phase → results page shows 0 results with explanation

**Verification:**
- Cancel button works during any screening phase
- Limits are passed to the backend and enforced
- Cannot start a second screen while one is running

---

### U9. Shared grid/list view toggle + stock detail modal

**Goal:** Build reusable ViewToggle and StockDetailModal components used by both screening and research pages.

**Requirements:** R9, R15

**Dependencies:** None (pure frontend component work)

**Files:**
- Create: `stock-analyzer/frontend/src/components/ViewToggle.tsx`
- Create: `stock-analyzer/frontend/src/components/StockDetailModal.tsx`
- Create: `stock-analyzer/frontend/src/components/StockListRow.tsx`
- Create: `stock-analyzer/frontend/src/hooks/useFocusTrap.ts`

**Approach:**
- `ViewToggle` — simple two-button toggle (grid/list icons), stores preference in `localStorage` per page key
- `StockListRow` — compact row component showing ticker, company name, composite score, sector, key metrics. Clickable.
- `StockDetailModal` — overlay modal matching the existing card layout: conviction bars, metric values, summary, company name, website link, FMP warning indicator if applicable. Closes on backdrop click or Escape key.
- All components accept generic props so they work for both screening results and research reports
- Modal uses Tailwind for styling — no modal library needed for single-user app
- **Accessibility/focus trap:** Build a small `useFocusTrap(ref)` custom hook (~30 lines) that confines Tab/Shift+Tab within the modal container. Modal must set `role="dialog"` `aria-modal="true"` `aria-labelledby` pointing to the stock name heading. On open, focus moves to the close button. On close (Escape, backdrop click), focus returns to the triggering list row. Same hook reused by U14's mobile hamburger drawer.

**Patterns to follow:**
- Existing card layout in `[runId]/page.tsx` for the modal content
- Existing Tailwind component patterns in `src/components/`

**Test scenarios:**
- Covers AE5. Happy path: Toggle to list view → see compact rows. Click row → modal opens with full card layout.
- Happy path: Toggle to grid view → see existing card layout
- Happy path: View preference persists in localStorage across page loads
- Edge case: Modal on mobile — full-screen or near-full-screen
- Edge case: Escape key closes modal
- Edge case: Empty results → list view shows "No results" message

**Verification:**
- Toggle switches between grid and list views smoothly
- Modal displays complete stock detail
- Preference persists across sessions

---

### U10. Screening results polish (company name, FMP warnings, exceptional highlighting, run settings)

**Goal:** Enhance the screening results page with richer stock identity, free-tier warning indicators, exceptional stock highlighting, and run settings display.

**Requirements:** R5, R8, R10, R11

**Dependencies:** U4, U5, U9

**Files:**
- Modify: `stock-analyzer/frontend/src/app/screening/[runId]/page.tsx`
- Modify: `stock-analyzer/frontend/src/components/StockListRow.tsx`
- Modify: `stock-analyzer/frontend/src/components/StockDetailModal.tsx`
- Modify: `stock-analyzer/frontend/src/app/api/screening/[runId]/route.ts` (add run-details proxy alongside existing results proxy)

**Approach:**
- Display `company_name` alongside ticker on cards and list rows (already in metric_snapshot from backend)
- Display website as a small external link icon next to company name
- **FMP warning indicator:** Amber triangle icon with tooltip listing blocked metrics. Tooltip content: map endpoint keys to human-readable names (e.g., `key_metrics_ttm` → "Key Metrics (TTM)", `ratios_ttm` → "Financial Ratios"). Trigger: visible on hover AND focus (keyboard) AND tap (mobile — toggle on tap, dismiss on tap-outside). Position: above the icon with left-edge clamp to prevent overflow on narrow cards.
- Exceptional stock highlighting: gold border + star badge on cards/rows where `composite_score >= 80`
- Run settings header: fetch `ScreeningRun.filter_config` and display active thresholds and limits at the top of the results page. If the run is "partial" due to rate-limit truncation, show "Screened X of Y available stocks (FMP rate limit reached)" below the header.
- Add proxy route for `GET /api/screening/{runId}` to fetch run details
- **Run deletion UI:** Add a trash icon on each run row in the screening list (visible on hover, always visible on mobile). On click: show confirmation dialog "Delete this run? This cannot be undone." with Cancel/Delete buttons. While deleting: row shows disabled "Deleting..." state. On success: optimistic removal from list. On error: restore row + error toast. Running runs show the trash icon disabled with tooltip "Cancel the run before deleting."

**Patterns to follow:**
- Existing card layout and conviction bars in `[runId]/page.tsx`
- Existing status badge pattern for visual indicators

**Test scenarios:**
- Happy path: Company name appears on all stock cards and list rows
- Happy path: Stock with data_warnings shows amber warning icon with tooltip
- Happy path: Stock with composite_score >= 80 has gold border and star badge
- Happy path: Results page header shows the thresholds and limits used for the run
- Edge case: Stock with no company_name → show ticker only (graceful fallback)
- Edge case: All stocks have data_warnings → warning indicators visible on every card
- Edge case: No exceptional stocks in results → no highlighting applied (no empty section)

**Verification:**
- Company names visible throughout results
- Warning indicators clearly distinguish tier-blocked from unavailable metrics
- Exceptional stocks are visually distinct at a glance
- Run settings are displayed in the results header

---

### U11. Research progress display + filtering/search/dedup

**Goal:** Wire up the existing research backend progress to the frontend (using ProgressPanel from U7), add filtering and search, and handle deduplication.

**Requirements:** R13, R14, R16

**Dependencies:** U7 (ProgressPanel component), U9 (ViewToggle)

**Files:**
- Modify: `stock-analyzer/frontend/src/app/research/page.tsx`
- Modify: `stock-analyzer/backend/app/api/research.py`
- Create: `stock-analyzer/frontend/src/app/api/research/reports/route.ts` (if not exists)

**Approach:**
- Research page keeps its existing polling loop (`GET /research/active` every 3s) — replace the current spinner display with the shared `ProgressPanel` component from U7 to satisfy R13's "layered pattern" requirement. No TaskContext subscription needed.
- Add filter bar: dropdown filters for recommendation (buy/hold/sell), confidence (high/medium/low), sector, date range. Ticker search field with 300ms debounce.
- **Filter state:** Local component state (not URL params — no sharing use case in single-user app). On data refresh (research task completes and new reports arrive), active filters remain applied and the filtered view updates in place. "Show all versions" dedup toggle combines with other filters (AND logic) — it controls whether dedup is applied to the filtered subset.
- Backend: update `GET /research/reports` to support query params: `recommendation`, `confidence`, `sector`, `ticker_search`, `deduplicated` (boolean, default true)
- Dedup: when `deduplicated=true`, backend uses a subquery pattern: inner query applies `DISTINCT ON (stock_ticker) ORDER BY stock_ticker, created_at DESC`, outer query re-orders by `created_at DESC` for the final result set. This preserves most-recent-first display order while deduplicating.
- Add "Show all versions" toggle that sets `deduplicated=false` for users who want to see historical reports
- Add grid/list view toggle using shared `ViewToggle` component

**Patterns to follow:**
- Existing filter bar pattern in screening results (`[runId]/page.tsx`)
- Existing research report list in `research/page.tsx`
- Existing proxy route pattern for Next.js API routes

**Test scenarios:**
- Happy path: Research progress panel shows stages while Claude analysis is running
- Happy path: Filter by recommendation "buy" → only buy reports shown
- Happy path: Search for "AAPL" → only Apple reports shown
- Happy path: Deduplicated view shows one report per ticker (latest)
- Edge case: No research reports → empty state with helpful message
- Edge case: Search returns no results → "No reports match" message
- Edge case: Ticker with multiple reports → dedup shows latest, "Show all versions" shows all

**Verification:**
- Research progress is visible during active research tasks
- All filters work correctly and combine (AND logic)
- Deduplication shows latest report per ticker by default

---

### U12. Traffic-light metric color coding on research sidebar

**Goal:** Color-code metric values on the research report sidebar based on canonical threshold directions.

**Requirements:** R20

**Dependencies:** U5 (canonical metrics defined in scorer)

**Files:**
- Modify: `stock-analyzer/backend/app/api/screening.py` (add thresholds endpoint)
- Create: `stock-analyzer/frontend/src/app/api/screening/thresholds/route.ts` (proxy)
- Modify: `stock-analyzer/frontend/src/app/research/[ticker]/page.tsx`

**Approach:**
- **Single source of truth:** Add `GET /api/screening/thresholds` backend endpoint that serializes `DEFAULT_THRESHOLDS` and `METRIC_RANGES` direction flags as JSON. Frontend fetches this once on page load and caches in module state. Eliminates threshold duplication across Python and TypeScript.
- For each metric in the sidebar: compare value against thresholds and assign green (great — well within threshold), orange (okay — near threshold), red (bad — outside threshold)
- **Mandatory non-color indicator (WCAG 1.4.1):** Each colored metric value must also carry a non-color signal — a small filled circle icon (●) placed before the value, colored with the same green/orange/red class. Plus `aria-label` on the metric value element describing its status (e.g., `aria-label="ROE 25% — good"`). This ensures the sidebar is scannable for color-blind users.
- "Near threshold" defined as within 20% of the threshold boundary
- Metrics without a defined threshold direction → neutral gray (no coloring, no icon)

**Patterns to follow:**
- Existing metric sidebar layout in `research/[ticker]/page.tsx`
- Canonical thresholds served from backend (no frontend duplication)

**Test scenarios:**
- Happy path: ROE of 25% (min threshold 15%) → green
- Happy path: P/E of 19 (max threshold 20) → orange (within 20% of threshold)
- Happy path: Debt-to-Equity of 2.5 (max threshold 1.0) → red
- Edge case: Metric value is null → no color applied, show "N/A"
- Edge case: Metric not in threshold map → neutral gray

**Verification:**
- All metrics with defined thresholds show appropriate colors
- Colors are visually clear and accessible (sufficient contrast)

---

### U13. Skeleton loaders + metrics reference page

**Goal:** Replace all text-based loading states with skeleton loaders and create the educational metrics reference page.

**Requirements:** R17, R19

**Dependencies:** None (can run in parallel with other Phase 4 work)

**Files:**
- Create: `stock-analyzer/frontend/src/components/Skeleton.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/[runId]/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/research/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/research/[ticker]/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/page.tsx` (dashboard)
- Modify: `stock-analyzer/frontend/src/app/settings/page.tsx`
- Create: `stock-analyzer/frontend/src/app/learn/page.tsx`

**Approach:**
- `Skeleton` component: animated pulse placeholder blocks (Tailwind `animate-pulse bg-gray-200 rounded`). Variants: text line, card, list row, metric bar, progress panel (two text lines + two count blocks + three log lines), run settings header (one wide text line).
- Replace every `Loading...` text string across the app with context-appropriate skeleton layouts (e.g., screening list shows skeleton run cards, results show skeleton stock cards)
- Metrics reference page (`/learn`): static content page explaining each of the 15 canonical metrics — what it measures, why the threshold direction matters, how to interpret values. Organized by category (Value, Growth, Financial Health, Profitability). Include examples.
- Add "Learn" link to the navigation bar

**Patterns to follow:**
- Existing loading patterns to replace (search for `Loading` across frontend)
- Tailwind `animate-pulse` for skeleton animations

**Test scenarios:**
- Happy path: Screening list page shows skeleton cards while loading
- Happy path: Results page shows skeleton stock cards while fetching
- Happy path: Research page shows skeleton report rows while loading
- Happy path: Metrics reference page displays all 15 canonical metrics with explanations
- Edge case: Fast load (cached data) → skeleton flashes briefly then content appears (no layout shift)
- Edge case: Learn page is accessible from nav on all pages

**Verification:**
- No text-based "Loading..." strings remain in the app
- Skeleton shapes match the content they replace (no layout shift)
- Metrics reference page is comprehensive and understandable by a layman

---

### U14. Dashboard exceptional stocks + mobile/responsive overhaul

**Goal:** Surface exceptional stocks on the dashboard and make the entire app responsive on mobile.

**Requirements:** R12, R18

**Dependencies:** U10 (exceptional stock definition), U9 (shared components)

**Files:**
- Modify: `stock-analyzer/frontend/src/app/page.tsx` (dashboard)
- Modify: `stock-analyzer/frontend/src/components/NavBar.tsx` (or equivalent nav component)
- Modify: `stock-analyzer/frontend/src/app/screening/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/[runId]/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/research/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/research/[ticker]/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/settings/page.tsx`

**Approach:**
- **Dashboard "Exceptional Stocks" section:** Fetch from `GET /api/screening/highlights?min_score=80&limit=5` (backend endpoint added in U3). Display as compact cards with ticker, company name, score, and link to full results.
  - **State handling:** Query targets the latest run with status "completed" or "partial". If the only run is currently "running", hide the section (don't show stale data from a previous run during an active screen). If no runs exist at all, hide the section entirely. If the latest completed/partial run has results but none meet the threshold, show "No standout stocks in latest screen." The threshold of 80 is a starting assumption — validate after the first 3 screening runs and adjust if the section is always empty or always full.
- Mobile nav: hamburger menu at `md` breakpoint, left-anchored slide-out drawer with nav links. Drawer uses the same `useFocusTrap` hook from U9. Closes on link click, backdrop click, or Escape.
- Responsive passes per page:
  - Screening list: stack run cards full-width on mobile
  - Results: single-column grid on mobile, filter bar wraps/stacks
  - Research list: full-width cards on mobile
  - Research report: sidebar stacks below content on mobile
  - Settings: single-column sector grid on mobile
  - Dashboard: stack sections vertically
- BulkActions bar: add safe-area padding for mobile

**Patterns to follow:**
- Existing `grid-cols-1 md:grid-cols-2` pattern for responsive grids
- Existing `max-w-7xl` container pattern
- Tailwind responsive utilities (`sm:`, `md:`, `lg:`)

**Test scenarios:**
- Happy path: Dashboard shows top 5 exceptional stocks from latest screening run
- Happy path: Mobile nav shows hamburger menu, clicking opens drawer with all links
- Happy path: All pages are usable at 375px width (iPhone SE)
- Edge case: No screening runs → dashboard exceptional section hidden
- Edge case: Latest run has no exceptional stocks → "No standout stocks" message
- Edge case: Nav drawer closes on link click and on backdrop click
- Integration: BulkActions bar doesn't overlap mobile nav or keyboard

**Verification:**
- Dashboard exceptional stocks section populated with real data
- All pages render correctly on mobile viewports
- Navigation is fully functional on mobile

---

## System-Wide Impact

- **Interaction graph:** TaskContext is a new global provider — all pages that show task-related state subscribe to it. Changes to polling frequency or task status shape affect every subscriber.
- **Error propagation:** Cancel endpoint → TaskStatus DB update → screener loop reads on next iteration → partial commit. Failure at any step should leave the system in a recoverable state (task marked failed, partial results committed).
- **State lifecycle risks:** Incremental commits in the screening loop mean partial results exist before the run is "completed." The results endpoint must handle `status in ("running", "partial")` runs gracefully.
- **API surface parity:** New endpoints (cancel, delete, run details) need corresponding Next.js proxy routes. All existing proxy routes continue to work unchanged.
- **Integration coverage:** The cancel flow crosses 4 layers (frontend button → proxy route → backend endpoint → screener loop DB check) and must be tested end-to-end.
- **Unchanged invariants:** The scoring algorithm, conviction calculation, composite score formula, and category weights are NOT changed by this plan. Only the set of input metrics is expanded.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Missing canonical metrics not available on FMP free tier | Record in data_warnings, display as unavailable. R21 reframed as "attempt all 15, surface unavailability clearly." Metric definitions still added to scorer/thresholds so they activate on tier upgrade. |
| Incremental commits in screening loop could leave partial data on crash | Partial data is better than no data (current behavior loses everything). "Partial" status badge makes the state visible. Orphaned task recovery handles the rest. Initial `db.commit()` for ScreeningRun before loop entry ensures run is visible to other sessions. |
| React Context polling across all pages could cause unnecessary re-renders | Context scoped to screening only (research keeps its own polling). Use `useMemo` and selective subscriptions. Only pages showing screening task state re-render on poll updates. |
| FMP parallelization could trigger server-side rate limiting beyond the 250/day counter | `asyncio.Lock` on rate counter prevents TOCTOU race. Start with conservative concurrency (5 requests). If rate limit truncates the universe, mark run as "partial" and surface "Screened X of Y" in results header. |
| Mobile overhaul scope is broad and touches every page | Tackle per-page with Tailwind responsive utilities. Most layouts already have `md:` breakpoints — focus on missing `sm:` and improving existing ones. |
| Exceptional stock threshold (80) may not match actual score distribution | Validate after first 3 runs. If dashboard section is always empty or always full, adjust. Hardcoded initially, configurable in preferences later. |
| SQLAlchemy identity map returns stale cancel flag | Cancel check uses column expression `select(TaskStatus.status)` which bypasses identity map and hits DB directly. |

---

## Sources & References

- **Origin document:** [docs/brainstorms/screening-ux-overhaul-requirements.md](docs/brainstorms/screening-ux-overhaul-requirements.md)
- Related code: `stock-analyzer/backend/app/services/screener.py` (screening loop), `stock-analyzer/backend/app/models/task.py` (TaskStatus), `stock-analyzer/backend/app/services/fmp_client.py` (FMP integration)
- Related code: `stock-analyzer/frontend/src/app/screening/` (screening UI), `stock-analyzer/frontend/src/app/research/` (research UI)
