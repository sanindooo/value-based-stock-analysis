"""Claude-powered research agent.

Orchestrates SEC filing extraction, news collection, and Claude analysis
to produce structured investment research reports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import update

from app.core.config import settings
from app.models.research import ResearchReport
from app.models.screening import ScreeningResult
from app.models.task import TaskStatus
from app.services.article_extractor import ExtractedArticle, fetch_and_extract, create_zyte_budget
from app.services.edgar_client import fetch_filing_sections
from app.services.news_client import fetch_news
from app.services.news_discovery import discover_articles

logger = logging.getLogger(__name__)

# Limit concurrent research tasks to avoid overwhelming external APIs
_semaphore = asyncio.Semaphore(3)

SYSTEM_PROMPT = """You are a senior financial analyst producing structured investment research reports.

Analyze the provided SEC filing data and recent news to produce a comprehensive but concise report.

You MUST respond with valid JSON matching this exact schema:

{
  "company_overview": "2-3 paragraph overview of what the company does, its market position, and business model",
  "competitive_position": "Analysis of competitive advantages, moats, market share, and industry dynamics",
  "financial_health": "Assessment of balance sheet strength, cash flows, profitability trends, and capital allocation",
  "growth_trajectory": "Evaluation of revenue/earnings growth drivers, TAM expansion, and forward outlook",
  "key_risks": "Top 3-5 material risks including regulatory, competitive, macro, and company-specific threats",
  "investment_opinion": {
    "verdict": "buy | hold | avoid",
    "confidence": "high | medium | low",
    "reasoning": "2-3 sentence summary of the investment thesis"
  }
}

Guidelines:
- Be specific and data-driven. Reference actual numbers from the filings when available.
- Distinguish between facts (from filings) and interpretations (your analysis).
- If filing data is limited or unavailable, note this and base analysis on available news and general knowledge.
- The verdict should reflect a value investing perspective: focus on intrinsic value, margin of safety, and long-term fundamentals.
- Respond ONLY with the JSON object, no markdown code fences or extra text."""

PRESERVATION_SYSTEM_PROMPT = """You are a senior financial analyst producing structured investment research reports with a focus on INFLATION RESILIENCE and CAPITAL PRESERVATION.

Analyze the provided SEC filing data, news, and preservation metrics to produce a comprehensive report that emphasizes how well this company protects investor capital during inflationary environments.

You MUST respond with valid JSON matching this exact schema:

{
  "company_overview": "2-3 paragraph overview emphasizing business model durability and inflation exposure",
  "competitive_position": "Analysis of competitive advantages with focus on pricing power sustainability",
  "financial_health": "Assessment emphasizing margin stability, dividend reliability, and balance sheet resilience",
  "growth_trajectory": "Evaluation of real (inflation-adjusted) growth potential and revenue consistency",
  "key_risks": "Top 3-5 risks with emphasis on inflation sensitivity, margin compression, and purchasing power erosion",
  "pricing_power_durability": "Assessment of the company's ability to pass cost increases to customers sustainably",
  "dividend_sustainability_under_stress": "Analysis of dividend coverage, payout ratio trends, and resilience during economic stress",
  "inflation_resilience_assessment": "Overall evaluation of how the business performs during high-inflation periods",
  "competitive_moat_strength": "Assessment of durable competitive advantages that protect margins over decades",
  "investment_opinion": {
    "verdict": "buy | hold | avoid",
    "confidence": "high | medium | low",
    "reasoning": "2-3 sentence summary focusing on capital preservation thesis"
  }
}

Guidelines:
- Be specific and data-driven. Reference actual numbers from the filings when available.
- Distinguish between facts (from filings) and interpretations (your analysis).
- If filing data is limited or unavailable, note this and base analysis on available news and general knowledge.
- The verdict should reflect a PRESERVATION investing perspective: focus on inflation resilience, pricing power, dividend sustainability, and capital protection.
- Respond ONLY with the JSON object, no markdown code fences or extra text."""


MAX_ARTICLE_PROMPT_CHARS = 5000

_INJECTION_PATTERN = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous\s+instructions|you\s+are\s+now|system\s*:|<\s*/?\s*system\s*>)",
)


def _sanitize_text(text: str, max_len: int = MAX_ARTICLE_PROMPT_CHARS) -> str:
    """Strip injection patterns and cap length."""
    return _INJECTION_PATTERN.sub("", text)[:max_len]


def _build_user_prompt(
    ticker: str,
    filing_data,
    news_articles: list,
    full_articles: list[ExtractedArticle] | None = None,
) -> str:
    """Build the user prompt from collected data."""
    parts = [f"## Research Request: {ticker}\n"]

    # Filing data
    if filing_data.filing_type not in ("none", "error"):
        parts.append(f"### SEC Filing ({filing_data.filing_type}, dated {filing_data.filing_date})")
        if filing_data.edgar_url:
            parts.append(f"Source: {filing_data.edgar_url}")

        if filing_data.sections:
            for key, text in filing_data.sections.items():
                label = key.replace("_", " ").title()
                truncated = text[:50_000] if len(text) > 50_000 else text
                parts.append(f"\n#### {label}\n{truncated}")
        elif filing_data.raw_text_fallback:
            parts.append(f"\n#### Raw Filing Text (truncated)\n{filing_data.raw_text_fallback}")
    else:
        parts.append("### SEC Filing\nNo recent SEC filing data available for this ticker.")

    # News headlines
    if news_articles:
        parts.append(f"\n### Recent News ({len(news_articles)} articles)")
        for article in news_articles:
            parts.append(
                f"- **{article.headline}** ({article.source}, {article.published_at})\n"
                f"  {article.summary}"
            )
    else:
        parts.append("\n### Recent News\nNo recent news articles found.")

    # Full article content (deep analysis only)
    if full_articles:
        parts.append(f"\n### Full News Articles ({len(full_articles)} articles)")
        for article in full_articles:
            sanitized = _sanitize_text(article.content)
            title = _sanitize_text(article.title, 200)
            date = _sanitize_text(article.publication_date, 50)
            parts.append(
                f"\n<article>\n"
                f"Title: {title}\n"
                f"Date: {date}\n\n"
                f"{sanitized}\n"
                f"</article>"
            )

    return "\n\n".join(parts)


def _call_claude_sync(user_prompt: str, api_key: str | None = None, mode: str = "value") -> dict:
    """Synchronous Claude API call. Run via asyncio.to_thread()."""
    key = api_key or settings.anthropic_api_key
    client = Anthropic(api_key=key)

    prompt_text = PRESERVATION_SYSTEM_PROMPT if mode == "preservation" else SYSTEM_PROMPT

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        timeout=120,
        system=[
            {
                "type": "text",
                "text": prompt_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines).strip()

    return json.loads(raw_text)


async def _update_task_progress(db: AsyncSession, task_id: int, progress: str) -> None:
    """Update the progress field on a TaskStatus row."""
    result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.progress = progress
        await db.commit()


async def run_research_for_ticker(
    db: AsyncSession,
    ticker: str,
    task_id: int,
    mode: str = "value",
    company_name: str | None = None,
) -> ResearchReport:
    """Run the full research pipeline for a single ticker.

    Updates task progress throughout and stores the result in the DB.
    """
    async with _semaphore:
        try:
            # Mark task as running now that we've acquired the semaphore
            result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.status = "running"
                await db.commit()

            # Step 1: Fetch SEC filing
            await _update_task_progress(db, task_id, "fetching_filing")
            filing_data = await fetch_filing_sections(ticker)

            # Step 2: Extract sections (already done in fetch_filing_sections)
            await _update_task_progress(db, task_id, "extracting_sections")

            # Step 3: Fetch news
            await _update_task_progress(db, task_id, "fetching_news")
            news_articles = await fetch_news(ticker)

            # Step 3b: Deep analysis — discover and extract full articles
            full_articles: list[ExtractedArticle] = []
            await _update_task_progress(db, task_id, "fetching_articles")
            budget = create_zyte_budget()
            discovered = await discover_articles(ticker, company_name)

            async def _extract_one(disc_article):
                extracted = await fetch_and_extract(disc_article.url, budget)
                if extracted:
                    if not extracted.title:
                        extracted.title = disc_article.title
                    if not extracted.publication_date:
                        extracted.publication_date = disc_article.published_date
                return extracted

            results = await asyncio.gather(
                *[_extract_one(a) for a in discovered],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, ExtractedArticle):
                    full_articles.append(result)

            # Step 4: Build prompt and call Claude
            await _update_task_progress(db, task_id, "analyzing")
            user_prompt = _build_user_prompt(ticker, filing_data, news_articles, full_articles)
            report_content = await asyncio.to_thread(_call_claude_sync, user_prompt, None, mode)

            # Step 5: Store report
            await _update_task_progress(db, task_id, "storing")
            sources = {
                "filing_type": filing_data.filing_type,
                "filing_date": filing_data.filing_date,
                "filing_url": filing_data.edgar_url,
                "news_articles": [
                    {"title": a.headline, "url": a.url, "source": a.source}
                    for a in news_articles
                ] + [
                    {"title": a.title, "url": ""}
                    for a in full_articles
                    if a.title
                ],
            }

            report = ResearchReport(
                stock_ticker=ticker,
                report_content=report_content,
                sources=sources,
                mode=mode,
            )
            db.add(report)
            await db.commit()
            await db.refresh(report)

            # Step 6: Mark task complete and update screening stage
            result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.status = "completed"
                task.progress = "complete"
                task.result_id = report.id
                task.completed_at = datetime.now(timezone.utc)

            await db.execute(
                update(ScreeningResult)
                .where(
                    ScreeningResult.stock_ticker == ticker,
                    ScreeningResult.stage == "researching",
                )
                .values(stage="researched")
            )
            await db.commit()

            return report

        except Exception as exc:
            logger.exception("Research failed for %s (task %d): %s", ticker, task_id, exc)
            from app.db import async_session as _async_session
            async with _async_session() as err_db:
                result = await err_db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
                task = result.scalar_one_or_none()
                if task and task.status not in ("completed", "failed"):
                    task.status = "failed"
                    task.error_message = "Research failed — check server logs."

                await err_db.execute(
                    update(ScreeningResult)
                    .where(
                        ScreeningResult.stock_ticker == ticker,
                        ScreeningResult.stage == "researching",
                    )
                    .values(stage="screened")
                )
                await err_db.commit()
            raise
