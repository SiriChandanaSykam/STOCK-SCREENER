"""
Aggressive Micro-Cap Momentum Screener for NSE/BSE
Scans Indian micro-cap stocks for momentum breakouts with full risk management.
"""

import time
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from utils.technicals import calculate_macd, calculate_rsi, calculate_smoothed_ma

st.set_page_config(page_title="Micro-Cap Screener", layout="wide")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SYMBOLS = (
    "SUZLON.NS, YESBANK.NS, IRFC.NS, NHPC.NS, RVNL.NS, HUDCO.NS, IREDA.NS, "
    "RECLTD.NS, PNBHOUSING.NS, MANAPPURAM.NS, MUTHOOTFIN.NS, IDFCFIRSTB.NS, "
    "BANDHANBNK.NS, CENTRALBK.NS, CANBK.NS, UNIONBANK.NS, UCOBANK.NS, "
    "BANKBARODA.NS, IOB.NS, MAHABANK.NS, INDIANB.NS, JKBANK.NS, "
    "SAIL.NS, NMDC.NS, NATIONALUM.NS, HINDALCO.NS, VEDL.NS, "
    "TATAPOWER.NS, ADANIPOWER.NS, NTPC.NS, RPOWER.NS, JPPOWER.NS, "
    "TRIDENT.NS, BOMDYEING.NS, JKTYRE.NS, APOLLOTYRE.NS, CEATLTD.NS, "
    "GNFC.NS, GSFC.NS, CHAMBLFERT.NS, DEEPAKNTR.NS, TATACHEM.NS, "
    "PCJEWELLER.NS, SENCO.NS, RAJESHEXPO.NS, "
    "IDEA.NS, GTLINFRA.NS, HFCL.NS, RAILTEL.NS, "
    "SJVN.NS, POWERGRID.NS, COALINDIA.NS"
)

# ---------------------------------------------------------------------------
# Thresholds / constants (tunable without hunting through logic)
# ---------------------------------------------------------------------------

CIRCUIT_PCT_THRESHOLD = 0.195       # ~20% circuit limit on NSE/BSE micro-caps
CONSOLIDATION_RANGE_PCT = 8.0       # max % range for tight-consolidation base
SINGLE_DAY_SWING_LIMIT = 0.15       # 15% max single-day move (manipulation flag)
VOLUME_DRY_UP_RATIO = 0.50          # last-3d avg < 50% of prior-5d avg → distribution
CANDLE_BODY_MAX_PCT = 0.08          # 8% max candle body for organic quality score
STOP_LOSS_FACTOR = 0.95             # strict 5% stop-loss
TAKE_PROFIT_FACTOR = 1.20           # 20% take-profit target

# ---------------------------------------------------------------------------
# Screening helpers
# ---------------------------------------------------------------------------


def _safe_float(val) -> float:
    """Convert a scalar or single-element array-like to a Python float."""
    if val is None:
        return float("nan")
    if isinstance(val, (int, float, np.floating, np.integer)):
        return float(val)
    try:
        return float(val)
    except Exception:
        return float("nan")


def _circuit_hits(df: pd.DataFrame, lookback: int = 5) -> int:
    """Return number of circuit-limit events in the last *lookback* sessions."""
    if len(df) < lookback + 1:
        return 0
    recent = df.tail(lookback + 1).copy()
    prev_close = recent["Close"].shift(1)
    pct_change = (recent["Close"] - prev_close).abs() / prev_close.abs()
    hits = int((pct_change >= CIRCUIT_PCT_THRESHOLD).sum())
    return hits


def _rsi_value(closes: np.ndarray, period: int = 14) -> float:
    rsi_arr = calculate_rsi(closes, period=period)
    return _safe_float(rsi_arr[-1])


def _macd_status(closes: np.ndarray) -> str:
    if len(closes) < 26:
        return "Neutral"
    macd_arr, signal_arr = calculate_macd(closes)
    macd_last = _safe_float(macd_arr[-1])
    signal_last = _safe_float(signal_arr[-1])
    macd_prev = _safe_float(macd_arr[-2]) if len(macd_arr) >= 2 else macd_last
    signal_prev = _safe_float(signal_arr[-2]) if len(signal_arr) >= 2 else signal_last
    if macd_prev <= signal_prev and macd_last > signal_last:
        return "Bullish Crossover"
    if macd_last > signal_last:
        return "Bullish"
    return "Neutral"


def _trend_status(closes: np.ndarray) -> str:
    sma20 = calculate_smoothed_ma(closes, window=20)
    sma50 = calculate_smoothed_ma(closes, window=50)
    price = _safe_float(closes[-1])
    s20 = _safe_float(sma20[-1])
    s50 = _safe_float(sma50[-1])
    if price > s20 > s50:
        return "Bull"
    if price < s20 or s20 < s50:
        return "Bear"
    return "Caution"


def _swing_quality_score(
    rsi: float,
    vol_ratio: float,
    df: pd.DataFrame,
    trend: str,
    circuit_hits_10: int,
) -> int:
    score = 0
    # +30 if RSI 60–75
    if 60 <= rsi <= 75:
        score += 30
    # +20 if volume 2x–6x (organic)
    if 2 <= vol_ratio < 6:
        score += 20
    # +20 if no single-day candle body > 8%
    if len(df) >= 10:
        recent = df.tail(10)
        bodies = ((recent["Close"] - recent["Open"]).abs() / recent["Open"]).max()
        if _safe_float(bodies) <= CANDLE_BODY_MAX_PCT:
            score += 20
    # +15 if price > SMA20 > SMA50
    if trend == "Bull":
        score += 15
    # +15 if no circuit in last 10 days
    if circuit_hits_10 == 0:
        score += 15
    return score


def _risk_category(rsi: float, vol_ratio: float, swing_score: int) -> str:
    if rsi <= 70 and 3 <= vol_ratio <= 5 and swing_score >= 80:
        return "LOW"
    if (70 < rsi <= 75 or 5 < vol_ratio <= 7) and 60 <= swing_score <= 79:
        return "MEDIUM"
    return "HIGH"


# ---------------------------------------------------------------------------
# Main screening function
# ---------------------------------------------------------------------------


def screen_stock(sym: str, min_swing_score: int, only_low_risk: bool):
    """
    Fetch and analyse a single stock.
    Returns a result dict on success, None if the stock fails any filter.
    Raises on data-fetch failure so the caller can show a warning.
    """
    ticker = yf.Ticker(sym)
    df = ticker.history(period="1y")
    if df is None or len(df) < 60:
        return None

    df = df.copy()
    closes = df["Close"].values.astype(float)
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    volumes = df["Volume"].values.astype(float)

    current_price = _safe_float(closes[-1])

    # ── 1. Price range ──────────────────────────────────────────────────────
    if not (20 <= current_price <= 150):
        return None

    # ── 2. Liquidity (1-month avg daily vol > 1 000 000) ───────────────────
    vol_1m = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
    if vol_1m <= 1_000_000:
        return None

    # ── 3. Momentum ignition (today vol > 3× 20-day avg) ───────────────────
    avg_vol_20 = (
        float(np.mean(volumes[-21:-1])) if len(volumes) >= 21
        else float(np.mean(volumes[:-1]))
    )
    if avg_vol_20 == 0:
        return None
    vol_ratio = _safe_float(volumes[-1]) / avg_vol_20
    if vol_ratio < 3:
        return None

    # ── 4. RSI filter (60–80) ───────────────────────────────────────────────
    rsi = _rsi_value(closes, period=14)
    if not (60 <= rsi <= 80):
        return None

    # ── 5. Price action ─────────────────────────────────────────────────────
    high_52w = float(np.max(highs))
    near_52w_high = (high_52w - current_price) / high_52w <= 0.02

    consolidation_breakout = False
    if len(df) >= 20:
        past20_high = float(np.max(highs[-21:-1]))
        past20_low = float(np.min(lows[-21:-1]))
        range_pct = (past20_high - past20_low) / past20_low * 100 if past20_low > 0 else 999.0
        consolidation_breakout = (
            range_pct <= CONSOLIDATION_RANGE_PCT and current_price > past20_high
        )

    if not (near_52w_high or consolidation_breakout):
        return None

    breakout_type = "52W High Breakout" if near_52w_high else "Consolidation Base Breakout"

    # ── 6. Circuit filter (last 5 sessions) ─────────────────────────────────
    circuit_5d = _circuit_hits(df, lookback=5)
    if circuit_5d > 0:
        return None

    # ── Manipulation / trap filters ─────────────────────────────────────────
    # 6a. Extreme pump: 5-day avg > 5× 20-day avg
    avg_vol_5d = float(np.mean(volumes[-5:])) if len(volumes) >= 5 else float(np.mean(volumes))
    if avg_vol_20 > 0 and avg_vol_5d / avg_vol_20 > 5:
        return None

    # 6b. Single-day swing > 15% in last 10 sessions
    if len(df) >= 11:
        recent10_close = closes[-11:]
        daily_swings = np.abs(np.diff(recent10_close) / recent10_close[:-1])
        if float(np.max(daily_swings)) > SINGLE_DAY_SWING_LIMIT:
            return None

    # 6c. Volume drying up after run (distribution signal)
    if len(volumes) >= 8:
        last3_avg = float(np.mean(volumes[-3:]))
        prior5_avg = float(np.mean(volumes[-8:-3]))
        if prior5_avg > 0 and last3_avg < VOLUME_DRY_UP_RATIO * prior5_avg:
            return None

    # ── Swing quality score ──────────────────────────────────────────────────
    circuit_10d = _circuit_hits(df, lookback=10)
    trend = _trend_status(closes)
    swing_score = _swing_quality_score(rsi, vol_ratio, df, trend, circuit_10d)
    if swing_score < min_swing_score:
        return None

    # ── Risk category ────────────────────────────────────────────────────────
    risk = _risk_category(rsi, vol_ratio, swing_score)
    if only_low_risk and risk != "LOW":
        return None

    # ── Risk management levels ───────────────────────────────────────────────
    stop_loss = current_price * STOP_LOSS_FACTOR
    support_level = float(np.min(lows[-10:])) if len(lows) >= 10 else stop_loss
    # Always use the strict 5% stop-loss
    effective_stop = stop_loss

    take_profit = current_price * TAKE_PROFIT_FACTOR

    # Nearest historical resistance: highest 52W high above current price
    highs_above = highs[highs > current_price]
    nearest_resistance = float(np.min(highs_above)) if len(highs_above) > 0 else take_profit

    rr_ratio = (take_profit - current_price) / max(current_price - effective_stop, 0.01)

    # ── Additional intelligence ──────────────────────────────────────────────
    macd_status = _macd_status(closes)
    sma20 = calculate_smoothed_ma(closes, window=20)
    sma50 = calculate_smoothed_ma(closes, window=50)

    return {
        "symbol": sym,
        "current_price": current_price,
        "breakout_type": breakout_type,
        "risk": risk,
        "swing_score": swing_score,
        "stop_loss": effective_stop,
        "support_level": support_level,
        "take_profit": take_profit,
        "nearest_resistance": nearest_resistance,
        "rr_ratio": rr_ratio,
        "rsi": rsi,
        "vol_today": _safe_float(volumes[-1]),
        "vol_ratio": vol_ratio,
        "trend": trend,
        "macd_status": macd_status,
        "circuit_hits_5d": circuit_5d,
        "df": df,
        "sma20": sma20,
        "sma50": sma50,
        "closes": closes,
    }


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------


def build_chart(result: dict) -> go.Figure:
    df = result["df"].tail(60).copy()
    sma20 = result["sma20"][-60:]
    sma50 = result["sma50"][-60:]
    closes_full = result["closes"]
    rsi_arr = calculate_rsi(closes_full, period=14)[-60:]

    dates = df.index
    opens = df["Open"].values
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values
    volumes = df["Volume"].values

    colors = [
        "rgba(0,200,0,0.7)" if c >= o else "rgba(200,0,0,0.7)"
        for c, o in zip(closes, opens)
    ]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.20, 0.25],
        vertical_spacing=0.04,
        subplot_titles=("Price", "Volume", "RSI(14)"),
    )

    # Candlesticks
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="Price",
            increasing_line_color="#00c800",
            decreasing_line_color="#c80000",
        ),
        row=1,
        col=1,
    )

    # SMAs
    fig.add_trace(
        go.Scatter(x=dates, y=sma20, name="SMA20", line=dict(color="orange", width=1.5)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=dates, y=sma50, name="SMA50", line=dict(color="purple", width=1.5)),
        row=1,
        col=1,
    )

    # Stop-loss and take-profit lines
    fig.add_hline(
        y=result["stop_loss"],
        line=dict(color="red", dash="dash", width=1.5),
        annotation_text=f"SL ₹{result['stop_loss']:.2f}",
        annotation_position="bottom right",
        row=1,
        col=1,
    )
    fig.add_hline(
        y=result["take_profit"],
        line=dict(color="green", dash="dash", width=1.5),
        annotation_text=f"TP ₹{result['take_profit']:.2f}",
        annotation_position="top right",
        row=1,
        col=1,
    )

    # Volume bars
    fig.add_trace(
        go.Bar(x=dates, y=volumes, name="Volume", marker_color=colors, showlegend=False),
        row=2,
        col=1,
    )

    # RSI
    fig.add_trace(
        go.Scatter(x=dates, y=rsi_arr, name="RSI(14)", line=dict(color="cyan", width=1.5)),
        row=3,
        col=1,
    )
    fig.add_hline(y=70, line=dict(color="red", dash="dot", width=1), row=3, col=1)
    fig.add_hline(y=60, line=dict(color="green", dash="dot", width=1), row=3, col=1)
    fig.add_hline(y=30, line=dict(color="gray", dash="dot", width=1), row=3, col=1)

    fig.update_layout(
        height=600,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=20),
        legend=dict(orientation="h", y=1.02),
    )
    return fig


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🔥 Micro-Cap Aggressive Momentum Screener")
st.markdown(
    "Scans NSE/BSE micro-cap stocks for high-probability swing trade setups "
    "with strict risk management and manipulation filters."
)

# Sidebar
with st.sidebar:
    st.header("⚙️ Screener Controls")
    raw_symbols = st.text_area(
        "Stock Symbols (comma-separated)",
        value=DEFAULT_SYMBOLS,
        height=200,
        help="Use NSE `.NS` or BSE `.BO` suffixes",
    )
    run_btn = st.button("🚀 Run Aggressive Screener", type="primary", use_container_width=True)
    min_score = st.slider("Min Swing Quality Score", min_value=40, max_value=100, value=60, step=5)
    only_low = st.checkbox("Show only LOW risk stocks", value=False)

    st.markdown("---")
    st.markdown(
        "**Filters applied:**\n"
        "- Price ₹20–₹150\n"
        "- 1M avg vol > 10L\n"
        "- Today vol > 3× 20D avg\n"
        "- RSI(14) 60–80\n"
        "- 52W high or consolidation breakout\n"
        "- No circuit hit in last 5 sessions\n"
        "- Manipulation filters\n"
        f"- Swing Score ≥ {min_score}"
    )

if not run_btn:
    st.info("👈 Configure filters in the sidebar and click **Run Aggressive Screener** to begin.")
    st.stop()

# Parse symbols
symbols = [s.strip() for s in raw_symbols.replace("\n", ",").split(",") if s.strip()]
if not symbols:
    st.error("Please enter at least one stock symbol.")
    st.stop()

# ── Scan ──────────────────────────────────────────────────────────────────
start_ts = time.time()
results = []
warnings = []

progress_bar = st.progress(0, text="Initialising scan…")
status_text = st.empty()

for i, sym in enumerate(symbols):
    progress_pct = int((i + 1) / len(symbols) * 100)
    progress_bar.progress(progress_pct, text=f"Scanning {sym} ({i+1}/{len(symbols)})…")
    status_text.text(f"Processing: {sym}")

    try:
        result = screen_stock(sym, min_score, only_low)
        if result is not None:
            results.append(result)
    except Exception as exc:
        warnings.append(f"⚠️ Could not process {sym}: {exc}")

    time.sleep(0.05)

progress_bar.empty()
status_text.empty()

elapsed = time.time() - start_ts

# ── Summary bar ───────────────────────────────────────────────────────────
st.success(
    f"✅ **{len(results)} stocks matched** out of {len(symbols)} scanned "
    f"| Scan time: {elapsed:.1f}s"
)

for w in warnings:
    st.warning(w)

if not results:
    st.info(
        "No stocks matched all criteria. Try lowering the Min Swing Quality Score "
        "or adding more symbols."
    )
    st.stop()

# Sort by swing score descending
results.sort(key=lambda r: r["swing_score"], reverse=True)

# ── Result cards ──────────────────────────────────────────────────────────
RISK_BADGE = {"LOW": "🟢 LOW", "MEDIUM": "🟡 MEDIUM", "HIGH": "🔴 HIGH"}

for res in results:
    sym = res["symbol"]
    risk_label = RISK_BADGE.get(res["risk"], res["risk"])
    header = f"{sym}  |  ₹{res['current_price']:.2f}  |  {res['breakout_type']}  |  {risk_label}"

    with st.expander(header, expanded=False):
        col_score, col_badge = st.columns([3, 1])
        with col_score:
            st.markdown(f"**Swing Quality Score: {res['swing_score']}/100**")
            st.progress(res["swing_score"] / 100)
        with col_badge:
            st.markdown(f"### {risk_label}")

        # Metrics table
        metrics_data = {
            "Metric": [
                "Current Price",
                "Stop Loss (5%)",
                "Support Level",
                "Take Profit (20%)",
                "Nearest Resistance",
                "Risk : Reward",
                "RSI(14)",
                "Volume (today)",
                "Vol vs 20D Avg",
                "Trend",
                "MACD",
                "Breakout Type",
                "Circuit Hits (5D)",
            ],
            "Value": [
                f"₹{res['current_price']:.2f}",
                f"₹{res['stop_loss']:.2f}",
                f"₹{res['support_level']:.2f}",
                f"₹{res['take_profit']:.2f}",
                f"₹{res['nearest_resistance']:.2f}",
                f"{res['rr_ratio']:.1f} : 1",
                f"{res['rsi']:.1f}",
                f"{res['vol_today'] / 1e6:.2f}M",
                f"{res['vol_ratio']:.1f}x",
                res["trend"],
                res["macd_status"],
                res["breakout_type"],
                str(res["circuit_hits_5d"]),
            ],
        }
        st.table(pd.DataFrame(metrics_data).set_index("Metric"))

        # Chart
        try:
            fig = build_chart(res)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as chart_err:
            st.warning(f"Chart could not be rendered: {chart_err}")

# ── Risk Management Summary ───────────────────────────────────────────────
st.markdown("---")
st.subheader("🛡️ Risk Management Summary")

col1, col2 = st.columns(2)
with col1:
    st.info(
        "**Capital Allocation Rule**\n\n"
        "Never allocate more than **2%** of your portfolio to any single micro-cap stock."
    )
with col2:
    st.info(
        "**Position Sizing Formula**\n\n"
        "`Position Size = (Portfolio × 0.02) / (Entry Price − Stop Loss)`\n\n"
        "Example: ₹5,00,000 portfolio, Entry ₹50, SL ₹47.50 → "
        "Position Size = (5,00,000 × 0.02) / 2.50 = **4,000 shares**"
    )

st.warning(
    "⚠️ **Micro-cap stocks are HIGH RISK.** These are swing trade setups only. "
    "Always use strict stop-losses. Past patterns do not guarantee future performance. "
    "This tool is for educational and informational purposes only — not financial advice."
)
