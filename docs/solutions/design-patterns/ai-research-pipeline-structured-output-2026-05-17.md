---
title: AI Research Pipeline with Structured Output
date: 2026-05-17
category: design-patterns
module: backend/research-agent
problem_type: design_pattern
component: service_object
severity: medium
applies_when:
  - Using Claude API to produce structured data (not free-form text)
  - Pipeline combines multiple data sources before sending to LLM
  - Multiple concurrent AI tasks need throttling
  - Results must be stored persistently and linked to other entities
tags:
  - claude-api
  - structured-output
  - research-pipeline
  - anthropic-sdk
  - semaphore
  - sec-edgar
  - prompt-engineering
related_components:
  - background_job
  - database
---

# AI Research Pipeline with Structured Output

## Context

The stock analysis app generates investment research reports by orchestrating multiple data sources (SEC EDGAR filings, Finnhub news) and feeding them to Claude for structured analysis. Each report is a JSON object with defined sections (company overview, competitive position, financial health, etc.) plus an investment opinion with verdict/confidence/reasoning.

The challenge: Claude must produce valid JSON matching a strict schema, multiple reports can run concurrently (but need throttling), and the pipeline must report progress at each stage while handling failures gracefully.

## Guidance

### Pipeline Architecture

```
Data Gathering (parallel)          Analysis           Storage
┌─────────────┐
│ SEC EDGAR   │──┐
└─────────────┘  │     ┌──────────────┐     ┌─────────────┐
                 ├────▶│ Claude API   │────▶│ Postgres    │
┌─────────────┐  │     │ (structured) │     │ (JSON col)  │
│ Finnhub News│──┘     └──────────────┘     └─────────────┘
└─────────────┘
```

### Structured JSON Output via System Prompt

Force Claude to respond with valid JSON by putting the schema in the system prompt with explicit "respond ONLY with the JSON object" instructions:

```python
SYSTEM_PROMPT = """You are a senior financial analyst producing structured investment research reports.

You MUST respond with valid JSON matching this exact schema:

{
  "company_overview": "2-3 paragraph overview...",
  "competitive_position": "Analysis of competitive advantages...",
  "financial_health": "Assessment of balance sheet strength...",
  "growth_trajectory": "Evaluation of revenue/earnings growth...",
  "key_risks": "Top 3-5 material risks...",
  "investment_opinion": {
    "verdict": "buy | hold | avoid",
    "confidence": "high | medium | low",
    "reasoning": "2-3 sentence summary..."
  }
}

Guidelines:
- Be specific and data-driven. Reference actual numbers from the filings.
- Distinguish between facts (from filings) and interpretations (your analysis).
- The verdict should reflect a value investing perspective.
- Respond ONLY with the JSON object, no markdown code fences or extra text."""
```

### Defensive JSON Parsing

Claude sometimes wraps JSON in markdown code fences despite instructions. Strip them before parsing:

```python
def _call_claude_sync(user_prompt: str) -> dict:
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines).strip()

    return json.loads(raw_text)
```

### Prompt Caching for Repeated System Prompts

The system prompt is identical across all research calls. Use Anthropic's prompt caching (`cache_control: {"type": "ephemeral"}`) to avoid re-processing it on every request:

```python
system=[{
    "type": "text",
    "text": SYSTEM_PROMPT,
    "cache_control": {"type": "ephemeral"},
}],
```

This reduces latency and cost when multiple research tasks run in sequence.

### Semaphore-Limited Concurrency

A module-level semaphore limits concurrent research tasks to 3, preventing external API overload:

```python
_semaphore = asyncio.Semaphore(3)

async def run_research_for_ticker(db, ticker, task_id):
    async with _semaphore:
        # Step 1: Fetch SEC filing
        filing_data = await fetch_filing_sections(ticker)
        # Step 2: Fetch news
        news_articles = await fetch_news(ticker)
        # Step 3: Call Claude (thread-offloaded since SDK is sync)
        user_prompt = _build_user_prompt(ticker, filing_data, news_articles)
        report_content = await asyncio.to_thread(_call_claude_sync, user_prompt)
        # Step 4: Store report
        report = ResearchReport(stock_ticker=ticker, report_content=report_content, sources=sources)
        db.add(report)
        await db.commit()
```

### Thread-Offloading Sync SDK Calls

The Anthropic Python SDK's `messages.create()` is synchronous. Wrap in `asyncio.to_thread()` to avoid blocking the event loop:

```python
report_content = await asyncio.to_thread(_call_claude_sync, user_prompt)
```

### Progress Tracking at Each Stage

Each pipeline stage updates the task status so the frontend can show which step is active:

```python
await _update_task_progress(db, task_id, "fetching_filing")
filing_data = await fetch_filing_sections(ticker)

await _update_task_progress(db, task_id, "fetching_news")
news_articles = await fetch_news(ticker)

await _update_task_progress(db, task_id, "analyzing")
report_content = await asyncio.to_thread(_call_claude_sync, user_prompt)

await _update_task_progress(db, task_id, "storing")
# ... save to DB
```

### User Prompt Construction

Build a structured prompt from collected data with clear section headers:

```python
def _build_user_prompt(ticker, filing_data, news_articles):
    parts = [f"## Research Request: {ticker}\n"]

    if filing_data.filing_type not in ("none", "error"):
        parts.append(f"### SEC Filing ({filing_data.filing_type})")
        for key, text in filing_data.sections.items():
            truncated = text[:50_000] if len(text) > 50_000 else text
            parts.append(f"\n#### {key.replace('_', ' ').title()}\n{truncated}")
    else:
        parts.append("### SEC Filing\nNo recent filing data available.")

    if news_articles:
        parts.append(f"\n### Recent News ({len(news_articles)} articles)")
        for article in news_articles:
            parts.append(f"- **{article.headline}** ({article.source})\n  {article.summary}")

    return "\n\n".join(parts)
```

Key decisions:
- Truncate filing sections to 50K chars to stay within context limits
- Distinguish between "no data" and "error fetching data"
- Include metadata (source, date) so Claude can assess recency

### Cross-Entity State Updates

When research completes, update the screening result's stage so the UI reflects the new state:

```python
await db.execute(
    update(ScreeningResult)
    .where(ScreeningResult.stock_ticker == ticker, ScreeningResult.stage == "researching")
    .values(stage="researched")
)
```

## Why This Matters

**Structured output**: Using JSON schema in the system prompt gets ~99% valid JSON responses. The code fence stripping handles the remaining edge cases without additional API calls or retries.

**Cost control**: Prompt caching reduces cost by ~90% for the system prompt portion (which is large). The semaphore prevents accidentally launching 50 concurrent Claude calls.

**Composability**: SEC data + news → structured prompt → structured response → Postgres JSON column. Each piece is independently testable and the pipeline can be extended with new data sources.

**Traceability**: Sources (filing type, date, news count, URLs) are stored alongside the report content, so users can verify claims and trace analysis back to raw data.

## When to Apply

- Claude API calls that need structured (JSON) responses
- Pipelines that gather multiple data sources before LLM analysis
- Multiple concurrent LLM tasks needing rate control
- Results that must be persisted and linked to other entities

**Alternatives for different needs:**
- If the schema is complex, consider Claude's tool use (function calling) instead of JSON in system prompt
- If real-time streaming is needed, use the streaming API instead of batch
- If the output is free-form text (not structured), skip the JSON schema approach

## Examples

A complete research flow for ticker "AAPL":

1. Frontend POSTs to `/api/research` with `{"ticker": "AAPL"}`
2. Backend creates TaskStatus, launches background task
3. Background task acquires semaphore (waits if 3 already running)
4. Fetches EDGAR 10-Q filing for AAPL → structured sections
5. Fetches Finnhub news for AAPL → 5-10 recent articles
6. Builds user prompt (~30K tokens with filing sections)
7. Calls Claude via `asyncio.to_thread` → structured JSON response
8. Stores ResearchReport with `report_content` (JSON) and `sources` (provenance)
9. Updates ScreeningResult stage from "researching" → "researched"
10. Marks task as completed with `result_id` pointing to the report

## Related

- [[background-task-lifecycle-management-2026-05-17]] — task system that orchestrates research tasks
- [[external-api-client-architecture-2026-05-17]] — EDGAR and Finnhub clients follow same patterns
- `stock-analyzer/backend/app/services/research_agent.py`: Main implementation
- `stock-analyzer/backend/app/services/edgar_client.py`: SEC filing extraction
- `stock-analyzer/backend/app/services/news_client.py`: Finnhub news fetching
- Commit `698dc3a`: SEC EDGAR integration, Finnhub news, and Claude research agent
