"""SEC EDGAR filing extraction using edgartools.

Fetches 10-K and 10-Q filings, extracts key sections (Business,
Risk Factors, MD&A), and returns structured filing data.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from edgar import Company

logger = logging.getLogger(__name__)

# Maximum characters for the raw-text fallback (~50K tokens)
RAW_TEXT_MAX_CHARS = 200_000

# Sections to extract from 10-K filings
TEN_K_ITEMS = {
    "item_1": "Item 1",
    "item_1a": "Item 1A",
    "item_7": "Item 7",
}

# Sections to extract from 10-Q filings
TEN_Q_ITEMS = {
    "item_2": "Part I, Item 2",
}


@dataclass
class FilingData:
    ticker: str
    filing_type: str  # "10-K" or "10-Q"
    filing_date: str
    sections: dict[str, str] = field(default_factory=dict)
    edgar_url: str = ""
    raw_text_fallback: str | None = None


class EdgarClientError(Exception):
    """Generic EDGAR client error."""


def _fetch_filing_sync(ticker: str) -> FilingData:
    """Synchronous function to fetch and extract filing data.

    Called via asyncio.to_thread() from async context since
    edgartools is a synchronous library.
    """
    company = Company(ticker)

    # Try 10-K first, fall back to 10-Q
    for filing_type, items_map in [("10-K", TEN_K_ITEMS), ("10-Q", TEN_Q_ITEMS)]:
        filings = company.get_filings(form=filing_type)
        if filings is None or len(filings) == 0:
            continue

        latest = filings[0]
        filing_date = str(latest.filing_date) if hasattr(latest, "filing_date") else ""
        edgar_url = latest.filing_homepage if hasattr(latest, "filing_homepage") else ""

        # Try to get the structured document
        try:
            doc = latest.obj()
        except Exception:
            logger.warning("Could not parse %s document for %s, using raw text", filing_type, ticker)
            doc = None

        sections: dict[str, str] = {}
        if doc is not None:
            for key, item_name in items_map.items():
                try:
                    section_text = str(getattr(doc, key, None) or "")
                    if section_text.strip():
                        sections[key] = section_text.strip()
                except Exception:
                    logger.debug("Could not extract %s from %s for %s", item_name, filing_type, ticker)

        # If no sections extracted, fall back to raw text
        raw_fallback: str | None = None
        if not sections:
            try:
                raw_text = latest.text()
                if raw_text:
                    raw_fallback = raw_text[:RAW_TEXT_MAX_CHARS]
            except Exception:
                logger.warning("Could not get raw text for %s %s", ticker, filing_type)

        return FilingData(
            ticker=ticker,
            filing_type=filing_type,
            filing_date=filing_date,
            sections=sections,
            edgar_url=str(edgar_url),
            raw_text_fallback=raw_fallback,
        )

    # No filings found at all
    return FilingData(
        ticker=ticker,
        filing_type="none",
        filing_date="",
        sections={},
        edgar_url="",
        raw_text_fallback=None,
    )


async def fetch_filing_sections(ticker: str) -> FilingData:
    """Fetch SEC filing sections for a ticker.

    Wraps the synchronous edgartools calls in asyncio.to_thread().
    """
    try:
        return await asyncio.to_thread(_fetch_filing_sync, ticker)
    except Exception as exc:
        logger.error("EDGAR fetch failed for %s: %s", ticker, exc)
        return FilingData(
            ticker=ticker,
            filing_type="error",
            filing_date="",
            sections={},
            edgar_url="",
            raw_text_fallback=None,
        )
