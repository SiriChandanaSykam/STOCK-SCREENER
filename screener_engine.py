# screener_engine.py — Indicator calculation + 6-layer filter logic

import logging
import pandas as pd
import pandas_ta as ta
from config import (
    SYMBOLS, PRICE_MIN, PRICE_MAX, AVG_VOLUME_MIN,
    VOLUME_SURGE_MULTIPLIER, RSI_MIN, RSI_MAX,
    RSI_PERIOD, EMA_PERIOD, VOLUME_AVG_PERIOD, WEEK52_PERIOD
)
from historical_data import seed_data
from data_ingestion import tick_store

logger = logging.getLogger(__name__)


def get_latest_ltp(symbol: str) -> float:
    deq = tick_store.get(symbol)
    if deq:
        return deq[-1]["ltp"]
    return 0.0


def get_live_volume(symbol: str) -> int:
    deq = tick_store.get(symbol)
    if deq:
        return deq[-1]["vol"]
    return 0


def compute_indicators(symbol: str) -> dict:
    """Compute RSI, EMA, AvgVol, 52W High for a symbol using seed + live data."""
    df = seed_data.get(symbol, pd.DataFrame())
    if df.empty or "close" not in df.columns:
        return {}

    ltp = get_latest_ltp(symbol)
    live_vol = get_live_volume(symbol)

    # Append today's live tick as the latest row
    if ltp > 0:
        latest_row = pd.DataFrame([{
            "close": ltp,
            "volume": live_vol,
            "high": ltp,
            "low": ltp,
            "open": ltp
        }])
        df = pd.concat([df, latest_row], ignore_index=True)

    close = df["close"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(dtype=float)

    # RSI
    rsi_series = ta.rsi(close, length=RSI_PERIOD)
    rsi = float(rsi_series.iloc[-1]) if rsi_series is not None and not rsi_series.empty else None

    # EMA(50)
    ema_series = ta.ema(close, length=EMA_PERIOD)
    ema = float(ema_series.iloc[-1]) if ema_series is not None and not ema_series.empty else None

    # 20-Day Average Volume
    avg_vol = float(volume.tail(VOLUME_AVG_PERIOD).mean()) if not volume.empty else 0.0

    # 52-Week High
    week52_high = float(close.tail(WEEK52_PERIOD).max()) if len(close) >= WEEK52_PERIOD else float(close.max())

    return {
        "symbol": symbol,
        "ltp": ltp,
        "rsi": rsi,
        "ema50": ema,
        "avg_vol_20d": avg_vol,
        "live_vol": live_vol,
        "week52_high": week52_high
    }


def run_screener() -> pd.DataFrame:
    """Run all 6 filters and return a DataFrame of passing stocks."""
    results = []
    for sym in SYMBOLS:
        try:
            ind = compute_indicators(sym)
            if not ind or ind["ltp"] <= 0:
                continue

            ltp = ind["ltp"]
            rsi = ind["rsi"]
            ema50 = ind["ema50"]
            avg_vol = ind["avg_vol_20d"]
            live_vol = ind["live_vol"]
            w52h = ind["week52_high"]

            if rsi is None or ema50 is None:
                continue

            # ── 6 Simultaneous Filters ──────────────────────────────
            f1 = PRICE_MIN <= ltp <= PRICE_MAX
            f2 = avg_vol > AVG_VOLUME_MIN
            f3 = live_vol > (VOLUME_SURGE_MULTIPLIER * avg_vol)
            f4 = RSI_MIN < rsi < RSI_MAX
            f5 = ltp > ema50
            f6 = ltp >= (0.98 * w52h)

            filters_met = sum([f1, f2, f3, f4, f5, f6])
            if filters_met < 5:
                continue  # Accept only stocks meeting 5 or 6 criteria

            results.append({
                "Ticker": sym,
                "LTP (₹)": round(ltp, 2),
                "RSI": round(rsi, 2),
                "EMA(50)": round(ema50, 2),
                "Avg Vol (20D)": int(avg_vol),
                "Live Vol": int(live_vol),
                "Vol Surge (x)": round(live_vol / avg_vol, 2) if avg_vol > 0 else 0,
                "52W High": round(w52h, 2),
                "% from High": round((ltp / w52h) * 100, 2) if w52h > 0 else 0,
                "All 6 Met": filters_met == 6,
                "_filters_met": filters_met
            })
        except Exception as e:
            logger.warning(f"Screener error for {sym}: {e}")

    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values("_filters_met", ascending=False)
        df_out = df_out.drop(columns=["_filters_met"])
    return df_out
