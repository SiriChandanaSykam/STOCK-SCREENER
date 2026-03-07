"""
screener_engine.py — Indicator calculation and 6-criteria filter logic.

For each symbol the engine:
  1. Retrieves the historical seed DataFrame (from historical_data.py)
  2. Appends the latest live price/volume from the WebSocket tick store
  3. Calculates RSI(14), EMA(50), 20-day average volume, and 52-week high
     using pandas-ta
  4. Applies ALL 6 filter criteria simultaneously
  5. Returns a list of passing symbols with their computed metrics

Imports are done lazily so the module can be imported for unit testing even
when optional dependencies (pandas-ta, NorenRestApiPy) are not installed.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta  # type: ignore[import]
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

from config import (
    SYMBOLS,
    PRICE_MIN,
    PRICE_MAX,
    AVG_VOLUME_MIN,
    VOLUME_SURGE_MULTIPLIER,
    RSI_MIN,
    RSI_MAX,
    RSI_PERIOD,
    EMA_PERIOD,
    VOLUME_AVG_PERIOD,
    WEEK52_PERIOD,
)
from data_ingestion import get_latest_tick, get_cumulative_volume
from historical_data import get_seed_df

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _append_live_row(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Append a synthetic 'today' row built from the latest WebSocket tick
    so that indicators reflect the current price and cumulative volume.
    """
    tick = get_latest_tick(symbol)
    if not tick:
        return df

    ltp = tick.get("ltp", 0.0)
    cum_vol = get_cumulative_volume(symbol)

    if ltp <= 0:
        return df

    today = pd.Timestamp.now().normalize()

    new_row = pd.DataFrame([{
        "date": today,
        "open": ltp,
        "high": ltp,
        "low": ltp,
        "close": ltp,
        "volume": cum_vol,
    }])

    # Replace the last row if it already has today's date; otherwise append
    if not df.empty and df.iloc[-1]["date"] == today:
        df = df.iloc[:-1].copy()

    df = pd.concat([df, new_row], ignore_index=True)
    return df


def _calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Run pandas-ta calculations on *df* and return a dict of indicator values.
    Returns an empty dict if the DataFrame is too short or pandas-ta is missing.
    """
    if df.empty or len(df) < EMA_PERIOD:
        return {}

    if not TA_AVAILABLE:
        logger.warning("pandas-ta not installed — falling back to manual calculations.")
        return _calculate_indicators_manual(df)

    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    # RSI
    rsi_series = ta.rsi(close, length=RSI_PERIOD)
    rsi = float(rsi_series.iloc[-1]) if rsi_series is not None and not rsi_series.empty else None

    # EMA(50)
    ema_series = ta.ema(close, length=EMA_PERIOD)
    ema50 = float(ema_series.iloc[-1]) if ema_series is not None and not ema_series.empty else None

    # 20-day average volume
    avg_vol_series = volume.rolling(VOLUME_AVG_PERIOD).mean()
    avg_vol_20 = float(avg_vol_series.iloc[-1]) if not avg_vol_series.empty else None

    # 52-week high (rolling max of close over WEEK52_PERIOD bars)
    high52_series = close.rolling(WEEK52_PERIOD, min_periods=min(WEEK52_PERIOD, len(df))).max()
    high52 = float(high52_series.iloc[-1]) if not high52_series.empty else None

    return {
        "rsi": rsi,
        "ema50": ema50,
        "avg_vol_20": avg_vol_20,
        "high52": high52,
    }


def _calculate_indicators_manual(df: pd.DataFrame) -> Dict[str, Any]:
    """Fallback indicator calculation without pandas-ta."""
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    # RSI (Wilder's smoothing via ewm)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    avg_loss_safe = avg_loss.replace(0, 1e-10)
    rs = avg_gain / avg_loss_safe
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1])

    # EMA(50)
    ema_series = close.ewm(span=EMA_PERIOD, min_periods=EMA_PERIOD).mean()
    ema50 = float(ema_series.iloc[-1])

    # 20-day average volume
    avg_vol_20 = float(volume.rolling(VOLUME_AVG_PERIOD).mean().iloc[-1])

    # 52-week high — use same min_periods as the pandas-ta version
    high52 = float(close.rolling(WEEK52_PERIOD, min_periods=min(WEEK52_PERIOD, len(df))).max().iloc[-1])

    return {
        "rsi": rsi,
        "ema50": ema50,
        "avg_vol_20": avg_vol_20,
        "high52": high52,
    }


# ---------------------------------------------------------------------------
# Public screening function
# ---------------------------------------------------------------------------

def run_screener() -> List[Dict[str, Any]]:
    """
    Evaluate every symbol in config.SYMBOLS against all 6 filter criteria.

    Returns a list of dicts for symbols that pass ALL criteria, each dict
    containing the metrics needed by the risk manager and dashboard.
    """
    passing: List[Dict[str, Any]] = []

    for sym in SYMBOLS:
        try:
            result = _screen_symbol(sym)
            if result is not None:
                passing.append(result)
        except Exception as exc:
            logger.error("Screener error for %s: %s", sym, exc)

    logger.info("Screener run complete: %d / %d symbols passed", len(passing), len(SYMBOLS))
    return passing


def _screen_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Screen a single symbol.  Returns a metrics dict if ALL 6 criteria are
    met, or None otherwise.
    """
    # --- Build DataFrame ---------------------------------------------------
    df = get_seed_df(symbol).copy()
    df = _append_live_row(df, symbol)

    if df.empty:
        logger.debug("%s: no data available — skipping", symbol)
        return None

    # --- Current price & volume -------------------------------------------
    current_price = float(df["close"].iloc[-1])
    cum_vol = get_cumulative_volume(symbol)

    # --- Indicators -------------------------------------------------------
    indicators = _calculate_indicators(df)
    if not indicators:
        logger.debug("%s: indicators could not be computed — skipping", symbol)
        return None

    rsi = indicators.get("rsi")
    ema50 = indicators.get("ema50")
    avg_vol_20 = indicators.get("avg_vol_20")
    high52 = indicators.get("high52")

    if any(v is None for v in [rsi, ema50, avg_vol_20, high52]):
        logger.debug("%s: incomplete indicators — skipping", symbol)
        return None

    # -----------------------------------------------------------------------
    # 6-criteria filter
    # -----------------------------------------------------------------------
    criteria = {
        "price_range": PRICE_MIN <= current_price <= PRICE_MAX,
        "avg_volume": avg_vol_20 > AVG_VOLUME_MIN,
        "volume_surge": (avg_vol_20 > 0 and cum_vol > VOLUME_SURGE_MULTIPLIER * avg_vol_20),
        "rsi_range": RSI_MIN < rsi < RSI_MAX,
        "above_ema": current_price > ema50,
        "near_52w_high": high52 > 0 and current_price >= 0.98 * high52,
    }

    criteria_met = sum(criteria.values())

    if criteria_met < 6:
        # Return partial data for yellow-row highlighting (5/6 met)
        if criteria_met == 5:
            return {
                "symbol": symbol,
                "ltp": current_price,
                "rsi": rsi,
                "ema50": ema50,
                "avg_vol_20": avg_vol_20,
                "cum_vol": cum_vol,
                "high52": high52,
                "criteria_met": criteria_met,
                "all_pass": False,
            }
        return None

    return {
        "symbol": symbol,
        "ltp": current_price,
        "rsi": rsi,
        "ema50": ema50,
        "avg_vol_20": avg_vol_20,
        "cum_vol": cum_vol,
        "high52": high52,
        "criteria_met": criteria_met,
        "all_pass": True,
    }
