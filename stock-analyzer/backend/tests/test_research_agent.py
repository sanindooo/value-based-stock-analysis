"""Tests for the research agent orchestrator.

All external calls (EDGAR, Finnhub, Claude) are mocked.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.edgar_client import FilingData
from app.services.news_client import NewsArticle
from app.services.research_agent import (
    SYSTEM_PROMPT,
    _build_user_prompt,
    _call_claude_sync,
    run_research_for_ticker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_FILING = FilingData(
    ticker="AAPL",
    filing_type="10-K",
    filing_date="2025-02-15",
    sections={
        "item_1": "Apple designs and manufactures consumer electronics.",
        "item_1a": "Risks include supply chain disruption and competition.",
        "item_7": "Revenue grew 8% driven by iPhone and Services.",
    },
    edgar_url="https://www.sec.gov/Archives/edgar/data/0000320193/10-k.htm",
)

MOCK_NEWS = [
    NewsArticle(
        headline="Apple Reports Record Q4 Revenue",
        summary="Apple reported quarterly revenue of $94.9 billion.",
        source="Reuters",
        url="https://reuters.com/apple-q4",
        published_at="2025-01-30T18:00:00+00:00",
    ),
    NewsArticle(
        headline="Apple Vision Pro Sales Disappoint",
        summary="Analysts lower Vision Pro sales estimates for 2025.",
        source="Bloomberg",
        url="https://bloomberg.com/apple-vision",
        published_at="2025-01-15T12:00:00+00:00",
    ),
]

MOCK_CLAUDE_RESPONSE = {
    "company_overview": "Apple Inc. is a multinational technology company...",
    "competitive_position": "Strong brand loyalty and ecosystem lock-in...",
    "financial_health": "Excellent cash generation with $100B+ free cash flow...",
    "growth_trajectory": "Services segment growing 15% YoY...",
    "key_risks": "Smartphone market saturation, regulatory pressure in EU...",
    "investment_opinion": {
        "verdict": "hold",
        "confidence": "high",
        "reasoning": "Strong fundamentals but fully valued at current multiples.",
    },
}


def _make_mock_db():
    """Create a mock AsyncSession that tracks task updates."""
    db = AsyncMock()

    task = MagicMock()
    task.id = 1
    task.status = "pending"
    task.progress = "queued"
    task.result_id = None
    task.error_message = None
    task.completed_at = None

    report = MagicMock()
    report.id = 42
    report.stock_ticker = "AAPL"
    report.report_content = MOCK_CLAUDE_RESPONSE
    report.sources = {}
    report.created_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = task

    db.execute.return_value = mock_result
    db.commit = AsyncMock()

    # db.refresh should set report.id for newly added reports
    async def mock_refresh(obj):
        if hasattr(obj, "stock_ticker"):
            obj.id = 42

    db.refresh = AsyncMock(side_effect=mock_refresh)
    db.add = MagicMock()

    return db, task


# ---------------------------------------------------------------------------
# Tests: Prompt building
# ---------------------------------------------------------------------------

def test_build_user_prompt_with_full_data():
    """Prompt should include filing sections and news articles."""
    prompt = _build_user_prompt("AAPL", MOCK_FILING, MOCK_NEWS)

    assert "AAPL" in prompt
    assert "10-K" in prompt
    assert "2025-02-15" in prompt
    assert "consumer electronics" in prompt.lower()
    assert "supply chain" in prompt.lower()
    assert "Record Q4 Revenue" in prompt
    assert "Vision Pro" in prompt
    assert "sec.gov" in prompt


def test_build_user_prompt_no_filing():
    """Prompt should note when no filing is available."""
    empty_filing = FilingData(
        ticker="NEWCO", filing_type="none", filing_date="", sections={}
    )
    prompt = _build_user_prompt("NEWCO", empty_filing, [])

    assert "No recent SEC filing data" in prompt
    assert "No recent news articles" in prompt


def test_build_user_prompt_with_raw_fallback():
    """Prompt should include raw text when sections are empty."""
    fallback_filing = FilingData(
        ticker="XYZ",
        filing_type="10-K",
        filing_date="2025-01-01",
        sections={},
        edgar_url="https://sec.gov/xyz",
        raw_text_fallback="This is the raw filing content for XYZ Corp...",
    )
    prompt = _build_user_prompt("XYZ", fallback_filing, [])

    assert "Raw Filing Text" in prompt
    assert "raw filing content for XYZ" in prompt


def test_build_user_prompt_truncates_long_sections():
    """Sections longer than 50K chars should be truncated."""
    long_filing = FilingData(
        ticker="BIG",
        filing_type="10-K",
        filing_date="2025-01-01",
        sections={"item_1": "X" * 60_000},
        edgar_url="",
    )
    prompt = _build_user_prompt("BIG", long_filing, [])

    # The section in the prompt should be 50K chars, not 60K
    assert "X" * 50_000 in prompt
    assert "X" * 60_000 not in prompt


# ---------------------------------------------------------------------------
# Tests: Claude API call
# ---------------------------------------------------------------------------

def test_call_claude_sync_parses_json():
    """Should parse Claude's JSON response correctly."""
    mock_content = MagicMock()
    mock_content.text = json.dumps(MOCK_CLAUDE_RESPONSE)

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("app.services.research_agent.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        MockAnthropic.return_value = mock_client

        result = _call_claude_sync("Analyze AAPL", api_key="test-key")

    assert result["investment_opinion"]["verdict"] == "hold"
    assert result["company_overview"] == MOCK_CLAUDE_RESPONSE["company_overview"]

    # Verify prompt caching is used
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_call_claude_sync_strips_code_fences():
    """Should handle Claude wrapping JSON in markdown code fences."""
    fenced_json = f"```json\n{json.dumps(MOCK_CLAUDE_RESPONSE)}\n```"

    mock_content = MagicMock()
    mock_content.text = fenced_json

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("app.services.research_agent.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        MockAnthropic.return_value = mock_client

        result = _call_claude_sync("Analyze AAPL", api_key="test-key")

    assert result["investment_opinion"]["verdict"] == "hold"


# ---------------------------------------------------------------------------
# Tests: Full pipeline orchestration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_research_full_pipeline():
    """Full pipeline should fetch filing, news, call Claude, and store report."""
    mock_db, mock_task = _make_mock_db()

    with (
        patch(
            "app.services.research_agent.fetch_filing_sections",
            new_callable=AsyncMock,
            return_value=MOCK_FILING,
        ) as mock_edgar,
        patch(
            "app.services.research_agent.fetch_news",
            new_callable=AsyncMock,
            return_value=MOCK_NEWS,
        ) as mock_news,
        patch(
            "app.services.research_agent._call_claude_sync",
            return_value=MOCK_CLAUDE_RESPONSE,
        ),
        patch("asyncio.to_thread", new_callable=AsyncMock, return_value=MOCK_CLAUDE_RESPONSE),
    ):
        report = await run_research_for_ticker(mock_db, "AAPL", task_id=1)

    # EDGAR and news were called
    mock_edgar.assert_called_once_with("AAPL")
    mock_news.assert_called_once_with("AAPL")

    # Report was stored
    mock_db.add.assert_called()
    mock_db.commit.assert_called()

    # Task was marked complete
    assert mock_task.status == "completed"
    assert mock_task.progress == "complete"
    assert mock_task.result_id == 42


@pytest.mark.asyncio
async def test_run_research_marks_task_failed_on_error():
    """If the pipeline fails, the task should be marked as failed."""
    mock_db, mock_task = _make_mock_db()

    with (
        patch(
            "app.services.research_agent.fetch_filing_sections",
            new_callable=AsyncMock,
            side_effect=Exception("EDGAR is down"),
        ),
    ):
        with pytest.raises(Exception, match="EDGAR is down"):
            await run_research_for_ticker(mock_db, "AAPL", task_id=1)

    assert mock_task.status == "failed"
    assert "EDGAR is down" in mock_task.error_message


@pytest.mark.asyncio
async def test_run_research_updates_progress():
    """Progress should be updated through each pipeline stage."""
    mock_db, mock_task = _make_mock_db()
    progress_values: list[str] = []

    # Track progress updates by capturing task.progress assignments
    original_commit = mock_db.commit

    async def tracking_commit():
        if mock_task.progress:
            progress_values.append(mock_task.progress)
        return await original_commit()

    mock_db.commit = AsyncMock(side_effect=tracking_commit)

    with (
        patch(
            "app.services.research_agent.fetch_filing_sections",
            new_callable=AsyncMock,
            return_value=MOCK_FILING,
        ),
        patch(
            "app.services.research_agent.fetch_news",
            new_callable=AsyncMock,
            return_value=MOCK_NEWS,
        ),
        patch("asyncio.to_thread", new_callable=AsyncMock, return_value=MOCK_CLAUDE_RESPONSE),
    ):
        await run_research_for_ticker(mock_db, "AAPL", task_id=1)

    # Should have gone through the expected stages
    assert "fetching_filing" in progress_values
    assert "analyzing" in progress_values
    assert "complete" in progress_values


# ---------------------------------------------------------------------------
# Tests: System prompt quality
# ---------------------------------------------------------------------------

def test_system_prompt_requests_json():
    """System prompt should instruct Claude to respond with JSON."""
    assert "JSON" in SYSTEM_PROMPT
    assert "company_overview" in SYSTEM_PROMPT
    assert "investment_opinion" in SYSTEM_PROMPT
    assert "verdict" in SYSTEM_PROMPT
    assert "buy" in SYSTEM_PROMPT
    assert "hold" in SYSTEM_PROMPT
    assert "avoid" in SYSTEM_PROMPT
