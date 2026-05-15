"""Tests for the SEC EDGAR client.

All tests mock edgartools — no real SEC API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.edgar_client import (
    RAW_TEXT_MAX_CHARS,
    FilingData,
    _fetch_filing_sync,
    fetch_filing_sections,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_filing(filing_type: str = "10-K", has_doc: bool = True, has_sections: bool = True):
    """Create a mock filing object mimicking edgartools behavior."""
    filing = MagicMock()
    filing.filing_date = "2025-02-15"
    filing.filing_homepage = f"https://www.sec.gov/Archives/edgar/data/0000320193/{filing_type.lower()}.htm"

    if has_doc:
        doc = MagicMock()
        if has_sections and filing_type == "10-K":
            doc.item_1 = "Apple Inc. designs, manufactures, and markets smartphones..."
            doc.item_1a = "The Company is subject to risks related to global markets..."
            doc.item_7 = "Revenue increased 8% year over year driven by iPhone sales..."
        elif has_sections and filing_type == "10-Q":
            doc.item_2 = "Quarterly revenue was $94.8 billion, up 5% from prior year..."
        else:
            doc.item_1 = None
            doc.item_1a = ""
            doc.item_7 = None
            doc.item_2 = None
        filing.obj.return_value = doc
    else:
        filing.obj.side_effect = Exception("Could not parse document")

    filing.text.return_value = "This is the raw filing text content..." * 100
    return filing


def _make_mock_filings(filing_list: list):
    """Create a mock filings collection."""
    mock_filings = MagicMock()
    mock_filings.__len__ = lambda self: len(filing_list)
    mock_filings.__getitem__ = lambda self, idx: filing_list[idx]
    return mock_filings


# ---------------------------------------------------------------------------
# Tests: Happy path — 10-K extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_10k_extracts_sections():
    """Successful 10-K fetch should extract item_1, item_1a, item_7."""
    mock_filing = _make_mock_filing("10-K", has_doc=True, has_sections=True)
    mock_filings_10k = _make_mock_filings([mock_filing])
    mock_filings_10q = _make_mock_filings([])

    mock_company = MagicMock()

    def get_filings_side_effect(form=None):
        if form == "10-K":
            return mock_filings_10k
        return mock_filings_10q

    mock_company.get_filings.side_effect = get_filings_side_effect

    with patch("app.services.edgar_client.Company", return_value=mock_company):
        result = await fetch_filing_sections("AAPL")

    assert isinstance(result, FilingData)
    assert result.ticker == "AAPL"
    assert result.filing_type == "10-K"
    assert result.filing_date == "2025-02-15"
    assert "item_1" in result.sections
    assert "item_1a" in result.sections
    assert "item_7" in result.sections
    assert "smartphones" in result.sections["item_1"]
    assert result.raw_text_fallback is None


# ---------------------------------------------------------------------------
# Tests: 10-Q fallback when no 10-K exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_falls_back_to_10q_when_no_10k():
    """If no 10-K filings exist, should try 10-Q."""
    mock_10q = _make_mock_filing("10-Q", has_doc=True, has_sections=True)
    mock_filings_10k = _make_mock_filings([])
    mock_filings_10q = _make_mock_filings([mock_10q])

    mock_company = MagicMock()

    def get_filings_side_effect(form=None):
        if form == "10-K":
            return mock_filings_10k
        return mock_filings_10q

    mock_company.get_filings.side_effect = get_filings_side_effect

    with patch("app.services.edgar_client.Company", return_value=mock_company):
        result = await fetch_filing_sections("NEWCO")

    assert result.filing_type == "10-Q"
    assert "item_2" in result.sections
    assert "Quarterly revenue" in result.sections["item_2"]


# ---------------------------------------------------------------------------
# Tests: Raw text fallback when sections fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raw_text_fallback_when_sections_empty():
    """If section extraction yields nothing, should fall back to raw text."""
    mock_filing = _make_mock_filing("10-K", has_doc=True, has_sections=False)
    mock_filings = _make_mock_filings([mock_filing])

    mock_company = MagicMock()
    mock_company.get_filings.return_value = mock_filings

    with patch("app.services.edgar_client.Company", return_value=mock_company):
        result = await fetch_filing_sections("AAPL")

    assert result.sections == {}
    assert result.raw_text_fallback is not None
    assert "raw filing text" in result.raw_text_fallback


@pytest.mark.asyncio
async def test_raw_text_fallback_when_doc_parsing_fails():
    """If obj() raises, should fall back to raw text."""
    mock_filing = _make_mock_filing("10-K", has_doc=False)
    mock_filings = _make_mock_filings([mock_filing])

    mock_company = MagicMock()
    mock_company.get_filings.return_value = mock_filings

    with patch("app.services.edgar_client.Company", return_value=mock_company):
        result = await fetch_filing_sections("AAPL")

    assert result.sections == {}
    assert result.raw_text_fallback is not None


@pytest.mark.asyncio
async def test_raw_text_truncated_to_max_chars():
    """Raw text fallback should be truncated to RAW_TEXT_MAX_CHARS."""
    long_text = "A" * (RAW_TEXT_MAX_CHARS + 10_000)
    mock_filing = _make_mock_filing("10-K", has_doc=True, has_sections=False)
    mock_filing.text.return_value = long_text
    mock_filings = _make_mock_filings([mock_filing])

    mock_company = MagicMock()
    mock_company.get_filings.return_value = mock_filings

    with patch("app.services.edgar_client.Company", return_value=mock_company):
        result = await fetch_filing_sections("AAPL")

    assert result.raw_text_fallback is not None
    assert len(result.raw_text_fallback) == RAW_TEXT_MAX_CHARS


# ---------------------------------------------------------------------------
# Tests: No filings found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_filings_returns_empty():
    """If company has no 10-K or 10-Q, return filing_type='none'."""
    mock_company = MagicMock()
    mock_company.get_filings.return_value = _make_mock_filings([])

    with patch("app.services.edgar_client.Company", return_value=mock_company):
        result = await fetch_filing_sections("FAKE")

    assert result.ticker == "FAKE"
    assert result.filing_type == "none"
    assert result.sections == {}
    assert result.raw_text_fallback is None


# ---------------------------------------------------------------------------
# Tests: Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_returns_error_filing_data():
    """If edgartools throws, should return filing_type='error' gracefully."""
    with patch("app.services.edgar_client.Company", side_effect=Exception("Network error")):
        result = await fetch_filing_sections("BOOM")

    assert result.ticker == "BOOM"
    assert result.filing_type == "error"
    assert result.sections == {}


# ---------------------------------------------------------------------------
# Tests: FilingData dataclass
# ---------------------------------------------------------------------------

def test_filing_data_defaults():
    """FilingData should have sensible defaults."""
    fd = FilingData(ticker="TEST", filing_type="10-K", filing_date="2025-01-01")
    assert fd.sections == {}
    assert fd.edgar_url == ""
    assert fd.raw_text_fallback is None
