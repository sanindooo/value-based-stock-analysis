---
date: 2026-05-21
topic: preservation-mode-tiered-analysis
---

# Preservation Mode & Tiered Analysis

## Summary

Add a "Preservation Mode" lens that surfaces a productive-equity score alongside the existing composite score, and introduce a three-tier analysis system (quick, standard, deep) as general infrastructure that both value and preservation lenses consume. Users can run analyses with or without preservation on any stock and access both results independently.

---

## Problem Frame

The stock analyzer currently excels at finding undervalued stocks using Buffett/Graham fundamentals. However, the current global economic climate introduces a concern the system doesn't address: inflation resilience. A stock can be undervalued by traditional metrics but still vulnerable if the underlying business lacks pricing power — the ability to pass rising costs to consumers without losing demand.

A video on inflation-hedging frameworks identifies four pillars: hard money, productive equity, real assets, and personal earning power. Of these, productive equity is the only pillar this tool can meaningfully assess — and it maps directly onto data the system already collects (margins, dividends, volatility, capital efficiency). The gap isn't data collection; it's interpretation. The system scores stocks on value but has no way to ask "will this company hold up in a difficult economic environment?"

Separately, the system currently offers only two analysis depths: screening (quantitative batch) and AI research (qualitative deep-dive). There's no middle tier for "I'm interested but not ready to commit to a full research report." Adding a standard-depth analysis that surfaces trend data and news headlines benefits all users, not just those concerned about inflation.

---

## Actors

- A1. Investor (user): Configures preservation preferences, triggers analyses at various depths, interprets results across both value and preservation lenses
- A2. Screening engine: Computes batch scores (composite and preservation) during screening runs
- A3. Analysis engine: Fetches additional data and produces standard or deep analysis per stock
- A4. AI research agent: Generates qualitative assessments, incorporating preservation context when the lens is active

---

## Key Flows

- F1. Batch screening with preservation
  - **Trigger:** User starts a new screening run with the preservation checkbox enabled
  - **Actors:** A1, A2
  - **Steps:** User configures screening parameters, preservation checkbox defaults from settings but can be overridden, screening runs and computes both composite and preservation scores, results display with both score columns visible
  - **Outcome:** All screened stocks have both composite and preservation scores; sortable by either
  - **Covered by:** R1, R2, R3, R4, R5

- F2. Per-stock standard analysis
  - **Trigger:** User clicks analysis button on a stock card
  - **Actors:** A1, A3
  - **Steps:** User selects standard depth and chooses whether preservation lens is on, system fetches trend data (margin history, dividend growth streak, revenue consistency) and recent news headlines, analysis presented with clear mode indicator
  - **Outcome:** Stock has enriched data beyond the quick score; results stored with mode label
  - **Covered by:** R6, R7, R8, R9, R11, R12

- F3. Per-stock deep analysis
  - **Trigger:** User clicks analysis button and selects deep depth (reserved for top picks)
  - **Actors:** A1, A3, A4
  - **Steps:** User confirms deep analysis (costs API credits), system fetches and reads full news articles, researches broader context (competitive position, industry trends, recent events), AI generates qualitative assessment with or without preservation lens, results stored alongside any prior analyses
  - **Outcome:** Comprehensive research on the stock with full context; both value and preservation perspectives available if requested
  - **Covered by:** R6, R7, R8, R9, R10, R11, R12

- F4. Switching lenses on an already-analysed stock
  - **Trigger:** User wants to see a stock through the other lens after already running an analysis
  - **Actors:** A1, A3
  - **Steps:** User triggers analysis with the alternate lens setting, new analysis runs and is stored separately, both results remain accessible
  - **Outcome:** Stock has analyses from both lenses; user can compare
  - **Covered by:** R11, R12

---

## Requirements

**Preservation Score (Quick Tier)**

- R1. Compute a preservation score (0-100) for each screened stock using existing metrics: gross margin (pricing power proxy), dividend yield, dividend payout ratio (sustainability), beta (stability), ROE/ROA (capital efficiency)
- R2. Display the preservation score as a second column alongside the existing composite score in both grid and list views when preservation mode is active
- R3. Allow sorting by either composite or preservation score
- R4. No stocks are hidden or filtered by preservation mode — it is purely additive

**Settings & Toggle Cascade**

- R5. Settings page has a persistent preservation mode on/off toggle. When on, the batch preservation checkbox on new screening runs defaults to checked. A quick toggle on the screening results page shows/hides the preservation score column per-session. The screening form checkbox can override the settings default per-run.

**Tiered Analysis (General Infrastructure)**

- R6. Three analysis tiers are available for any stock: quick (automatic, from existing data), standard (fetches trend data + news headlines), deep (reads full articles + contextual AI research)
- R7. Standard analysis fetches: margin history over time, dividend growth streak (consecutive years of increases), revenue consistency, and recent Yahoo news headlines
- R8. Deep analysis fetches and reads full news articles, researches competitive position and broader context. Requires explicit user confirmation before running (API credit cost).
- R9. News headlines are a general feature visible on stock detail views regardless of preservation mode

**Preservation as a Lens**

- R10. When preservation mode is active during standard or deep analysis, the analysis additionally evaluates: pricing power durability, dividend sustainability under stress, inflation resilience of the business model, and competitive moat strength
- R11. A user can run analysis with or without preservation mode on the same stock. Both results are stored and accessible — running one does not overwrite the other.
- R12. The UI clearly indicates which mode (value-only or value + preservation) each analysis result was produced under

---

## Acceptance Examples

- AE1. **Covers R2, R4, R5.** Given preservation mode is on in settings, when a screening run completes, all screened stocks display both composite and preservation scores. A stock with composite score 85 but preservation score 40 is still visible — not filtered out.
- AE2. **Covers R5.** Given preservation mode is on in settings, when the user starts a new screening run, the preservation checkbox is pre-checked. The user unchecks it. The run produces only composite scores, no preservation scores.
- AE3. **Covers R11, R12.** Given a stock has a completed standard analysis without preservation, when the user runs standard analysis again with preservation on, both results are stored. The UI shows two analysis entries with clear labels ("Value Analysis" / "Value + Preservation Analysis").
- AE4. **Covers R8.** Given a user clicks deep analysis, a confirmation dialog appears showing that this will consume API credits before the analysis begins.

---

## Success Criteria

- User can identify which of their screened stocks are best positioned for inflationary environments without losing the existing value analysis
- Analysis depth is proportional to conviction — quick glance for all stocks, richer data for interesting ones, full research for top picks
- A downstream planner can implement this without inventing product behavior around mode toggling, analysis triggers, or result storage

---

## Scope Boundaries

- Hard money (gold/silver) tracking or analysis
- Real assets (commodities, property, mortgage) analysis
- Personal earning power assessment
- Portfolio allocation recommendations or rebalancing
- Macroeconomic indicators or inflation rate tracking
- Changes to which stocks pass the initial screening filter
- Specific scraping implementation details (deferred to planning, informed by `syntech-content-sourcing` repo research)

---

## Key Decisions

- **Preservation is a lens, not a pipeline**: Same data collection infrastructure, different interpretation. Avoids building parallel systems.
- **Three-tier analysis is general infrastructure**: Benefits all users regardless of preservation mode. Standard tier fills the gap between screening and full AI research.
- **Results are additive, not replaceable**: Running analysis in one mode doesn't overwrite results from another mode. Users build up layers of insight per stock.
- **MVP preservation score uses existing metrics**: No new data sources needed for the quick tier. Trend data is fetched only at standard/deep tiers when the user explicitly requests it.

---

## Dependencies / Assumptions

- Yahoo Finance API (already integrated) can provide news headlines and historical margin/dividend data
- Existing scraping infrastructure in `syntech-content-sourcing` repo (Apify, SERP API, Zeit HTTP) can be adapted for deep analysis article fetching — research this during planning
- AI research agent prompts can be extended with preservation-specific evaluation criteria without architectural changes

---

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Needs research] What is the optimal weighting formula for the preservation score? Should it be configurable like the existing category weights, or fixed?
- [Affects R7][Needs research] Which Yahoo Finance endpoints provide margin history and dividend growth streak data? Verify availability and rate limits.
- [Affects R8][Needs research] Research `syntech-content-sourcing` repo for scraping patterns, Apify/SERP/Zeit integration, and list-based polling architecture applicable to deep analysis.
- [Affects R10][Technical] How should preservation-specific evaluation criteria be injected into the existing AI research agent prompts?
- [Affects R11][Technical] What is the storage model for multiple analysis results per stock (separate records with mode indicator vs. nested structure)?
