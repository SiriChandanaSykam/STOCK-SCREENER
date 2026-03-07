"""
historical_data.py — Bootstrap historical OHLCV seed data at startup.

Responsibilities:
  * Fetch daily OHLCV data for every symbol in config.SYMBOLS via the
    Shoonya REST API (get_time_price_series)
  * Store per-symbol DataFrames in the shared in-memory dict SEED_DATA
  * Provide a helper that returns a merged (seed + live ticks) DataFrame
    ready for indicator calculation

Nothing is written to disk at any point.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# Shoonya API is optional at import time (same pattern as data_ingestion.py)
try:
    from NorenRestApiPy.NorenRestApi import NorenApi  # type: ignore[import]
    NOREN_AVAILABLE = True
except ImportError:
    NOREN_AVAILABLE = False

from config import SYMBOLS, NSE_EXCHANGE, WEEK52_PERIOD

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store: symbol -> pd.DataFrame (columns: date, open, high, low,
#                                          close, volume)
# ---------------------------------------------------------------------------
SEED_DATA: dict = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _parse_shoonya_timeseries(raw: list) -> pd.DataFrame:
    """
    Convert the list of dicts returned by get_time_price_series into a
    clean OHLCV DataFrame.
    """
    if not raw:
        return pd.DataFrame()

    rows = []
    for candle in raw:
        try:
            rows.append({
                # Shoonya API field mapping:
                #   ssboe / time  — epoch timestamp (seconds); 'ssboe' is used in
                #                   get_time_price_series, 'time' in some WebSocket variants
                #   into / o      — open price ('into' = interval open, 'o' = short form)
                #   inth / h      — high
                #   intl / l      — low
                #   intc / c      — close
                #   intv / v      — volume
                "date": pd.to_datetime(candle.get("ssboe") or candle.get("time"), unit="s"),
                "open": float(candle.get("into", candle.get("o", 0))),
                "high": float(candle.get("inth", candle.get("h", 0))),
                "low": float(candle.get("intl", candle.get("l", 0))),
                "close": float(candle.get("intc", candle.get("c", 0))),
                "volume": int(candle.get("intv", candle.get("v", 0))),
            })
        except (ValueError, TypeError, KeyError) as exc:
            logger.debug("Skipping malformed candle: %s — %s", candle, exc)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _fetch_symbol_history(api: object, symbol: str, days: int = WEEK52_PERIOD + 20) -> pd.DataFrame:
    """
    Fetch *days* of daily OHLCV data for *symbol* using get_time_price_series.
    Returns an empty DataFrame on any error.
    """
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=int(days * 1.5))  # extra buffer for holidays

    try:
        ret = api.get_time_price_series(  # type: ignore[attr-defined]
            exchange=NSE_EXCHANGE,
            token=symbol,
            starttime=start_dt.strftime("%d-%m-%Y %H:%M:%S"),
            endtime=end_dt.strftime("%d-%m-%Y %H:%M:%S"),
            interval=1440,  # daily bars
        )
        if ret is None:
            logger.warning("No data returned for %s", symbol)
            return pd.DataFrame()
        if isinstance(ret, list):
            return _parse_shoonya_timeseries(ret)
        logger.warning("Unexpected response type for %s: %s", symbol, type(ret))
    except Exception as exc:
        logger.error("Error fetching history for %s: %s", symbol, exc)

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def bootstrap_seed_data(api: Optional[object] = None) -> None:
    """
    Populate SEED_DATA for all symbols in config.SYMBOLS.

    *api* must be a logged-in NorenApi instance (or None when running
    without Shoonya, in which case SEED_DATA will remain empty).
    """
    if api is None or not NOREN_AVAILABLE:
        logger.warning(
            "No Shoonya API instance provided — seed data will be empty. "
            "Indicator values will be available once live ticks accumulate."
        )
        return

    logger.info("Bootstrapping historical seed data for %d symbols…", len(SYMBOLS))
    fetched = 0

    for sym in SYMBOLS:
        df = _fetch_symbol_history(api, sym)
        if not df.empty:
            SEED_DATA[sym] = df
            fetched += 1
            logger.debug("Seeded %s with %d rows", sym, len(df))
        else:
            logger.warning("Could not seed %s — proceeding without historical data", sym)

    logger.info("Seed data ready for %d / %d symbols", fetched, len(SYMBOLS))


def get_seed_df(symbol: str) -> pd.DataFrame:
    """Return the cached historical DataFrame for *symbol* (may be empty)."""
    return SEED_DATA.get(symbol, pd.DataFrame())
