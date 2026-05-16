---
date: 2026-05-15
topic: stock-analysis-pipeline
---

# Stock Analysis Pipeline

## Summary

A personal stock analysis pipeline that screens US stocks using Buffett-style value investing metrics, surfaces candidates with metric summaries and pass/fail reasoning, and lets the user select stocks for deeper AI-powered research using SEC filings and news — all filtered through configurable portfolio preferences.

---

## Problem Frame

Value investing requires comparing dozens of financial metrics across thousands of stocks, then diving deep into qualitative sources (shareholder letters, SEC filings, news) for the shortlisted few. Doing this manually with tools like Finviz and spreadsheets is slow enough that opportunities pass before analysis completes, and the qualitative research step — reading 10-Ks, parsing shareholder letters — is where most individual investors give up entirely.

The user completed a value investing course (NMW) that teaches a Buffett-style screening methodology using fundamental metrics (P/E, PEG, P/B, ROE, debt ratios, margins, EPS growth, dividend yield) and a side-by-side company comparison framework. The knowledge exists but has never been applied to real investment decisions. The gap is not understanding — it's operationalizing the methodology into a repeatable, efficient workflow.

---

## Actors

- A1. Investor (user): Configures portfolio preferences, reviews screened stocks, selects candidates for deep research, makes final investment decisions
- A2. Screening engine: Runs value investing filters against US stock data, scores and ranks candidates
- A3. Research agent: Pulls SEC filings, shareholder letters, and news for selected stocks; generates AI-powered analysis summaries

---

## Key Flows

- F1. Stock screening
  - **Trigger:** User initiates a screen (on-demand or scheduled)
  - **Actors:** A1, A2
  - **Steps:** Screening engine pulls current fundamental data for US stocks; applies value investing metric filters with user-configured thresholds; scores passing stocks against portfolio preferences; surfaces results ranked by composite score
  - **Outcome:** A list of candidate stocks with metric snapshots, pass/fail reasoning per metric, and a quick summary explaining why each stock passed
  - **Covered by:** R1, R2, R3, R4, R5

- F2. Triage and selection
  - **Trigger:** User reviews screened candidates
  - **Actors:** A1
  - **Steps:** User browses candidate list with key metrics visible; reviews quick AI-generated summaries based on the numbers; bulk-selects stocks for deep research or rejects them; rejected stocks are recorded so they don't resurface in the same screening cycle
  - **Outcome:** A shortlist of stocks promoted to the deep research stage
  - **Covered by:** R6, R7, R8

- F3. Deep research
  - **Trigger:** User selects one or more stocks for deep research
  - **Actors:** A1, A3
  - **Steps:** Research agent fetches the latest 10-K, 10-Q, and shareholder letters from SEC EDGAR; pulls recent news coverage; AI analyzes filings and news to produce a structured research report with buy/hold/avoid reasoning; user reads the AI analysis and can access the source documents directly
  - **Outcome:** A research report per stock with AI opinion, key evidence from filings, and links to source documents
  - **Covered by:** R9, R10, R11, R12

- F4. Portfolio preference configuration
  - **Trigger:** User sets up or adjusts their investment profile
  - **Actors:** A1
  - **Steps:** User configures preferred sectors/industries, risk tolerance level, target hold duration, and any metric threshold overrides
  - **Outcome:** Preferences are saved and applied to all future screening and scoring
  - **Covered by:** R13, R14

---

## Requirements

**Screening**
- R1. Screen US stocks (NYSE, NASDAQ, AMEX) using configurable value investing metric filters: P/E, Forward P/E, PEG, P/B, P/S, Price/Cash, Price/Free Cash Flow, EPS growth (this year, next year, past 5 years, next 5 years), ROE, ROA, ROI, current ratio, quick ratio, debt/equity, LT debt/equity, gross margin, operating margin, net profit margin, dividend yield
- R2. Each metric filter has configurable thresholds (min/max) with sensible defaults based on the NMW course methodology
- R3. Score passing stocks with a composite value score that weights metrics according to portfolio preferences
- R4. Display screened stocks with: ticker, company name, sector/industry, key metrics that caused it to pass, composite score, and a brief AI-generated summary explaining the valuation case (e.g., "Low P/E of 8.3 vs sector average of 18, strong ROE at 22%, minimal debt")
- R5. When a stock passes screening, show how far above/below threshold each metric is, so the user can see conviction strength

**Triage**
- R6. Present screened stocks in a browsable list/card view with sorting and filtering by any displayed metric
- R7. Support bulk selection: user can check multiple stocks and promote them to deep research or reject them in one action
- R8. Rejected stocks are marked and excluded from the current screening results (but can be un-rejected)

**Deep research**
- R9. For selected stocks, fetch the most recent annual report (10-K), latest quarterly report (10-Q), and any available shareholder/CEO letters from SEC EDGAR
- R10. Pull recent news articles about the company (last 3-6 months)
- R11. Generate a structured AI research report that includes: company overview, competitive position, financial health assessment, growth trajectory, key risks, and a buy/hold/avoid opinion with explicit reasoning tied to evidence from the filings
- R12. Provide direct links/access to source documents so the user can verify the AI's analysis

**Portfolio preferences**
- R13. User can configure and save: preferred sectors/industries (multi-select), risk tolerance (conservative/moderate/aggressive), target hold duration, and custom metric threshold overrides
- R14. Portfolio preferences influence screening scores — stocks in preferred sectors and matching the risk profile rank higher, but stocks outside preferences can still appear if their fundamentals are strong enough

**Infrastructure**
- R15. Next.js frontend with React, Python backend, hosted on Railway
- R16. PostgreSQL database (Railway's built-in Postgres service, same private network as the app services) for storing screening results, research reports, portfolio preferences, and rejection history
- R17. Minimize costs: use free-tier data APIs (Financial Modeling Prep, yfinance, SEC EDGAR) where possible; the primary paid cost is AI API tokens for the research analysis layer
- R18. Set up a database GUI tool (e.g., TablePlus or pgAdmin) for browsing and inspecting the PostgreSQL data during development and operation

---

## Acceptance Examples

- AE1. **Covers R4, R5.** Given a stock with P/E of 10 (threshold: < 20) and ROE of 25% (threshold: > 15%), when screening completes, the stock card shows "P/E: 10 (50% below threshold)" and "ROE: 25% (67% above threshold)" alongside the quick summary.
- AE2. **Covers R7, R8.** Given 15 screened stocks, when the user selects 5 and clicks "Research these," those 5 move to the deep research stage; when the user selects 3 others and clicks "Reject," those 3 are grayed out and excluded from the current view but remain accessible via an "include rejected" toggle.
- AE3. **Covers R14.** Given a user with "Technology" and "Healthcare" as preferred sectors, when two stocks score equally on fundamentals but one is in Technology and the other in Energy, the Technology stock ranks higher — but the Energy stock still appears in results.
- AE4. **Covers R9, R11, R12.** Given a stock selected for deep research, when the research completes, the report shows a "Sources" section with clickable links to the actual 10-K and 10-Q filings on SEC EDGAR, and the AI's claims reference specific sections of those filings.

---

## Success Criteria

- The user can go from "screen the market" to "here are my top 5 candidates with research reports" in under 30 minutes of active time
- Screened stocks surface genuinely undervalued companies that would have been found manually using the NMW course spreadsheet — the system automates, not reinvents, the methodology
- The AI research reports provide enough substance that the user feels informed enough to make investment decisions without separately reading full 10-K filings
- The system runs affordably: data API costs are $0 (free tiers), and AI token costs stay reasonable for analyzing 5-10 stocks per screening session

---

## Scope Boundaries

### Deferred for later

- Backtesting engine: run historical stocks through the pipeline and analyze what patterns preceded strong performers — using shareholder letters, metric trajectories, and news events to train the system on historical data
- Historical pattern recognition: identify leading indicators from backdated data that predict future stock performance
- Scheduled/automated screening runs (cron-based re-screening)
- Email or push notification alerts when new stocks pass screening
- Comparison view: side-by-side comparison of two or more stocks (replicating the Chapter 11 spreadsheet digitally)
- Watchlist functionality for stocks that are close to passing but not quite there yet

### Outside this product's identity

- Automated trading or order execution — this is a research and decision-support tool, not a trading bot
- Portfolio tracking of actual holdings, P&L, or performance — use a dedicated portfolio tracker for that
- Technical analysis signals (moving averages, RSI, chart patterns, candlestick patterns) — the system is fundamentals-only, aligned with the Buffett value investing philosophy
- Mobile app
- Multi-user or SaaS features — this is a personal tool

---

## Key Decisions

- **Pipeline model over dashboard model:** The system is structured as a stage-gated pipeline (Screen → Triage → Research → Decide) rather than a single dashboard showing everything at once. This matches how value investing works in practice — you narrow progressively.
- **AI research is on-demand, not automatic:** Deep research runs only on stocks the user explicitly selects, keeping AI token costs controlled and ensuring the user is intentional about what they analyze.
- **Railway Postgres over Neon or SQLite:** Railway's built-in PostgreSQL runs on the same private network as the app services, eliminating external network latency. Neon's serverless advantages (scale-to-zero, branching) aren't needed for a single-user tool already running on Railway.
- **Free data APIs as the default:** Financial Modeling Prep (free tier, 250 req/day) as the primary fundamental data source, SEC EDGAR (free, no key) for filings, yfinance as a fallback. The only paid API is Claude for the AI analysis layer.
- **Configurable thresholds with course defaults:** Screening metric thresholds ship with sensible defaults from the NMW course but are fully user-configurable, since different market conditions and risk profiles warrant different cutoffs.

---

## Dependencies / Assumptions

- Financial Modeling Prep's free tier (250 requests/day) is sufficient for screening US stocks — may need to cache aggressively or batch requests
- SEC EDGAR API provides reliable access to 10-K, 10-Q filings and shareholder letters in a parseable format
- Claude API can produce useful investment analysis from SEC filing text within reasonable token budgets
- Railway's free/starter tier can host both a Next.js frontend and Python backend
- Railway's PostgreSQL add-on is included in the Railway plan at minimal additional cost

---

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Needs research] What are the exact default threshold values for each metric from the NMW course? The Chapter 11 Numbers spreadsheet likely contains these but needs to be opened in Numbers.app to extract
- [Affects R3][Technical] How should the composite value score weight different metrics? Equal weighting vs risk-adjusted weighting vs user-configurable weights
- [Affects R9][Needs research] How reliably can shareholder/CEO letters be extracted from SEC EDGAR filings programmatically? They're often embedded in the 10-K rather than filed separately
- [Affects R10][Technical] Which free news API provides the best coverage for stock-specific news? Finnhub free tier vs alternatives
- [Affects R15][Technical] Best approach for Python backend + Next.js frontend communication on Railway — REST API vs tRPC vs something else
- [Affects R17][Needs research] Estimated Claude API token cost per deep research report — depends on filing sizes and prompt strategy
