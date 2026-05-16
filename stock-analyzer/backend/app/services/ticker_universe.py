"""Ticker universe — dynamically discovers US stocks for screening via Yahoo Finance.

Uses yfinance's EquityQuery screener to find US-listed stocks above a market cap
threshold. Caches the result for 7 days to avoid repeat API calls.
Falls back to a curated S&P 500 list if the live fetch fails.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).resolve().parent.parent.parent / ".tmp" / "ticker_universe.json"
_CACHE_MAX_AGE_DAYS = 7
_MIN_MARKET_CAP = 2_000_000_000
_US_EXCHANGES = {"NMS", "NYQ", "NGM", "NCM"}


def _fetch_from_yahoo() -> list[str]:
    """Fetch US-listed stocks above market cap threshold via Yahoo Finance screener."""
    import yfinance as yf

    tickers: list[str] = []
    offset = 0

    while True:
        eq = yf.EquityQuery("and", [
            yf.EquityQuery("gt", ["intradaymarketcap", _MIN_MARKET_CAP]),
            yf.EquityQuery("eq", ["region", "us"]),
        ])
        result = yf.screen(eq, offset=offset, size=250)
        quotes = result.get("quotes", [])
        if not quotes:
            break
        for q in quotes:
            sym = q.get("symbol", "")
            exchange = q.get("exchange", "")
            if sym and exchange in _US_EXCHANGES and "." not in sym:
                tickers.append(sym)
        total = result.get("total", 0)
        offset += 250
        if offset >= total:
            break

    return sorted(set(tickers))


def _read_cache() -> list[str] | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        age = datetime.now(timezone.utc) - cached_at
        if age.days >= _CACHE_MAX_AGE_DAYS:
            return None
        return data["tickers"]
    except Exception:
        return None


def _write_cache(tickers: list[str]) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "tickers": tickers,
    }
    _CACHE_FILE.write_text(json.dumps(data))


def get_screening_universe() -> list[str]:
    """Return US-listed stocks for screening.

    Tries: cached tickers -> live Yahoo screener -> hardcoded fallback.
    """
    cached = _read_cache()
    if cached:
        logger.info("Using cached ticker universe (%d tickers)", len(cached))
        return cached

    try:
        tickers = _fetch_from_yahoo()
        if len(tickers) >= 200:
            _write_cache(tickers)
            logger.info("Fetched ticker universe from Yahoo (%d tickers)", len(tickers))
            return tickers
        logger.warning("Yahoo screener returned only %d tickers, using fallback", len(tickers))
    except Exception as exc:
        logger.warning("Failed to fetch ticker universe from Yahoo: %s", exc)

    return _FALLBACK_TICKERS


_FALLBACK_TICKERS = [
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM",
    "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM",
    "ALB", "ALGN", "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP",
    "AMT", "AMZN", "ANET", "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV",
    "ARE", "ATO", "AVB", "AVGO", "AVY", "AWK", "AXP", "AZO",
    "BA", "BAC", "BAX", "BBY", "BDX", "BEN", "BF-B", "BG", "BIIB",
    "BIO", "BK", "BKNG", "BKR", "BLDR", "BLK", "BMY", "BR", "BRK-B", "BRO",
    "BSX", "BWA", "BX", "BXP",
    "C", "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL",
    "CDNS", "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR", "CI",
    "CINF", "CL", "CLX", "CMCSA", "CME", "CMG", "CMI", "CMS", "CNC", "CNP",
    "COF", "COO", "COP", "COR", "COST", "CPAY", "CPB", "CPRT", "CPT", "CRL",
    "CRM", "CRWD", "CSCO", "CSGP", "CSX", "CTAS", "CTRA", "CTSH",
    "CTVA", "CVS", "CVX", "CZR",
    "D", "DAL", "DD", "DE", "DECK", "DFS", "DG", "DGX", "DHI",
    "DHR", "DIS", "DLR", "DLTR", "DOV", "DOW", "DPZ", "DRI", "DTE",
    "DUK", "DVA", "DVN",
    "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EIX", "EL", "EMN",
    "EMR", "ENPH", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ERIE", "ES", "ESS",
    "ETN", "ETR", "EVRG", "EW", "EXC", "EXPD", "EXPE", "EXR",
    "F", "FANG", "FAST", "FCNCA", "FDS", "FDX", "FE", "FFIV", "FI", "FICO",
    "FIS", "FITB", "FMC", "FOX", "FOXA", "FRT", "FSLR", "FTNT",
    "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GILD", "GIS", "GL",
    "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW",
    "HAL", "HAS", "HBAN", "HCA", "HD", "HES", "HIG", "HII", "HLT",
    "HOLX", "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB",
    "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY",
    "INTC", "INTU", "INVH", "IP", "IPG", "IQV", "IR", "IRM", "ISRG",
    "IT", "ITW", "IVZ",
    "J", "JBHT", "JBL", "JCI", "JKHY", "JNJ", "JNPR", "JPM",
    "K", "KDP", "KEY", "KEYS", "KHC", "KIM", "KKR", "KLAC", "KMB", "KMI",
    "KMX", "KO", "KR",
    "L", "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ", "LLY", "LMT", "LNT",
    "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV",
    "MA", "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT",
    "MET", "META", "MGM", "MHK", "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST",
    "MO", "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRO", "MS", "MSCI",
    "MSFT", "MSI", "MTB", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE",
    "NEM", "NFLX", "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS",
    "NUE", "NVDA", "NVR", "NWS", "NWSA", "NXPI",
    "O", "ODFL", "OKE", "OMC", "ON", "ORCL", "ORLY", "OTIS", "OXY",
    "PANW", "PAYC", "PAYX", "PCAR", "PCG", "PEG", "PEP", "PFE",
    "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD", "PLTR", "PM", "PNC",
    "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX", "PTC",
    "PVH", "PWR", "PYPL", "QCOM", "QRVO", "RCL", "REG", "REGN",
    "RF", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG", "RTX",
    "RVTY", "SBAC", "SBUX", "SCHW", "SEE", "SHW", "SJM", "SLB",
    "SMCI", "SNA", "SNPS", "SO", "SPG", "SPGI", "SRE", "STE",
    "STLD", "STT", "STX", "STZ", "SWK", "SWKS", "SYF", "SYK", "SYY",
    "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TFX", "TGT",
    "TJX", "TMO", "TMUS", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO",
    "TSLA", "TSN", "TT", "TTWO", "TXN", "TXT", "TYL",
    "UAL", "UBER", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB",
    "V", "VICI", "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRTX", "VST",
    "VTR", "VTRS", "VZ",
    "WAB", "WAT", "WBA", "WBD", "WDC", "WEC", "WELL", "WFC", "WM", "WMB",
    "WMT", "WRB", "WST", "WTW", "WY", "WYNN",
    "XEL", "XOM", "XYL",
    "YUM",
    "ZBH", "ZBRA", "ZION", "ZTS",
]
