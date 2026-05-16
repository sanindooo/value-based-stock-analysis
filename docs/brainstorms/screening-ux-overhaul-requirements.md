---
date: 2026-05-16
topic: screening-ux-overhaul
---

# Screening & Research UX Overhaul

## Summary

A broad UX and reliability pass across the stock analyzer: make screening resilient to navigation and cancellation, surface granular progress for both screening and research pipelines, improve the results experience with view modes and richer stock identity, add run management and research filtering, batch API calls for performance, and bring the whole app up to polish standards with skeleton loaders, mobile responsiveness, and educational content.

---

## Problem Frame

The screening pipeline works end-to-end but the experience around it is fragile. Navigating away from a running screen loses all progress visibility with no way back. Failed runs accumulate in the database with no way to see or clear them. The results page shows only tickers — no company names, no way to switch to a compact view, no visual signal for standout stocks. The research reports page has no filtering or search, and duplicate entries are already appearing at small scale.

Progress feedback during both screening and research is minimal — a stage label and spinner, despite the backend already tracking granular stages. The user can't cancel a long-running screen, can't control how many results to find, and can't see which settings produced a given run's results. Free-tier API limitations silently drop stocks without any indication of data loss.

These gaps compound: the tool produces useful output but doesn't yet feel reliable or navigable enough for regular use.

---

## Key Flows

- F1. Run and monitor a screen
  - **Trigger:** User clicks "Run Screen" with configured settings
  - **Steps:** Screen starts in background → user sees layered progress (stage, counts, elapsed time, activity log) → user can navigate away and return without losing progress → user can cancel at any point, saving partial results → screen completes or is cancelled → results display with run settings visible
  - **Outcome:** User has a result set they trust, with full context on how it was produced
  - **Covered by:** R1, R2, R3, R4, R5, R8

- F2. Browse and triage results
  - **Trigger:** User views a completed (or partial) screening run
  - **Steps:** User toggles between grid and list view → sees full company names and optional website → spots exceptional stocks via visual highlighting → clicks a list row to open detail modal → filters, sorts, and triages stocks
  - **Outcome:** User can efficiently scan results and identify stocks worth researching
  - **Covered by:** R9, R10, R11, R12

- F3. Browse and search research reports
  - **Trigger:** User navigates to Research page
  - **Steps:** User searches by ticker → filters by recommendation, confidence, sector, or date → toggles grid/list view → clicks into a report
  - **Outcome:** User can find any research report quickly as the collection grows
  - **Covered by:** R14, R15

---

## Requirements

**Screening resilience**
- R1. Screening progress persists across page navigation — the user can leave the screening page and return to find the running screen with current progress intact.
- R2. Layered progress display during screening: current stage name, elapsed time, throughput counts (stocks examined, matches found so far), and a scrollable activity log showing individual stock processing.
- R3. Cancel button during screening that gracefully stops the process, saves all results found so far, and navigates to the results page as if the run completed normally.
- R4. Two configurable limits before starting a screen: maximum stocks to examine (controls runtime) and maximum matches to collect (controls result volume). Screen stops when either limit is hit.
- R5. Each completed run displays the filter settings/thresholds that produced it, so users can correlate good results with specific configurations.

**Run management**
- R6. The screening list page shows all runs regardless of status, with clear status badges: completed, failed, partial (from cancellation), and running.
- R7. Users can delete any run from the list, clearing it from the database.

**Results experience**
- R8. Stocks that hit FMP free-tier limitations (402 errors) are still stored but display a warning indicator showing which metrics are missing due to tier restrictions.
- R9. Grid/list view toggle on screening results. Grid shows the current card layout; list shows a compact row per stock. Clicking a list row opens a detail modal with the full card-style view (conviction bars, metrics, summary).
- R10. Stock cards and list rows show the full company name alongside the ticker. Optionally show the company website link.
- R11. Exceptional stocks — those with high composite scores or strong conviction across multiple metrics — are visually highlighted in results.
- R12. Exceptional stocks are surfaced on the dashboard as a highlight section.

**Research page improvements**
- R13. Research pipeline progress is displayed on the frontend using the existing backend progress stages and polling endpoint, following the same layered pattern as screening (stage, elapsed time, activity log).
- R14. Research reports page includes filtering by recommendation type, confidence level, sector, and date, plus a ticker search field.
- R15. Research reports page has the same grid/list view toggle as screening results, with a detail modal for list view.
- R16. Duplicate research reports for the same ticker are deduplicated or clearly distinguished.

**App-wide polish**
- R17. All loading states across the app use skeleton loaders instead of text-based loading indicators.
- R18. Mobile/responsive layout overhaul across all pages.
- R19. A dedicated metrics reference page explaining what each screening metric measures, why the threshold direction matters for value investing, and how to interpret the results. Aimed at new users or laymen.

**Research report polish**
- R20. Research report metric sidebar uses traffic-light color coding: green (great — well within threshold), orange (okay — near threshold), red (bad — outside threshold), based on the canonical metric directions. Makes ratio quality instantly scannable without cross-referencing thresholds.

**Metric completeness**
- R21. The screener must evaluate all 15 canonical metrics: PE (last 12 months), Projected Earnings Growth Rate, PEG Ratio, BETA, Book Value (p/share), Current Ratio, Debt-to-EBITDA ratio (ttm), Dividend Payout, Dividend Yield, Profit Margin, ROA (ttm), ROE (ttm), Debt to Equity, Analyst Rating, and 12-month trading range. Each metric has a preferred direction (lower/higher/below 1.0/low). Audit during planning to identify which are currently missing and which FMP endpoints supply them.

**Performance**
- R22. External API calls are batched where providers support it. FMP does not offer batch endpoints — manual parallelization within rate limits, to be researched during planning.

---

## Acceptance Examples

- AE1. **Covers R1.** Given a screening run is in progress and the user navigates to the Dashboard page, when they return to the Screening page, they see the running screen with current progress (stage, elapsed time, counts).
- AE2. **Covers R3, R6.** Given a screening run has found 15 matches after 2 minutes and the user clicks Cancel, the run saves those 15 results and navigates to the results page showing them. The screening list shows this run with a "partial" badge.
- AE3. **Covers R4.** Given the user sets "max matches" to 25 and "max stocks to examine" to 500, the screen stops as soon as either 25 matches are found or 500 stocks have been examined, whichever comes first.
- AE4. **Covers R8.** Given PG returns a 402 on key-metrics-ttm, the stock still appears in results with a warning icon and tooltip indicating which metrics could not be retrieved due to free-tier limitations.
- AE5. **Covers R9.** Given the user is viewing screening results in list view and clicks on a row for AAPL, a modal opens showing the full card layout with conviction bars, metric values, and summary text.

---

## Success Criteria

- A user can start a screen, navigate away, return, and see live progress without losing state.
- A user can cancel a long-running screen and immediately work with partial results.
- A user can identify the best stocks at a glance via visual highlighting without reading every card.
- A user new to value investing can understand what each metric means and why it matters by reading the reference page.
- Research reports remain navigable and searchable as the collection grows past dozens of entries.
- The app feels responsive and polished on both desktop and mobile, with skeleton loaders replacing all loading text.

---

## Scope Boundaries

- No WebSocket/SSE — polling is sufficient and already in place
- No backend task system rearchitecture (no Celery/Redis) — FastAPI BackgroundTasks is working; the issues are frontend-side
- No changes to the scoring algorithm or conviction logic
- Research pipeline feature changes deferred to a separate brainstorm after the research arm has been evaluated

---

## Key Decisions

- Cancel saves partial results as a normal result set (not discarded, not specially flagged beyond the "partial" status badge) — rationale: the user wants to work with what's been found, not start over.
- Progress uses layered verbosity (stage + time → counts → activity log) rather than a single indicator — rationale: the user wants maximum visibility into what the system is doing.
- Grid/list toggle is a shared pattern across both screening results and research reports — rationale: consistency and scalability as both collections grow.
- Metrics reference is a dedicated page rather than inline tooltips — rationale: needs enough depth for a layman to learn from, not just quick reminders.

---

## Dependencies / Assumptions

- FMP API rate limits and available endpoints need research during planning to determine the best parallelization strategy.
- The backend already emits granular research progress stages and has a polling endpoint — the research progress feature is frontend-only.
- The "exceptional stock" threshold (what qualifies as exceptional) will be defined during planning based on current scoring distribution.
- Company name and website data availability depends on what FMP or other providers return — may need an additional data source.

---

## Outstanding Questions

### Deferred to Planning

- [Affects R21][Needs research] Which of the 15 canonical metrics are currently implemented in the screener, and which FMP endpoints supply the missing ones (BETA, Book Value, Debt-to-EBITDA, Dividend Payout, Projected Earnings Growth Rate, Analyst Rating, 12-month trading range)?
- [Affects R22][Needs research] What are FMP's exact rate limits, and what parallelization strategy stays safely within them?
- [Affects R11, R12][Technical] What composite score threshold or metric pattern defines an "exceptional" stock? Needs analysis of current scoring distribution.
- [Affects R10][Needs research] Does the current data pipeline already store company name and website, or does this require additional API calls?
- [Affects R16][Technical] Are duplicate research reports a data model issue (same ticker researched multiple times) or a display bug? Determines whether deduplication is backend or frontend.
