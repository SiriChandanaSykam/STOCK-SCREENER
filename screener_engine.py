"""
screener_engine.py - Indicator calculation and screening logic.

The ORIGINAL engine preserves the existing 6-criteria micro-cap filter.
Additional institutional engines can be run independently or together via
run_screener(engine="ALL").
"""

import logging
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

try:
    import pandas_ta as ta  # type: ignore[import]
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

from config import (
    AVG_VOLUME_MIN,
    EMA_PERIOD,
    EMA200_PERIOD,
    ENGINE_NAMES,
    HIGH10_PERIOD,
    HIGH5_PERIOD,
    LOW10_PERIOD,
    LOW5_PERIOD,
    PRICE_MAX,
    PRICE_MIN,
    RSI_MAX,
    RSI_MIN,
    RSI_PERIOD,
    RUPEE_TURNOVER_FLOORS,
    SMA20_PERIOD,
    SMA50_PERIOD,
    SYMBOLS,
    VOLUME_AVG_PERIOD,
    VOLUME_SURGE_MULTIPLIER,
    WEEK52_PERIOD,
)
try:
    from data_ingestion import get_cumulative_volume, get_latest_tick
except ImportError:
    def get_latest_tick(symbol: str) -> Dict[str, Any]:
        return {}

    def get_cumulative_volume(symbol: str) -> float:
        return 0.0

from historical_data import get_seed_df

logger = logging.getLogger(__name__)

ENGINE_FUNCTIONS: Dict[str, Callable[[str, pd.DataFrame, float, Dict[str, Any]], Optional[Dict[str, Any]]]]


def _append_live_row(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Append a synthetic current-day row from the latest WebSocket tick.
    """
    tick = get_latest_tick(symbol)
    if not tick:
        return df

    ltp = float(tick.get("ltp", 0.0) or 0.0)
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

    if not df.empty and "date" in df.columns and df.iloc[-1]["date"] == today:
        df = df.iloc[:-1].copy()

    return pd.concat([df, new_row], ignore_index=True)


def _calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate all indicators needed by ORIGINAL and institutional engines.
    """
    if df.empty or len(df) < EMA_PERIOD:
        return {}

    if not TA_AVAILABLE:
        logger.warning("pandas-ta not installed - falling back to manual calculations.")
        return _calculate_indicators_manual(df)

    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    rsi_series = ta.rsi(close, length=RSI_PERIOD)
    ema50_series = ta.ema(close, length=EMA_PERIOD)
    ema200_series = ta.ema(close, length=EMA200_PERIOD)
    sma20_series = ta.sma(close, length=SMA20_PERIOD)
    sma50_series = ta.sma(close, length=SMA50_PERIOD)

    return {
        "rsi": _last_float(rsi_series),
        "ema50": _last_float(ema50_series),
        "ema200": _last_float(ema200_series),
        "sma20": _last_float(sma20_series),
        "sma50": _last_float(sma50_series),
        "avg_vol_20": _last_float(volume.rolling(VOLUME_AVG_PERIOD).mean()),
        "high52": _last_float(close.rolling(WEEK52_PERIOD, min_periods=min(WEEK52_PERIOD, len(df))).max()),
        "high10": _last_float(close.rolling(HIGH10_PERIOD, min_periods=HIGH10_PERIOD).max()),
        "low10": _last_float(close.rolling(LOW10_PERIOD, min_periods=LOW10_PERIOD).min()),
        "high5": _last_float(close.rolling(HIGH5_PERIOD, min_periods=HIGH5_PERIOD).max()),
        "low5": _last_float(close.rolling(LOW5_PERIOD, min_periods=LOW5_PERIOD).min()),
        "open_price": float(df["open"].iloc[-1]),
        "candle_high": float(df["high"].iloc[-1]),
        "candle_low": float(df["low"].iloc[-1]),
    }


def _calculate_indicators_manual(df: pd.DataFrame) -> Dict[str, Any]:
    """Fallback indicator calculation without pandas-ta."""
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))

    return {
        "rsi": _last_float(rsi),
        "ema50": _last_float(close.ewm(span=EMA_PERIOD, min_periods=EMA_PERIOD).mean()),
        "ema200": _last_float(close.ewm(span=EMA200_PERIOD, min_periods=EMA200_PERIOD).mean()),
        "sma20": _last_float(close.rolling(SMA20_PERIOD, min_periods=SMA20_PERIOD).mean()),
        "sma50": _last_float(close.rolling(SMA50_PERIOD, min_periods=SMA50_PERIOD).mean()),
        "avg_vol_20": _last_float(volume.rolling(VOLUME_AVG_PERIOD).mean()),
        "high52": _last_float(close.rolling(WEEK52_PERIOD, min_periods=min(WEEK52_PERIOD, len(df))).max()),
        "high10": _last_float(close.rolling(HIGH10_PERIOD, min_periods=HIGH10_PERIOD).max()),
        "low10": _last_float(close.rolling(LOW10_PERIOD, min_periods=LOW10_PERIOD).min()),
        "high5": _last_float(close.rolling(HIGH5_PERIOD, min_periods=HIGH5_PERIOD).max()),
        "low5": _last_float(close.rolling(LOW5_PERIOD, min_periods=LOW5_PERIOD).min()),
        "open_price": float(df["open"].iloc[-1]),
        "candle_high": float(df["high"].iloc[-1]),
        "candle_low": float(df["low"].iloc[-1]),
    }


def _last_float(series: Any) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def run_screener(engine: str = "ORIGINAL") -> List[Dict[str, Any]]:
    """
    Evaluate config.SYMBOLS against the selected screening engine.

    engine="ORIGINAL" preserves the existing 6-criteria behavior.
    engine="ALL" runs ORIGINAL and all institutional engines, deduplicating
    by symbol and merging engine names.
    """
    engine = (engine or "ORIGINAL").upper()
    valid_engines = set(ENGINE_NAMES) | {"ALL"}
    if engine not in valid_engines:
        raise ValueError(f"Unknown screening engine: {engine}")

    passing: List[Dict[str, Any]] = []
    for sym in SYMBOLS:
        try:
            if engine == "ORIGINAL":
                result = _screen_symbol(sym)
            else:
                result = _screen_symbol_with_engine(sym, engine)
            if result is not None:
                passing.append(result)
        except Exception as exc:
            logger.error("Screener error for %s: %s", sym, exc)

    logger.info("Screener run complete: %d / %d symbols passed", len(passing), len(SYMBOLS))
    return passing


def _screen_symbol_with_engine(symbol: str, engine: str) -> Optional[Dict[str, Any]]:
    df, cum_vol, indicators = _prepare_symbol(symbol)
    if df is None or not indicators:
        return None

    if engine == "ALL":
        results: List[Dict[str, Any]] = []
        original = _screen_prepared_original(symbol, df, cum_vol, indicators)
        if original is not None:
            results.append(original)
        for name, fn in ENGINE_FUNCTIONS.items():
            result = fn(symbol, df, cum_vol, indicators)
            if result is not None:
                results.append(result)
        return _merge_engine_results(results)

    if engine in ENGINE_FUNCTIONS:
        return ENGINE_FUNCTIONS[engine](symbol, df, cum_vol, indicators)

    return _screen_prepared_original(symbol, df, cum_vol, indicators)


def _screen_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Screen a single symbol with the existing ORIGINAL 6-criteria filter.
    """
    df, cum_vol, indicators = _prepare_symbol(symbol)
    if df is None or not indicators:
        return None
    return _screen_prepared_original(symbol, df, cum_vol, indicators)


def _prepare_symbol(symbol: str) -> tuple[Optional[pd.DataFrame], float, Dict[str, Any]]:
    df = get_seed_df(symbol).copy()
    df = _append_live_row(df, symbol)

    if df.empty:
        logger.debug("%s: no data available - skipping", symbol)
        return None, 0.0, {}

    cum_vol = float(get_cumulative_volume(symbol) or df["volume"].iloc[-1] or 0.0)
    indicators = _calculate_indicators(df)
    if not indicators:
        logger.debug("%s: indicators could not be computed - skipping", symbol)
    return df, cum_vol, indicators


def _screen_prepared_original(
    symbol: str,
    df: pd.DataFrame,
    cum_vol: float,
    indicators: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    current_price = float(df["close"].iloc[-1])
    rsi = indicators.get("rsi")
    ema50 = indicators.get("ema50")
    avg_vol_20 = indicators.get("avg_vol_20")
    high52 = indicators.get("high52")

    if any(v is None for v in [rsi, ema50, avg_vol_20, high52]):
        logger.debug("%s: incomplete indicators - skipping", symbol)
        return None

    criteria = {
        "price_range": PRICE_MIN <= current_price <= PRICE_MAX,
        "avg_volume": avg_vol_20 > AVG_VOLUME_MIN,
        "volume_surge": avg_vol_20 > 0 and cum_vol > VOLUME_SURGE_MULTIPLIER * avg_vol_20,
        "rsi_range": RSI_MIN < rsi < RSI_MAX,
        "above_ema": current_price > ema50,
        "near_52w_high": high52 > 0 and current_price >= 0.98 * high52,
    }
    criteria_met = sum(criteria.values())

    if criteria_met < 6:
        if criteria_met == 5:
            return _standard_result(symbol, "ORIGINAL", current_price, cum_vol, indicators, criteria_met, False)
        return None

    return _standard_result(symbol, "ORIGINAL", current_price, cum_vol, indicators, criteria_met, True)


def _standard_result(
    symbol: str,
    engine: str,
    ltp: float,
    cum_vol: float,
    indicators: Dict[str, Any],
    criteria_met: int,
    all_pass: bool,
) -> Dict[str, Any]:
    avg_vol_20 = float(indicators.get("avg_vol_20") or 0.0)
    open_price = float(indicators.get("open_price") or ltp)
    return {
        "symbol": symbol,
        "engine": engine,
        "ltp": ltp,
        "rsi": indicators.get("rsi"),
        "ema50": indicators.get("ema50"),
        "ema200": indicators.get("ema200"),
        "sma20": indicators.get("sma20"),
        "sma50": indicators.get("sma50"),
        "avg_vol_20": avg_vol_20,
        "cum_vol": cum_vol,
        "high52": indicators.get("high52"),
        "high10": indicators.get("high10"),
        "low10": indicators.get("low10"),
        "high5": indicators.get("high5"),
        "low5": indicators.get("low5"),
        "open_price": open_price,
        "candle_high": indicators.get("candle_high"),
        "candle_low": indicators.get("candle_low"),
        "criteria_met": criteria_met,
        "all_pass": all_pass,
        "rupee_turnover": ltp * cum_vol,
        "candle_body_pct": ((ltp - open_price) / open_price) * 100 if open_price > 0 else 0.0,
        "volume_surge_x": cum_vol / avg_vol_20 if avg_vol_20 > 0 else 0.0,
    }


def _engine_result(symbol: str, engine: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Dict[str, Any]:
    return _standard_result(symbol, engine, float(df["close"].iloc[-1]), cum_vol, indicators, 0, True)


def _base_values(df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, float]]:
    values = {
        "ltp": float(df["close"].iloc[-1]),
        "rsi": indicators.get("rsi"),
        "ema50": indicators.get("ema50"),
        "ema200": indicators.get("ema200"),
        "sma20": indicators.get("sma20"),
        "sma50": indicators.get("sma50"),
        "avg_vol_20": indicators.get("avg_vol_20"),
        "high52": indicators.get("high52"),
        "high10": indicators.get("high10"),
        "low10": indicators.get("low10"),
        "high5": indicators.get("high5"),
        "low5": indicators.get("low5"),
        "open_price": indicators.get("open_price"),
        "candle_high": indicators.get("candle_high"),
        "candle_low": indicators.get("candle_low"),
        "cum_vol": float(cum_vol),
    }
    if any(value is None for value in values.values()):
        return None
    return {key: float(value) for key, value in values.items()}


def _passes_turnover(engine: str, ltp: float, cum_vol: float) -> bool:
    return ltp * cum_vol > RUPEE_TURNOVER_FLOORS[engine]


def _screen_macro_floor(symbol: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = _base_values(df, cum_vol, indicators)
    if not v or not _passes_turnover("MACRO_FLOOR", v["ltp"], v["cum_vol"]):
        return None
    if (
        PRICE_MIN <= v["ltp"] <= 500
        and v["cum_vol"] > 1_500_000
        and v["candle_low"] <= v["ema200"]
        and v["ltp"] > v["ema200"]
        and v["ltp"] > v["ema50"]
        and v["ltp"] >= v["open_price"] * 1.04
        and v["ltp"] >= v["candle_high"] * 0.97
        and v["cum_vol"] > v["avg_vol_20"] * 2.0
    ):
        return _engine_result(symbol, "MACRO_FLOOR", df, cum_vol, indicators)
    return None


def _screen_kinetic_squeeze(symbol: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = _base_values(df, cum_vol, indicators)
    if not v or not _passes_turnover("KINETIC_SQUEEZE", v["ltp"], v["cum_vol"]):
        return None
    if (
        PRICE_MIN <= v["ltp"] <= 500
        and v["cum_vol"] > 2_000_000
        and v["ltp"] > v["sma20"]
        and v["ltp"] > v["ema50"]
        and v["cum_vol"] > v["avg_vol_20"] * 2.5
        and v["ltp"] >= v["high10"]
        and 60 < v["rsi"] < 80
        and v["ltp"] >= v["open_price"] * 1.02
    ):
        return _engine_result(symbol, "KINETIC_SQUEEZE", df, cum_vol, indicators)
    return None


def _screen_stealth_accumulation(symbol: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = _base_values(df, cum_vol, indicators)
    if not v or not _passes_turnover("STEALTH_ACCUMULATION", v["ltp"], v["cum_vol"]):
        return None
    if (
        PRICE_MIN <= v["ltp"] <= 500
        and v["avg_vol_20"] > 500_000
        and v["cum_vol"] > v["avg_vol_20"] * 1.5
        and v["ltp"] > v["open_price"]
        and v["ltp"] <= v["open_price"] * 1.03
        and v["high10"] <= v["low10"] * 1.10
        and v["ltp"] > v["sma50"]
        and 45 < v["rsi"] < 65
    ):
        return _engine_result(symbol, "STEALTH_ACCUMULATION", df, cum_vol, indicators)
    return None


def _screen_btst(symbol: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = _base_values(df, cum_vol, indicators)
    if not v or not _passes_turnover("BTST", v["ltp"], v["cum_vol"]):
        return None
    if (
        50 <= v["ltp"] <= 500
        and v["cum_vol"] > 2_000_000
        and v["ltp"] >= v["candle_high"] * 0.995
        and v["ltp"] >= v["open_price"] * 1.05
        and v["cum_vol"] > v["avg_vol_20"] * 2.0
        and v["ltp"] > v["sma20"]
        and v["ltp"] >= v["high52"] * 0.70
        and v["rsi"] > 55
    ):
        return _engine_result(symbol, "BTST", df, cum_vol, indicators)
    return None


def _screen_vcp_setup(symbol: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = _base_values(df, cum_vol, indicators)
    if not v or not _passes_turnover("VCP_SETUP", v["ltp"], v["cum_vol"]):
        return None
    if (
        50 <= v["ltp"] <= 500
        and v["cum_vol"] > 500_000
        and v["ltp"] >= v["high52"] * 0.94
        and v["high5"] <= v["low5"] * 1.05
        and v["cum_vol"] <= v["avg_vol_20"] * 0.75
        and 50 < v["rsi"] < 65
    ):
        return _engine_result(symbol, "VCP_SETUP", df, cum_vol, indicators)
    return None


def _screen_vcp_breakout(symbol: str, df: pd.DataFrame, cum_vol: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = _base_values(df, cum_vol, indicators)
    if not v or not _passes_turnover("VCP_BREAKOUT", v["ltp"], v["cum_vol"]):
        return None
    if (
        50 <= v["ltp"] <= 500
        and v["cum_vol"] > 1_000_000
        and v["ltp"] >= v["high52"] * 0.95
        and v["ltp"] >= v["high10"] * 0.99
        and v["cum_vol"] > v["avg_vol_20"] * 2.0
        and v["rsi"] > 60
    ):
        return _engine_result(symbol, "VCP_BREAKOUT", df, cum_vol, indicators)
    return None


def _merge_engine_results(results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not results:
        return None

    full_pass = [row for row in results if row.get("all_pass", False)]
    candidates = full_pass or results
    merged = candidates[0].copy()
    engines: List[str] = []
    for row in candidates:
        for name in str(row.get("engine", "")).split(","):
            name = name.strip()
            if name and name not in engines:
                engines.append(name)
    merged["engine"] = ", ".join(engines)
    merged["all_pass"] = any(row.get("all_pass", False) for row in candidates)
    return merged


ENGINE_FUNCTIONS = {
    "MACRO_FLOOR": _screen_macro_floor,
    "KINETIC_SQUEEZE": _screen_kinetic_squeeze,
    "STEALTH_ACCUMULATION": _screen_stealth_accumulation,
    "BTST": _screen_btst,
    "VCP_SETUP": _screen_vcp_setup,
    "VCP_BREAKOUT": _screen_vcp_breakout,
}
