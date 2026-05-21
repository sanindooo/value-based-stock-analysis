---
title: "feat: Add Preservation Mode & Tiered Analysis"
type: feat
status: active
date: 2026-05-21
origin: docs/brainstorms/preservation-mode-requirements.md
---

# feat: Add Preservation Mode & Tiered Analysis

## Summary

Extends the existing scoring, screening, and preferences infrastructure with a preservation score lens (inflation resilience), adds three-tier analysis depth (quick/standard/deep), and adapts article extraction patterns from the syntech-content-sourcing repo for deep analysis. Standard-tier uses yfinance for trend data and existing Finnhub integration for news headlines. Deep-tier adds SerpApi for article URL discovery (when Finnhub/yfinance lack sufficient context) + trafilatura/readability extraction + Zyte anti-bot fallback.

---

## Problem Frame

The stock analyzer scores stocks on value fundamentals but has no way to assess inflation resilience — whether a company can maintain margins and dividends in a difficult economic environment. The metrics to answer this question (gross margin, dividend yield, beta, ROE/ROA) are already collected; the gap is interpretation. Separately, there's no middle tier between batch screening and full AI research — users need a "standard" depth for stocks they're interested in but not ready to commit API credits on. (see origin: `docs/brainstorms/preservation-mode-requirements.md`)

---

## Requirements

- R1. Compute a preservation score (0-100) for each screened stock using existing metrics: gross margin, dividend yield, dividend payout ratio, beta, ROE, ROA
- R2. Display preservation score alongside composite score in grid and list views when preservation mode is active
- R3. Allow sorting by either composite or preservation score
- R4. No stocks hidden or filtered by preservation mode — purely additive
- R5. Settings page toggle cascades: persistent toggle → screening form checkbox default → per-session column toggle
- R6. Three analysis tiers: quick (from screening data), standard (trend data + headlines), deep (articles + AI research)
- R7. Standard analysis fetches: (1) trend data — margin history, dividend growth streak, revenue consistency; (2) recent news headlines via existing Finnhub integration
- R8. Deep analysis fetches and reads full news articles, researches competitive position and broader context; requires user confirmation (API credit cost)
- R9. News headlines are a general feature visible on stock detail regardless of preservation mode
- R10. When preservation mode is active during analysis, additionally evaluates: pricing power durability, dividend sustainability under stress, inflation resilience, competitive moat strength
- R11. All analysis runs are append-only — each run creates a new historical record. Cross-mode runs (value vs. preservation) are stored separately per the origin. Same-mode re-runs also append, creating a timestamped history accessible via a date-based dropdown in the UI
- R12. UI clearly indicates which mode each analysis result was produced under

**Origin actors:** A1 (Investor/user), A2 (Screening engine), A3 (Analysis engine), A4 (AI research agent)
**Origin flows:** F1 (Batch screening with preservation), F2 (Per-stock standard analysis), F3 (Per-stock deep analysis), F4 (Switching lenses on already-analysed stock)
**Origin acceptance examples:** AE1 (covers R2, R4, R5), AE2 (covers R5), AE3 (covers R11, R12), AE4 (covers R8)

---

## Scope Boundaries

- Hard money, real assets, personal earning power assessment
- Portfolio allocation or rebalancing recommendations
- Macroeconomic indicators or inflation rate tracking
- Changes to which stocks pass the initial screening filter
- Apify social media scraping actors (LinkedIn/Instagram/X — not relevant for stock news)

### Deferred to Follow-Up Work

- Configurable preservation category weights: existing weight infrastructure makes this easy to add later; fixed defaults for this iteration
- Tavily as supplementary news discovery source: SerpApi covers the primary use case; Tavily can be added as a second leg in a follow-up
- Queue-based extraction architecture: syntech's Postgres work queue is overkill for per-stock inline analysis; can revisit if analysis volume grows

---

## Context & Research

### Relevant Code and Patterns

- `stock-analyzer/backend/app/services/scorer.py` — 4-category weighted scoring with `CATEGORY_METRICS`, `METRIC_RANGES`, `normalize_metric()`, `score_category()`, `compute_composite_score()`. Preservation scorer follows this exact pattern
- `stock-analyzer/backend/app/services/screener.py` — `run_screening()` computes composite scores per stock, writes `ScreeningResult` rows, supports cancellation and progress tracking via `TaskStatus`
- `stock-analyzer/backend/app/services/research_agent.py` — Claude structured-output pipeline: SEC filing + news → system prompt with JSON schema → Claude → `ResearchReport`. System prompt and schema are the extension points for preservation lens
- `stock-analyzer/backend/app/services/news_client.py` — Finnhub news via `asyncio.to_thread()` wrapping sync client. Pattern to follow for new sync API calls
- `stock-analyzer/backend/app/services/yahoo_client.py` — yfinance integration with semaphore-controlled batch concurrency, 24h staleness cache, `asyncio.to_thread()` for sync calls. Historical endpoints (`.financials`, `.dividends`) available for trend data
- `stock-analyzer/backend/app/models/preference.py` — Single-row `PortfolioPreference` with JSON columns for weights and overrides
- `stock-analyzer/frontend/src/components/stock-card.tsx`, `StockListRow.tsx` — Grid/list views with `scoreColor()` helper
- `stock-analyzer/frontend/src/app/settings/page.tsx` — Settings form with radio buttons, sliders, expandable sections
- `stock-analyzer/frontend/src/contexts/TaskContext.tsx` — Global polling (3s) for active tasks with auto-stop on completion

### Institutional Learnings

- **Cache invalidation (HIGH priority):** Background tasks mutate DB without triggering `revalidateTag()`. All new endpoints serving background-task data MUST implement `?poll=1` bypass pattern and aggressive `revalidateTag()` during polling. (see `docs/solutions/ui-bugs/research-status-cache-invalidation-2026-05-17.md`)
- **External API client architecture:** Staleness cache pattern (check DB → fetch on miss → upsert), semaphore-controlled concurrency, `data_warnings` for graceful degradation on per-stock failures. (see `docs/solutions/architecture-patterns/external-api-client-architecture-2026-05-17.md`)
- **Background task lifecycle:** `TaskStatus` model with `pending → running → completed|failed|cancelled` flow, cooperative cancellation, `progress_data` JSON for stage reporting. (see `docs/solutions/architecture-patterns/background-task-lifecycle-management-2026-05-17.md`)
- **AI research structured output:** JSON schema in system prompt with `cache_control: {"type": "ephemeral"}` for prompt caching. Schema extension is the right approach for preservation criteria. (see `docs/solutions/design-patterns/ai-research-pipeline-structured-output-2026-05-17.md`)
- **Tag-based cache revalidation:** Tag naming convention (`resource-name` for lists, `resource-${id}` for entities), revalidation windows (5min lists, 1hr data), `force-dynamic` for polling routes. (see `docs/solutions/architecture-patterns/nextjs-tag-based-cache-revalidation-2026-05-17.md`)

### Syntech-Content-Sourcing Patterns (for Deep Analysis)

The repo at `/Users/sanindo/syntech-content-sourcing` provides battle-tested article fetching and extraction:

- **SerpApi Google News** (`app/handlers/google.py`): `GET https://serpapi.com/search` with `engine=google_news`, time filtering via `tbs` param, keyword variant fan-out, URL + title + snippet + date extraction
- **Three-tier extraction cascade** (`app/extraction.py`): trafilatura (primary, `bare_extraction()` with `favor_precision=True`) → readability-lxml (fallback) → BeautifulSoup heuristic (last resort). Minimum 100 chars to accept
- **Direct HTTP fetch** with rotating browser-like UA headers, `Sec-Fetch-*` headers, Google Referer spoofing for news URLs, streaming response with 10MB content limit
- **Zyte anti-bot fallback** (`app/scraping_api.py`): `POST https://api.zyte.com/v1/extract` with HTTP Basic auth, Base64-encoded response body. Triggered on 403/429 or high Unicode replacement char density
- **Content cleaning**: markdown artifact removal, whitespace normalization, 1MB cap for ReDoS protection
- **Date extraction**: meta tags, JSON-LD, `<time>` tags, URL patterns, relative dates
- **Summary generation**: sentence-boundary truncation within 500 chars

These will be adapted as inline library code in the stock analyzer backend, not as a service dependency.

---

## Key Technical Decisions

- **Preservation score uses 4 fixed-weight categories with existing metrics**: pricing_power (gross_margin), income_resilience (dividend_yield, dividend_payout), stability (beta — inverted), capital_efficiency (roe, roa). Equal weights (25/25/25/25). No new data collection needed. Follows the exact `normalize → average → weight → scale` pattern of `compute_composite_score()`. Note: income_resilience deliberately averages opposite-polarity metrics — higher yield (good) + lower payout (sustainable) = more resilient income. Both are independently normalized before averaging.
- **Storage: hybrid model across tiers**: Quick tier → `preservation_score` Float column on `screening_results`. Standard tier → new `stock_analysis` table with `tier`, `mode`, `analysis_data` JSON. Deep tier → `mode` String column added to `research_reports`. This separates concerns (screening scores vs. trend data vs. full research) while keeping each tier's data co-located with its existing model. Query pattern for "all analyses for a stock": query `stock_analysis` (standard tier) and `research_reports` (deep tier) by ticker, return unified in the API response.
- **Append-only analysis history**: Every analysis run appends a new row — never upserts. The UI shows a date-based dropdown to select historical results per ticker/tier/mode combination. This applies to both cross-mode (R11) and same-mode re-runs.
- **Standard-tier news from Finnhub; SerpApi reserved for deep analysis**: Standard analysis uses the existing `news_client.py` Finnhub integration for recent headlines (already integrated, no new API key). Deep analysis uses SerpApi for article URL discovery when Finnhub/yfinance lack sufficient context for full article extraction. This avoids introducing a paid dependency for the lightweight standard tier.
- **Article extraction adapted as library code**: Functions from syntech-content-sourcing (`fetch_html`, `extract_article`, `validate_content`, `clean_content`) adapted into a new `article_extractor.py` service. All syntech-specific imports (app.models, app.config, app.dedup) replaced with stock-analyzer equivalents. No queue, no work table — inline execution per stock is sufficient for the 5-15 articles fetched per deep analysis.
- **Two AI system prompt variants**: Value-only prompt (existing) and value+preservation prompt (extends schema with preservation fields). Both benefit from separate prompt caching via `cache_control: {"type": "ephemeral"}`.
- **Standard analysis as a background task**: Uses existing `TaskStatus` model with new `task_type: "standard_analysis"`. Follows the same polling, progress tracking, and cancellation patterns as screening. Reusing existing background task infrastructure is lower total effort than a synchronous endpoint (which would need a navigation guard to prevent data loss during fetch).
- **Access control**: New analysis endpoints use the same access control mechanism as existing endpoints (single-user tool with `site_secret` authentication). No additional auth layer needed.
- **Concurrent analysis guard**: Before creating a new analysis task, check for an active (pending/running) task for the same ticker+tier+mode. Reject with 409 Conflict if one exists.

---

## Open Questions

### Resolved During Planning

- **Preservation score weighting formula [R1]:** 4 categories with equal weights (25 each), using 6 existing metrics mapped to preservation-relevant categories. Fixed weights for MVP; configurable weights deferred since the infrastructure already exists in preferences.
- **Yahoo Finance endpoints for trend data [R7]:** `yfinance.Ticker.financials` for income statement history (gross margin over time), `yfinance.Ticker.dividends` for dividend payment history (growth streak computation), revenue from financials (consistency via std dev of growth). All sync calls wrapped in `asyncio.to_thread()`.
- **Standard-tier news source [R7]:** Use existing Finnhub integration (`news_client.py`) for standard-tier headlines. SerpApi reserved for deep-tier article URL discovery where Finnhub/yfinance lack sufficient context for full article extraction.
- **syntech-content-sourcing repo patterns [R8]:** Repo found at `/Users/sanindo/syntech-content-sourcing`. Key patterns: SerpApi for news discovery, trafilatura+readability cascade for extraction, Zyte for anti-bot fallback. Adapted as inline library code with all syntech-specific imports replaced.
- **AI prompt extension [R10]:** Conditional schema extension — when mode is "preservation", system prompt includes additional evaluation fields (pricing_power_durability, dividend_sustainability_under_stress, inflation_resilience_assessment, competitive_moat_strength). Two separately cached prompt variants.
- **Storage model for multiple analyses [R11]:** Hybrid approach — `preservation_score` on screening_results for quick tier, new `stock_analysis` table for standard tier, `mode` on research_reports for deep tier. All analysis runs are append-only with date-based history dropdown in the UI.
- **Standard analysis sync vs async:** Background task — reuses existing TaskStatus/TaskContext infrastructure, lower total effort than synchronous (which would need a navigation guard), consistent UX pattern with deep analysis.
- **Same-mode re-run behavior [R11]:** Always append new row. Full historical record accessible via date-based dropdown. No upsert — every run creates a new entry.

### Deferred to Implementation

- Exact SerpApi result limits and time window for deep analysis article discovery — tune based on result quality during development
- Zyte API key provisioning — may need a separate key or budget allocation for the stock analyzer vs. syntech-content-sourcing. Store as Railway secret env var
- Optimal article count per deep analysis — start with top 10 most recent, adjust based on Claude prompt length constraints

---

## Implementation Units

### U1. Database Schema + Backend Model/Schema Updates

**Goal:** Create the foundation — all table changes, model updates, and schema updates needed by subsequent units.

**Requirements:** R1, R5, R11

**Dependencies:** None

**Files:**
- Create: `stock-analyzer/backend/alembic/versions/d4e5f6a7b8c9_add_preservation_and_analysis.py`
- Modify: `stock-analyzer/backend/app/models/screening.py`
- Modify: `stock-analyzer/backend/app/models/preference.py`
- Modify: `stock-analyzer/backend/app/models/research.py`
- Create: `stock-analyzer/backend/app/models/analysis.py`
- Modify: `stock-analyzer/backend/app/models/__init__.py`
- Modify: `stock-analyzer/backend/app/schemas/screening.py`
- Modify: `stock-analyzer/backend/app/schemas/preferences.py`
- Modify: `stock-analyzer/backend/app/schemas/research.py`
- Create: `stock-analyzer/backend/app/schemas/analysis.py`

**Approach:**
- Add `preservation_score` (Float, nullable) to `screening_results` table
- Add `preservation_enabled` (Boolean, default false) to `portfolio_preferences` table
- Add `mode` (String(20), default "value") to `research_reports` table
- Create `stock_analysis` table: `id` (PK), `stock_ticker` (String(10), FK → stocks.ticker — matching `screening_results` FK pattern), `screening_run_id` (FK → screening_runs, nullable), `tier` (String: "standard"/"deep"), `mode` (String: "value"/"preservation"), `analysis_data` (JSON), `created_at` (DateTime). Allows multiple rows per ticker/tier/mode (append-only history)
- Single Alembic migration for all changes. For `research_reports.mode`: add column with `server_default='value'` and run `UPDATE research_reports SET mode='value' WHERE mode IS NULL` to backfill existing rows
- Update Pydantic schemas to expose new fields: `ScreeningResultOut.preservation_score`, `PreferencesResponse.preservation_enabled`, `PreferencesUpdate.preservation_enabled` (must be `bool | None = None`, not `bool = False`, to work with the existing `exclude_none=True` setattr loop in the preferences PUT handler), new `StockAnalysisOut` schema

**Patterns to follow:**
- Existing model patterns in `stock-analyzer/backend/app/models/screening.py` for column definitions
- Existing schema patterns in `stock-analyzer/backend/app/schemas/screening.py` for Pydantic `model_config = {"from_attributes": True}`
- Migration naming convention from `stock-analyzer/backend/alembic/versions/`

**Test scenarios:**
- Happy path: Migration applies cleanly on fresh DB and on existing DB with data
- Happy path: New `preservation_score` field appears as null in `ScreeningResultOut` for existing results
- Happy path: `PreferencesUpdate` accepts `preservation_enabled: true` and persists it
- Edge case: `stock_analysis` table allows multiple rows per stock_ticker with different tier/mode combinations
- Edge case: `research_reports.mode` defaults to "value" for existing rows (migration backfill)

**Verification:**
- Migration runs without error against the dev database
- All existing tests pass without modification (new fields are nullable/have defaults)
- New Pydantic schemas serialize correctly with `from_attributes`

---

### U2. Preservation Score Computation + Screening Integration

**Goal:** Compute preservation scores during screening runs and store them alongside composite scores.

**Requirements:** R1, R4

**Dependencies:** U1

**Files:**
- Modify: `stock-analyzer/backend/app/services/scorer.py`
- Modify: `stock-analyzer/backend/app/services/screener.py`
- Modify: `stock-analyzer/backend/app/api/screening.py`
- Test: `stock-analyzer/backend/tests/test_scorer.py`
- Test: `stock-analyzer/backend/tests/test_screener.py`

**Approach:**
- Define `PRESERVATION_METRICS` mapping in `scorer.py` with 4 categories: `pricing_power` → [gross_margin], `income_resilience` → [dividend_yield, dividend_payout], `stability` → [beta], `capital_efficiency` → [roe, roa]
- Note: `dividend_payout` and `beta` are "lower is better" metrics (already correctly configured in `METRIC_RANGES`) — for preservation, lower payout = more sustainable, lower beta = more stable. The existing normalization handles the inversion via `higher_is_better: False`. The `income_resilience` category deliberately averages `dividend_yield` (higher=better, normalized 0→1) with `dividend_payout` (lower=better, normalized 0→1 inverted). Higher yield + lower payout = more resilient income. Both metrics are independently normalized before averaging, so opposite polarity is handled correctly
- Create `compute_preservation_score()` following the same `normalize → average → weight → scale` pattern. Fixed equal weights (25/25/25/25). No sector bonus
- In `run_screening()`, accept `preservation_enabled` from preferences. When true, compute preservation score for each stock alongside composite score. Store in `ScreeningResult.preservation_score`
- Handle missing metrics gracefully — if a stock lacks all metrics for a category, that category contributes nothing (same as composite score behavior)
- Pass `preservation_enabled` through from the screening API endpoint's `filter_config` or preferences

**Patterns to follow:**
- `compute_composite_score()` in `scorer.py` for the scoring pattern
- `run_screening()` score computation loop for integration pattern
- `data_warnings` pattern for graceful degradation on missing metrics

**Test scenarios:**
- Happy path: Stock with all 6 preservation metrics gets a score 0-100
- Happy path: Preservation score computed alongside composite in screening pipeline when enabled
- Happy path: Preservation score is null when preservation_enabled is false
- Covers AE1: All screened stocks display preservation scores when preservation mode is on
- Edge case: Stock missing all metrics for one category still gets a score from remaining 3 categories
- Edge case: Stock missing ALL preservation metrics gets 0 score (not null — R4 says no filtering)
- Edge case: High gross margin + low beta + moderate dividends → high preservation score (validates formula direction)
- Edge case: Low gross margin + high beta + no dividends → low preservation score
- Error path: `preservation_enabled` absent from preferences defaults to false, no preservation score computed

**Verification:**
- `test_scorer.py` passes with new preservation scoring tests
- `test_screener.py` passes with preservation integration tests
- Screening run with preservation enabled stores non-null preservation_score values

---

### U3. Settings Toggle Cascade + Screening Results Preservation UI

**Goal:** Add preservation mode toggle to settings, cascade to screening form, and display preservation scores in screening results with per-session visibility toggle and sort option.

**Requirements:** R2, R3, R4, R5

**Dependencies:** U1

**Files:**
- Modify: `stock-analyzer/backend/app/api/preferences.py`
- Modify: `stock-analyzer/backend/app/api/screening.py`
- Modify: `stock-analyzer/frontend/src/app/settings/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/page.tsx`
- Modify: `stock-analyzer/frontend/src/app/screening/[runId]/page.tsx`
- Modify: `stock-analyzer/frontend/src/components/stock-card.tsx`
- Modify: `stock-analyzer/frontend/src/components/StockListRow.tsx`
- Modify: `stock-analyzer/frontend/src/app/api/screening/route.ts`

**Approach:**
- Backend: preferences API already handles `PUT /api/preferences` → update model → invalidate `preferences` tag. Add `preservation_enabled` to the accepted fields. No new endpoints needed
- Backend: update `sort_by` Query parameter pattern constraint from `^(composite_score|stock_ticker)$` to `^(composite_score|preservation_score|stock_ticker)$` to prevent ORM injection when adding the new sort option
- Settings UI: add a new "Preservation Mode" section with a pill toggle (on/off), matching the existing section structure. Label: "Enable Preservation Mode" with brief description of what it does. Toast feedback on save
- Screening form: when starting a new run, checkbox for preservation (defaults from settings `preservation_enabled` but overridable per-run). On preferences load failure, checkbox defaults to unchecked. Pass through in `filter_config` or as a separate field
- Screening results page: add per-session toggle in the same toolbar row as the sort dropdown and grid/list view toggle. Use a checkbox or pill toggle labeled "Show Preservation". Default: show when preservation scores exist in the run data
- Stock card (grid): show preservation score as a smaller secondary badge (e.g., `h-8 w-8` with "P" superscript label) stacked below the composite score badge. Uses same `scoreColor()` helper. Conditionally visible based on session toggle
- Stock list row: add preservation score column immediately after the composite score column, using the same `scoreColor()` helper
- Sort dropdown: add "Preservation Score" option
- Per R4: preservation mode never hides stocks; column toggles visibility, not data

**Patterns to follow:**
- Settings page section structure and toast feedback pattern
- `scoreColor()` helper for consistent score coloring
- Existing sort dropdown and `sort_by` query param handling
- `localStorage` pattern from `ViewToggle` for any persistence needs

**Test scenarios:**
- Covers AE1: Screening run with preservation on → all stocks show both scores; stock with composite 85 / preservation 40 is visible
- Covers AE2: Settings has preservation on → new screening form shows pre-checked checkbox → user unchecks → run produces only composite scores
- Happy path: Settings toggle persists across page reloads (stored in DB preferences)
- Happy path: Per-session column toggle hides/shows preservation column without page reload
- Happy path: Sorting by preservation score reorders results correctly
- Edge case: Screening run from before preservation feature has null preservation scores → column hidden, no errors
- Edge case: Per-session toggle state resets on page navigation (React state, not persisted)
- Edge case: Preferences load failure → preservation checkbox defaults to unchecked, no errors

**Verification:**
- Settings page shows preservation toggle, saves successfully with toast
- New screening run with preservation enabled shows both score columns
- Sort by preservation score works in both grid and list views
- Old screening runs display without errors (null preservation scores handled gracefully)

---

### U4. Standard Analysis Service + API + Frontend

**Goal:** Build the standard-tier analysis: fetch trend data (margin history, dividend growth streak, revenue consistency) and recent news headlines via existing integrations, store results, and display in the stock detail view with analysis history.

**Requirements:** R6, R7, R9, R11

**Dependencies:** U1

**Files:**
- Create: `stock-analyzer/backend/app/services/trend_analyzer.py`
- Create: `stock-analyzer/backend/app/api/analysis.py`
- Modify: `stock-analyzer/backend/app/main.py` (register analysis router: `app.include_router(analysis_router, prefix="/api")`)
- Create: `stock-analyzer/frontend/src/app/api/analysis/route.ts` (proxy for `POST /api/analysis/standard/{ticker}`)
- Create: `stock-analyzer/frontend/src/app/api/analysis/[ticker]/route.ts` (proxy for `GET /api/analysis/{ticker}`)
- Modify: `stock-analyzer/frontend/src/components/StockDetailModal.tsx`
- Modify: `stock-analyzer/frontend/src/contexts/TaskContext.tsx`
- Test: `stock-analyzer/backend/tests/test_trend_analyzer.py`

**Approach:**

*Trend data service (`trend_analyzer.py`):*
- Fetch historical income statements via `yfinance.Ticker.financials` (annual) to compute gross margin over available years
- Fetch dividend history via `yfinance.Ticker.dividends` to compute consecutive years of dividend increases (growth streak)
- Compute revenue consistency: standard deviation of year-over-year revenue growth rates
- All sync yfinance calls wrapped in `asyncio.to_thread()` following `yahoo_client.py` pattern
- Return structured dict: `{ margin_history: [...], dividend_growth_streak: int, revenue_consistency: float, years_of_data: int }`

*News headlines (existing Finnhub integration):*
- Reuse `news_client.py` (`fetch_news()`) for standard-tier headlines — already integrated, no new API key
- Per R9: news headlines are a general feature, not preservation-specific
- SerpApi is reserved for deep-tier article discovery (U5) where Finnhub headlines lack sufficient context

*API endpoints:*
- `POST /api/analysis/standard/{ticker}` — triggers standard analysis as background task. Before creating, check for active (pending/running) task for same ticker+tier+mode; reject with 409 Conflict if one exists (concurrent analysis guard)
- `GET /api/analysis/{ticker}` — retrieves all analyses for a stock (standard + deep, all modes, all historical runs), ordered by `created_at` descending
- Background task: fetch trend data + Finnhub headlines → store in `stock_analysis` table with `tier="standard"`, `mode` from request. Each run appends a new row (never upserts)
- Task type: `"standard_analysis"` in TaskStatus

*Frontend:*
- Next.js API routes proxying to backend via `backendFetch()` with tag-based caching
- Cache tag: `analysis-${ticker}`, revalidated on new analysis completion
- Polling endpoint for task status uses `force-dynamic` (no cache) — follows poll-bypass pattern from cache invalidation learning
- Stock detail modal: two side-by-side buttons for tier selection: "Standard Analysis" / "Deep Analysis". Both disabled while an analysis task is active for this stock. Loading indicator below buttons shows task stage (e.g., "Fetching trends...", "Fetching news...", "Storing results..."). Deep analysis button triggers confirmation dialog (see U5)
- Analysis results section: show most recent result by default. Date-based dropdown to access historical runs (grouped by tier+mode). Each result displays: margin history trend, dividend growth streak, revenue consistency indicator, and news headlines as a compact list (linked title opening in new tab, source + date, truncated snippet)

**Patterns to follow:**
- `news_client.py` for Finnhub headlines integration and sync-to-async wrapping
- `research_agent.py` for background task + TaskStatus integration
- `backendFetch()` + tag-based caching for frontend API routes
- Poll-bypass pattern (`?poll=1` → `cache: "no-store"`) for task status polling

**Test scenarios:**
- Happy path: Standard analysis for stock with available yfinance history returns margin history + dividend streak + revenue consistency
- Happy path: Finnhub returns news headlines for a well-known company (e.g., AAPL)
- Happy path: Analysis results stored in `stock_analysis` with correct tier/mode, retrievable via GET
- Happy path: Task progress updates visible during analysis (fetching_trends → fetching_news → complete)
- Happy path: Multiple runs for same stock appear in history dropdown, most recent shown by default
- Edge case: Stock with no dividend history → dividend_growth_streak = 0, no error
- Edge case: Stock with only 1 year of financials → margin_history has single entry, revenue_consistency is null
- Edge case: Finnhub returns empty results for obscure stock → analysis completes with empty headlines, no failure
- Edge case: Concurrent analysis request for same ticker+tier+mode → 409 Conflict returned
- Error path: yfinance timeout → analysis stores partial results with data_warnings, does not fail entirely
- Error path: Finnhub API key missing → news section skipped with warning, trend data still stored
- Integration: Background task completion triggers cache invalidation on `analysis-${ticker}` tag

**Verification:**
- Standard analysis produces trend data and Finnhub news for a real stock
- Results appear in stock detail modal with formatted trend display and news headlines
- Task polling shows progress and completion without stale cache issues
- Multiple standard analyses per stock stored independently and accessible via history dropdown
- Concurrent request guard works (409 on duplicate)

---

### U5. Deep Analysis Article Extraction + Expanded Research Pipeline

**Goal:** Enhance deep analysis to fetch and read full news articles (beyond Finnhub headlines), using SerpApi for article URL discovery and adapting the article extraction pipeline from syntech-content-sourcing. Extend the AI research agent prompt to include article content.

**Requirements:** R6, R8

**Dependencies:** U1, U4

**Files:**
- Create: `stock-analyzer/backend/app/services/article_extractor.py`
- Create: `stock-analyzer/backend/app/services/news_discovery.py`
- Modify: `stock-analyzer/backend/app/services/research_agent.py` (owns user prompt construction — adds article content section)
- Modify: `stock-analyzer/backend/app/core/config.py` (add `serpapi_api_key: str = ""`, `zyte_api_key: str = ""`, `zyte_max_articles_per_analysis: int = 5`)
- Modify: `stock-analyzer/backend/requirements.txt`
- Test: `stock-analyzer/backend/tests/test_article_extractor.py`
- Test: `stock-analyzer/backend/tests/test_research_agent.py`

**Approach:**

*News discovery service (`news_discovery.py`):*
- SerpApi for article URL discovery, used only in deep analysis (not standard tier)
- Adapted from syntech-content-sourcing's `app/handlers/google.py` — simplified: hardcoded keyword variants (company name, "{ticker} stock", "{company_name} earnings"), no dedup layer, no persistent state, no db_pool
- Call SerpApi `google_news` engine: `GET https://serpapi.com/search?engine=google_news&q=...`. Note: SerpApi requires the API key as a `?api_key=` query parameter (their API design, not configurable). This means the key appears in plaintext in httpx debug logs — ensure httpx logging level suppresses query params in production config
- Parse results for URL, title, snippet, publication date (prefer `iso_date` field)
- Return list of article URL objects: `{ title, url, source, published_date, snippet }`

*Article extractor (`article_extractor.py`):*
- Adapted from syntech-content-sourcing's `app/extraction.py`. All syntech-specific imports (`app.models`, `app.config`, `app.dedup`) replaced with stock-analyzer equivalents (config from `app.core.config`, no dedup module, no work queue)
- `is_safe_url(url)`: SSRF protection — block private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`, `::1`, `fc00::/7`) and non-HTTP schemes before any HTTP request. Ported from syntech's validation pattern and per execution script standards
- `fetch_html(url)`: HTTP GET via httpx with rotating browser UA headers, streaming response, 10MB content limit. On 403/429 or garbled content (high Unicode replacement char density), fall back to Zyte
- `extract_article(html, url)`: Three-tier cascade — trafilatura (`bare_extraction()` with `favor_precision=True`) → readability-lxml → BeautifulSoup heuristic. Minimum 100 chars to accept
- `clean_content(text)`: Remove markdown artifacts, normalize whitespace, 1MB cap
- `fetch_and_extract(url)`: Combined pipeline returning `{ title, content, summary, publication_date }`
- Zyte fallback: `POST https://api.zyte.com/v1/extract` with HTTP Basic auth. Budget cap per analysis run via `ZYTE_MAX_ARTICLES_PER_ANALYSIS` env var (default 5). Zyte key stored as Railway secret env var, never in source or committed `.env`
- New dependencies: `trafilatura>=2.0,<3.0`, `readability-lxml>=0.8`

*Research agent enhancement:*
- After existing Finnhub news fetch, use `news_discovery.py` (SerpApi) to find article URLs for deeper context
- For each URL: validate with `is_safe_url()`, then call `fetch_and_extract()` to get full article content
- Cap at top 10 articles to keep Claude prompt within context limits
- Article content sanitization before prompt injection: wrap each article in clear `<article>` delimiter tokens, strip known injection patterns (e.g., "ignore previous instructions"), cap per-article content at 5000 chars
- Include article content in the user prompt under a new `## Recent News Articles` section, each with title, source, date, and truncated content
- Existing pipeline flow preserved: SEC filing + Finnhub headlines + full articles → Claude → ResearchReport

*AE4 confirmation dialog:*
- Headline: "Run Deep Analysis?"
- Body: "This will fetch and read full news articles, research competitive position, and generate an AI-powered research report. This consumes API credits (Claude AI + article fetching)."
- Buttons: "Run Deep Analysis" (primary) / "Cancel" (secondary)
- Store `mode` on the `ResearchReport` when created

**Patterns to follow:**
- `app/extraction.py` from syntech-content-sourcing for the three-tier extraction cascade
- `app/scraping_api.py` from syntech-content-sourcing for Zyte fallback pattern
- `app/handlers/google.py` from syntech-content-sourcing for SerpApi result parsing
- `_build_user_prompt()` in `research_agent.py` for prompt section structure
- `asyncio.to_thread()` for sync library calls
- `_semaphore` pattern for limiting concurrent external calls

**Test scenarios:**
- Happy path: Article extractor fetches and extracts content from a standard news URL (trafilatura path)
- Happy path: Research agent includes full article content in Claude prompt when articles are available
- Happy path: SSRF validation blocks `http://127.0.0.1/...` and `http://10.0.0.1/...` URLs
- Covers AE4: Deep analysis trigger shows confirmation dialog with headline, cost warning, and Run/Cancel buttons
- Edge case: URL returns 403 → Zyte fallback triggered, article extracted successfully
- Edge case: Article with < 100 chars after extraction → trafilatura fails, readability fallback tried
- Edge case: All 3 extraction tiers fail → article skipped with warning, analysis continues with remaining articles
- Edge case: More than 10 articles found → only top 10 most recent included in prompt
- Edge case: Zyte budget cap reached (5 articles) → remaining 403/429 URLs skipped
- Error path: Zyte API key not configured → fallback disabled, 403/429 URLs skipped with warning
- Error path: SerpApi returns no results → analysis proceeds with Finnhub news only (graceful degradation)
- Error path: Total article content exceeds prompt limit → articles truncated, Claude still receives within-limit prompt

**Verification:**
- Deep analysis for a real stock includes full article content in the research report
- Article extraction handles common news sites (Reuters, Bloomberg, Yahoo Finance)
- Research report quality improves with article context vs. headlines-only
- Zyte fallback works for at least one known paywall/anti-bot site
- SSRF protection blocks private network URLs

---

### U6. Preservation Lens in Analysis + Mode Indicators + Lens Switching

**Goal:** When preservation mode is active during standard or deep analysis, add preservation-specific evaluation. Store mode on all analysis results and display clear mode indicators. Enable lens switching (F4).

**Requirements:** R10, R11, R12

**Dependencies:** U1, U2, U3, U4, U5

**Note:** Both U5 and U6 modify `research_agent.py`. U5 owns user prompt construction (adding article content section). U6 owns system prompt variant selection (adding PRESERVATION_SYSTEM_PROMPT). U5 must be fully merged before U6 begins to avoid conflicts in the prompt logic.

**Files:**
- Modify: `stock-analyzer/backend/app/services/research_agent.py` (owns system prompt variant selection)
- Modify: `stock-analyzer/backend/app/api/analysis.py`
- Modify: `stock-analyzer/frontend/src/components/StockDetailModal.tsx`
- Modify: `stock-analyzer/frontend/src/components/research-report.tsx`
- Modify: `stock-analyzer/frontend/src/app/api/analysis/[ticker]/route.ts`
- Test: `stock-analyzer/backend/tests/test_research_agent.py`

**Approach:**

*AI prompt preservation extension:*
- Create a second system prompt variant (`PRESERVATION_SYSTEM_PROMPT`) extending the existing JSON schema with: `pricing_power_durability`, `dividend_sustainability_under_stress`, `inflation_resilience_assessment`, `competitive_moat_strength`
- Both prompts use `cache_control: {"type": "ephemeral"}` for separate prompt caching
- In `research_agent.py`, select prompt variant based on `mode` parameter
- Preservation user prompt additionally includes: preservation score context, relevant metrics highlighted with preservation framing

*Standard analysis preservation:*
- When mode is "preservation", standard analysis results include additional interpretation: margin trend direction (pricing power signal), dividend streak reliability, revenue volatility (business model resilience)
- Stored in `stock_analysis.analysis_data` with preservation-specific fields alongside general trend data

*Mode on all results:*
- Standard analysis: `mode` field in `stock_analysis` table (already in U1)
- Deep analysis: `mode` field on `research_reports` (already in U1)
- API returns mode with each result; frontend displays it

*UI mode indicators:*
- Each analysis result card shows a mode badge in the top-right corner: "Value" (default, neutral color) or "Value + Preservation" (distinct accent color, e.g., green-tinted)
- Consistent badge styling across standard and deep analysis views — same component used everywhere
- Covers AE3: both results accessible, clearly labeled

*Lens switching (F4):*
- Below the analysis results section in the stock detail modal, show a lens switch button: "Run with Preservation Lens" or "Run Value-Only" (label adapts based on current mode of the most recent analysis)
- Button disabled while an analysis task is active for this stock
- When a stock has analyses in both modes, all are listed in the history dropdown with mode badges
- Running analysis in one mode does not affect or overwrite the other (R11). Same-mode re-runs also append (consistent with append-only model)

**Patterns to follow:**
- `SYSTEM_PROMPT` in `research_agent.py` for prompt structure
- Existing badge components for mode indicators
- `research-report.tsx` component for rendering deep analysis results

**Test scenarios:**
- Covers AE3: Stock with standard analysis (value-only), then standard analysis (preservation) → both stored separately, both visible with distinct labels in history dropdown
- Happy path: Deep analysis with preservation mode produces report with preservation fields populated
- Happy path: Mode badge displays correctly for "Value" and "Value + Preservation"
- Happy path: Lens switch button triggers new analysis with alternate mode, preserving original
- Happy path: Re-running same-mode analysis appends new row, both visible in history
- Edge case: Stock with only value analysis → no preservation result shown, lens switch button available
- Edge case: Stock with only preservation analysis → no value result shown, lens switch button available
- Integration: Switching lens (F4) creates a new background task, polling updates status, completion shows both results in history

**Verification:**
- Deep analysis with preservation produces additional preservation fields in report
- Both value and preservation analysis results visible for the same stock
- Mode badges distinguish results clearly with consistent styling
- Lens switching works from stock detail view
- History dropdown correctly groups results by date and mode

---

## System-Wide Impact

- **Interaction graph:** Settings (`preservation_enabled`) → screening form (default checkbox) → screener (computes preservation score) → screening results UI (displays column). Analysis trigger → background task → trend data (yfinance) + headlines (Finnhub for standard, SerpApi for deep) → optional article extraction (deep only) → optional Claude call (deep only) → stock_analysis/research_reports → stock detail UI with history dropdown. Cache invalidation tags: `preferences`, `screening-run-${id}`, `analysis-${ticker}`, `research-reports`
- **Error propagation:** Background task failures should update TaskStatus to `"failed"` with error_message, revert any in-progress stage markers. Per-stock failures in batch operations (missing metrics, failed article extraction) should warn but not fail the entire analysis. Follow `data_warnings` pattern
- **State lifecycle risks:** Standard/deep analysis tasks must implement stage rollback on failure (learning from research-status bug). Polling endpoints must bypass Next.js cache (`?poll=1` → `cache: "no-store"`). New cache tags must be invalidated on analysis completion
- **API surface parity:** New analysis endpoints follow existing REST pattern (POST to trigger, GET to retrieve) with same `site_secret` access control. Frontend API routes proxy to backend via `backendFetch()`. Sort parameter extended for preservation score with updated pattern constraint
- **Concurrent analysis guard:** POST endpoints check for active (pending/running) task for same ticker+tier+mode before creating a new task. Reject with 409 Conflict. This prevents duplicate work and race conditions
- **Integration coverage:** Cache invalidation during background task completion (the known gap). Settings change propagation to screening form defaults. History dropdown correctly displays all runs
- **Unchanged invariants:** Existing composite scoring and screening pipeline behavior is unaffected when preservation is disabled. Research reports for existing stocks continue to work. No changes to ticker universe discovery or data collection pipeline

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| yfinance historical endpoints may not return consistent data across all stocks | Graceful degradation — compute what's available, flag gaps in `data_warnings`. Test with diverse ticker sample |
| SerpApi rate limits or quota during analysis runs | Per-analysis budget cap, exponential backoff on 429. SerpApi has generous limits (~100 req/s) but track usage |
| Zyte API costs for anti-bot fallback | Budget cap per analysis run (default 5 articles via Zyte). Skip Zyte fallback for non-critical articles |
| trafilatura/readability extraction quality varies across news sites | Three-tier cascade handles most sites. Content validation rejects garbled output. Log extraction method for quality monitoring |
| Cache invalidation gap for new background tasks | Apply proven `?poll=1` bypass pattern from day one — this is the highest-risk known pattern from institutional learnings |
| Two system prompt variants increase Claude API costs | Prompt caching (`cache_control: ephemeral`) mitigates — each variant caches independently. Standard analysis does not use Claude, limiting cost to deep tier only |

---

## Documentation / Operational Notes

- New environment variables needed (both deep-analysis-only, added in U5):
  - `SERPAPI_API_KEY` — for deep analysis article URL discovery. Standard tier uses existing Finnhub, so this is only needed if deep analysis is used
  - `ZYTE_API_KEY` (optional) — anti-bot fallback for article extraction. Deep analysis degrades gracefully without it (403/429 URLs skipped)
  - `ZYTE_MAX_ARTICLES_PER_ANALYSIS` (default: 5) — budget cap on Zyte fallback calls per analysis run
- All API keys stored as Railway secret env vars for deployment, never in source or committed `.env`
- Add new Python dependencies to `stock-analyzer/backend/requirements.txt`: `trafilatura>=2.0,<3.0`, `readability-lxml>=0.8`
- Docker image rebuild required for new dependencies

---

## Sources & References

- **Origin document:** [docs/brainstorms/preservation-mode-requirements.md](docs/brainstorms/preservation-mode-requirements.md)
- **Syntech content sourcing patterns:** `syntech-content-sourcing` — article extraction, SerpApi integration, Zyte fallback (adapted for deep analysis only)
- **Solution docs:** `docs/solutions/ui-bugs/research-status-cache-invalidation-2026-05-17.md` (cache invalidation), `docs/solutions/architecture-patterns/external-api-client-architecture-2026-05-17.md` (API client patterns), `docs/solutions/design-patterns/ai-research-pipeline-structured-output-2026-05-17.md` (Claude structured output)
- Related code: `stock-analyzer/backend/app/services/scorer.py`, `stock-analyzer/backend/app/services/screener.py`, `stock-analyzer/backend/app/services/research_agent.py`
