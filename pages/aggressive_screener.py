"""
pages/aggressive_screener.py

Aggressive Quantitative Screener — NSE Micro-Cap Momentum
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data source   : Shoonya (Finvasia) API — 100% live / no yfinance
Criteria      : 6 hard filters + anti-manipulation guard
Risk Mgmt     : ATR-based stop, support/resistance target, R:R ratio
Swing filter  : EMA trend + consolidation breakout detection
"""

import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyotp
import streamlit as st
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Micro-cap universe  (~70 NSE stocks typically in ₹20–₹150 range)
# ─────────────────────────────────────────────────────────────────────────────
MICRO_CAP_UNIVERSE = [
    # PSU Banks
    "YESBANK", "BANKINDIA", "IOB", "CENTRALBK", "MAHABANK",
    "CANBK", "UNIONBANK", "PSBBANK", "J&KBANK", "BANDHANBNK",
    # PSU Infra / Power Finance
    "RVNL", "IRFC", "IREDA", "SJVN", "NHPC", "PFC", "RECLTD",
    "IRCON", "RITES", "RAILTEL", "HUDCO", "NBCC",
    # Metals & Mining
    "NMDC", "SAIL", "NATIONALUM", "MOIL", "HINDCOPPER",
    # Renewable / Power
    "SUZLON", "RPOWER", "JPPOWER",
    # Fertilizers
    "NFL", "RCF", "GNFC", "GSFC", "CHAMBLFERT", "DEEPAKNTR",
    # Telecom
    "IDEA",
    # Sugar / Agri
    "BALRAMCHIN", "DHAMPUR", "TRIVENI", "DCMSHRIRAM",
    # Finance / NBFC
    "IFCI", "PNBHOUSING", "RBLBANK",
    # Others
    "COALINDIA", "GMRINFRA", "TRIDENT", "SPICEJET",
    "BEML", "BEL", "MTNL", "MMTC",
    "TATACOMM", "BFUTILITIE", "ORIENTPPR",
    "MANAPPURAM", "MUTHOOTFIN",
]

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aggressive Screener",
    layout="wide",
    page_icon="🎯",
)
st.title("🎯 Aggressive Micro-Cap Momentum Screener")
st.markdown(
    "**Shoonya Live Data &nbsp;|&nbsp; 6-Criteria Filter &nbsp;|&nbsp; "
    "Anti-Manipulation Guard &nbsp;|&nbsp; ATR-Based Risk Management**"
)


# ─────────────────────────────────────────────────────────────────────────────
# Shoonya API — login once per session
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Connecting to Shoonya API…")
def get_shoonya_api():
    try:
        from NorenRestApiPy.NorenApi import NorenApi  # type: ignore[import]
    except ImportError:
        return None, "NorenRestApiPy not installed — run: pip install NorenRestApiPy"

    env_path = Path(__file__).resolve().parent.parent / "shoonya.env"
    load_dotenv(dotenv_path=env_path, override=True)

    uid        = os.getenv("SHOONYA_USER_ID", "")
    pwd        = os.getenv("SHOONYA_PASSWORD", "")
    totp_raw   = os.getenv("SHOONYA_TOTP_SECRET", "").replace("-", "").replace(" ", "").strip()
    vc         = os.getenv("SHOONYA_VENDOR_CODE", "")
    api_secret = os.getenv("SHOONYA_API_SECRET", "")
    imei       = os.getenv("SHOONYA_IMEI", "")

    twoFA = totp_raw if totp_raw.isdigit() else pyotp.TOTP(totp_raw.upper()).now()

    class _Api(NorenApi):
        def __init__(self):
            super().__init__(
                host="https://api.shoonya.com/NorenWClientTP/",
                websocket="wss://api.shoonya.com/NorenWSTP/",
            )

    api = _Api()
    ret = api.login(
        userid=uid, password=pwd, twoFA=twoFA,
        vendor_code=vc, api_secret=api_secret, imei=imei,
    )
    if ret and ret.get("stat") == "Ok":
        return api, f"✅ Logged in as **{ret.get('uname', uid)}** ({uid})"
    return None, f"❌ Login failed: {ret.get('emsg') if ret else 'No response'}"


# ─────────────────────────────────────────────────────────────────────────────
# Shoonya data helpers
# ─────────────────────────────────────────────────────────────────────────────
def resolve_token(api, symbol: str, exchange: str = "NSE"):
    """Return (token, lot_size) for a symbol, or (None, 0)."""
    try:
        resp = api.searchscrip(exchange=exchange, searchtext=symbol)
        if resp and resp.get("stat") == "Ok":
            values = resp.get("values", [])
            # Exact match first
            for item in values:
                if item.get("tsym") == symbol:
                    return item.get("token"), int(float(item.get("ls", 1) or 1))
            # Fallback: first result
            if values:
                return values[0].get("token"), int(float(values[0].get("ls", 1) or 1))
    except Exception:
        pass
    return None, 0


def fetch_ohlcv(api, token: str, exchange: str = "NSE", days: int = 290) -> pd.DataFrame:
    """Fetch daily OHLCV bars from Shoonya get_time_price_series."""
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=int(days * 1.5))
    try:
        raw = api.get_time_price_series(
            exchange=exchange,
            token=token,
            starttime=start_dt.strftime("%d-%m-%Y %H:%M:%S"),
            endtime=end_dt.strftime("%d-%m-%Y %H:%M:%S"),
            interval=1440,
        )
        if not isinstance(raw, list) or len(raw) == 0:
            return pd.DataFrame()

        rows = []
        for c in raw:
            try:
                rows.append({
                    "date":   pd.to_datetime(c.get("ssboe") or c.get("time"), unit="s"),
                    "open":   float(c.get("into", c.get("o", 0))),
                    "high":   float(c.get("inth", c.get("h", 0))),
                    "low":    float(c.get("intl", c.get("l", 0))),
                    "close":  float(c.get("intc", c.get("c", 0))),
                    "volume": int(c.get("intv", c.get("v", 0))),
                })
            except Exception:
                pass
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def fetch_live_quote(api, token: str, exchange: str = "NSE") -> dict:
    """Return live quote dict from Shoonya get_quotes."""
    try:
        q = api.get_quotes(exchange=exchange, token=token)
        if q and q.get("stat") == "Ok":
            return {
                "ltp":    float(q.get("lp", 0) or 0),
                "volume": int(q.get("v",  0) or 0),
                "h52":    float(q.get("h52", 0) or 0),
                "l52":    float(q.get("l52", 0) or 0),
                "high":   float(q.get("h", 0) or 0),
                "low":    float(q.get("l", 0) or 0),
                "oi":     int(q.get("oi", 0) or 0),
                "pdcl":   float(q.get("pdcl", 0) or 0),  # prev day close
            }
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Technical indicators (pure pandas — no extra deps)
# ─────────────────────────────────────────────────────────────────────────────
def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    ag    = gain.ewm(com=period - 1, min_periods=period).mean()
    al    = loss.ewm(com=period - 1, min_periods=period).mean()
    rs    = ag / al.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"]  - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def swing_lows(close: pd.Series, window: int = 5) -> list:
    lows = []
    for i in range(window, len(close) - window):
        if close.iloc[i] == close.iloc[i - window: i + window + 1].min():
            lows.append(i)
    return lows


def swing_highs(close: pd.Series, window: int = 5) -> list:
    highs = []
    for i in range(window, len(close) - window):
        if close.iloc[i] == close.iloc[i - window: i + window + 1].max():
            highs.append(i)
    return highs


def find_support_resistance(df: pd.DataFrame, ltp: float):
    """
    Return (support, resistance, ema20) using swing levels + EMAs.
    """
    close = df["close"].astype(float)
    ema20 = float(close.ewm(span=20, min_periods=1).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, min_periods=1).mean().iloc[-1])

    recent_low  = float(df["low"].tail(20).min())
    recent_high = float(df["high"].tail(60).max())

    sl_idx = swing_lows(close, window=5)
    sh_idx = swing_highs(close, window=5)

    sl_prices = [float(close.iloc[i]) for i in sl_idx if float(close.iloc[i]) < ltp]
    sh_prices = [float(close.iloc[i]) for i in sh_idx if float(close.iloc[i]) > ltp]

    # Support: highest swing low below LTP, floored by ema20
    support_candidates = [recent_low, ema20, ema50] + sl_prices[-5:]
    support_candidates = [s for s in support_candidates if 0 < s < ltp]
    support = max(support_candidates) if support_candidates else round(ltp * 0.95, 2)

    # Resistance: lowest swing high above LTP, capped at 52W high
    h52 = float(close.tail(252).max())
    resistance_candidates = [h52, recent_high] + sh_prices[:5]
    resistance_candidates = [r for r in resistance_candidates if r > ltp]
    resistance = min(resistance_candidates) if resistance_candidates else round(ltp * 1.20, 2)

    return round(support, 2), round(resistance, 2), round(ema20, 2), round(ema50, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Criteria helpers
# ─────────────────────────────────────────────────────────────────────────────
def is_consolidation_breakout(df: pd.DataFrame) -> bool:
    """
    4-week tight consolidation breakout:
    Last 20 days range < 8% AND today closes above the range top.
    """
    if len(df) < 25:
        return False
    consol     = df.tail(21).iloc[:-1]
    c_max      = float(consol["close"].max())
    c_min      = float(consol["close"].min())
    today_c    = float(df["close"].iloc[-1])
    if c_min <= 0:
        return False
    return ((c_max - c_min) / c_min < 0.08) and (today_c > c_max)


def circuit_hit_recently(df: pd.DataFrame, lookback: int = 5) -> bool:
    """
    True if any of the last N sessions look like a circuit:
    - |pct_change| >= 19%  (hit the 20% circuit band)
    - OR high == low (price completely frozen — hard circuit)
    - OR hl_range < 0.1% with very high volume (operator-held price)
    """
    if len(df) < lookback + 2:
        return False
    recent = df.tail(lookback + 1).copy()
    pct = recent["close"].pct_change().abs()
    hl  = (recent["high"] - recent["low"]) / recent["close"].replace(0, 1e-10)
    hard_circuit  = pct.tail(lookback) >= 0.19
    frozen_price  = hl.tail(lookback) < 0.001
    return bool((hard_circuit | frozen_price).any())


def manipulation_flags(df: pd.DataFrame, ltp: float) -> list:
    """
    Return list of warning strings if suspicious patterns found.
    Empty list = clean.
    """
    if len(df) < 20:
        return []

    flags = []
    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)

    # 1. Pump-and-dump: trough-to-LTP > 50% in last 20 days
    trough = float(close.tail(20).min())
    if trough > 0 and (ltp - trough) / trough > 0.50:
        flags.append(f"PUMP: +{round((ltp-trough)/trough*100)}% from 20d low")

    # 2. Spike-and-reversal: single day >15% then next day < -5%
    pct = close.pct_change().tail(12).values
    for i in range(len(pct) - 1):
        if pct[i] > 0.15 and pct[i + 1] < -0.05:
            flags.append("SPIKE+DUMP pattern in recent sessions")
            break

    # 3. Zero-volume days > 2 in last 20 (illiquid / frozen)
    zero_days = int((volume.tail(20) == 0).sum())
    if zero_days > 2:
        flags.append(f"{zero_days} zero-vol days in 20d (illiquid)")

    # 4. Extremely erratic volume: CV > 3.0 (operator churning)
    mu = float(volume.tail(20).mean())
    sd = float(volume.tail(20).std())
    if mu > 0 and sd / mu > 3.0:
        flags.append("Erratic volume CV>3 (operator suspected)")

    # 5. Price frozen > 2 days (hard circuit / artificial hold)
    hl_pct = ((df["high"] - df["low"]) / df["close"].replace(0, 1e-10)).tail(10)
    frozen = int((hl_pct < 0.005).sum())
    if frozen > 2:
        flags.append(f"{frozen} near-frozen candles (circuit/manip)")

    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Core screener — one symbol
# ─────────────────────────────────────────────────────────────────────────────
def screen_symbol(api, symbol: str, exchange: str = "NSE") -> dict:
    base = {"symbol": symbol, "pass": False, "criteria_met": 0}

    # Step 1: Token
    token, _ = resolve_token(api, symbol, exchange)
    if not token:
        return {**base, "status": "No token"}

    # Step 2: Live quote
    quote = fetch_live_quote(api, token, exchange)
    ltp   = quote.get("ltp", 0.0)
    if ltp <= 0:
        return {**base, "status": "No live price"}

    # Step 3: Historical OHLCV (290 trading days ≈ 1 year + buffer)
    df = fetch_ohlcv(api, token, exchange, days=290)
    if df.empty or len(df) < 60:
        return {**base, "status": f"Insufficient history ({len(df)} bars)"}

    # Inject live price into today's bar
    today = pd.Timestamp.now().normalize()
    last_date = df.iloc[-1]["date"]
    if hasattr(last_date, "normalize") and last_date.normalize() == today:
        df.loc[df.index[-1], "close"] = ltp
        df.loc[df.index[-1], "high"]  = max(float(df.iloc[-1]["high"]), ltp)
        df.loc[df.index[-1], "low"]   = min(float(df.iloc[-1]["low"]),  ltp)
        if quote.get("volume", 0) > 0:
            df.loc[df.index[-1], "volume"] = quote["volume"]

    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)

    # ── Criteria ─────────────────────────────────────────────────────────────

    # C1 — Price ₹20–₹150
    c1 = 20.0 <= ltp <= 150.0

    # C2 — 1-month (20d) avg daily volume > 1,000,000
    avg_vol_20 = float(volume.tail(20).mean())
    c2 = avg_vol_20 >= 1_000_000

    # C3 — Today's volume > 3× 20d avg
    today_vol      = int(quote.get("volume", int(volume.iloc[-1])))
    vol_surge_mult = today_vol / max(avg_vol_20, 1)
    c3 = vol_surge_mult >= 3.0

    # C4 — RSI(14) between 60 and 80
    rsi_series = calc_rsi(close, 14)
    rsi        = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 else 0.0
    c4 = 60.0 < rsi < 80.0

    # C5 — Within 2% of 52W high  OR  4-week consolidation breakout
    high52          = float(close.tail(252).max())
    near_52w        = ltp >= 0.98 * high52
    consol_breakout = is_consolidation_breakout(df)
    c5 = near_52w or consol_breakout

    # C6 — No circuit hit in last 5 sessions
    circuit = circuit_hit_recently(df, lookback=5)
    c6 = not circuit

    criteria = {
        "Price ₹20–₹150":        c1,
        "Avg Vol > 1M":           c2,
        "Vol Surge ≥ 3×":         c3,
        "RSI(14) 60–80":          c4,
        "Near 52W High/Breakout": c5,
        "No Circuit (5d)":        c6,
    }
    criteria_met = sum(criteria.values())

    # ── Anti-Manipulation ─────────────────────────────────────────────────────
    m_flags  = manipulation_flags(df, ltp)
    is_clean = len(m_flags) == 0
    all_pass = (criteria_met == 6) and is_clean

    # ── Risk Management ───────────────────────────────────────────────────────
    support, resistance, ema20, ema50 = find_support_resistance(df, ltp)

    atr_series = calc_atr(df, 14)
    atr        = float(atr_series.iloc[-1]) if len(atr_series) > 0 else ltp * 0.02

    # Stop-loss: tightest of (5% hard stop, 1.5× ATR stop), but ≥ support
    hard_stop = ltp * 0.95
    atr_stop  = ltp - 1.5 * atr
    stop_loss = max(min(hard_stop, atr_stop), support)
    stop_loss = min(stop_loss, ltp * 0.95)      # never wider than 5%

    # Target: nearest resistance or 20% hard target, whichever is reachable
    hard_tgt  = ltp * 1.20
    target    = resistance if ltp < resistance <= hard_tgt * 1.10 else hard_tgt

    risk   = ltp - stop_loss
    reward = target - ltp
    rr     = round(reward / max(risk, 0.01), 2)

    # Trend
    trend = "📈 UPTREND" if (ltp > ema50 and ema20 > ema50) else \
            "↔️ SIDEWAYS" if ltp > ema50 else "📉 DOWNTREND"

    price_action_lbl = ("🔝 Near 52W High" if near_52w else "") + \
                       (" 🚀 Consol Breakout" if consol_breakout else "")

    return {
        "symbol":           symbol,
        "ltp":              round(ltp, 2),
        "rsi":              round(rsi, 1),
        "avg_vol_20":       int(avg_vol_20),
        "today_vol":        today_vol,
        "vol_surge":        round(vol_surge_mult, 1),
        "high52":           round(high52, 2),
        "near_52w":         near_52w,
        "consol_breakout":  consol_breakout,
        "price_action":     price_action_lbl.strip(),
        "ema20":            round(ema20, 2),
        "ema50":            round(ema50, 2),
        "atr":              round(atr, 2),
        "trend":            trend,
        "support":          support,
        "resistance":       resistance,
        "stop_loss":        round(stop_loss, 2),
        "target":           round(target, 2),
        "risk":             round(risk, 2),
        "reward":           round(reward, 2),
        "rr_ratio":         rr,
        "criteria":         criteria,
        "criteria_met":     criteria_met,
        "all_pass":         all_pass,
        "is_clean":         is_clean,
        "manip_flags":      m_flags,
        "circuit_hit":      circuit,
        "status":           "✅ ALL PASS" if all_pass else f"{criteria_met}/6 criteria",
        "pass":             all_pass,
        "df":               df,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Chart builder
# ─────────────────────────────────────────────────────────────────────────────
def build_chart(res: dict) -> go.Figure:
    df_c  = res["df"].tail(60).copy()
    close = df_c["close"].astype(float)

    ema20_line = close.ewm(span=20, min_periods=1).mean()
    ema50_line = close.ewm(span=50, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_c["date"],
        open=df_c["open"], high=df_c["high"],
        low=df_c["low"],   close=close,
        name=res["symbol"],
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=df_c["date"], y=ema20_line,
        name="EMA20", line=dict(color="#ff9800", width=1.2),
    ))
    fig.add_trace(go.Scatter(
        x=df_c["date"], y=ema50_line,
        name="EMA50", line=dict(color="#2196f3", width=1.2),
    ))
    # Volume bars (secondary y)
    fig.add_trace(go.Bar(
        x=df_c["date"], y=df_c["volume"],
        name="Volume", opacity=0.25,
        marker_color="#90a4ae",
        yaxis="y2", showlegend=False,
    ))
    # Stop-loss & target lines
    fig.add_hline(
        y=res["stop_loss"], line=dict(color="#ef5350", dash="dash", width=1.5),
        annotation_text=f"SL ₹{res['stop_loss']}", annotation_font_color="#ef5350",
    )
    fig.add_hline(
        y=res["target"], line=dict(color="#26a69a", dash="dash", width=1.5),
        annotation_text=f"TGT ₹{res['target']}", annotation_font_color="#26a69a",
    )
    fig.update_layout(
        height=380,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        title=dict(text=f"{res['symbol']} — Last 60 Sessions", font_size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, visible=False),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────
api, login_msg = get_shoonya_api()
if api:
    st.success(login_msg)
else:
    st.error(f"Shoonya API connection failed: {login_msg}")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Screener Settings")

use_custom = st.sidebar.checkbox("Use custom symbol list", value=False)
if use_custom:
    raw_input = st.sidebar.text_area(
        "Symbols (comma / newline separated)",
        value=", ".join(MICRO_CAP_UNIVERSE[:15]),
        height=160,
    )
    symbols_to_scan = [
        s.strip().upper()
        for s in raw_input.replace(",", "\n").splitlines()
        if s.strip()
    ]
else:
    symbols_to_scan = list(MICRO_CAP_UNIVERSE)

min_show    = st.sidebar.slider("Min criteria to show in watchlist", 3, 6, 5)
show_charts = st.sidebar.checkbox("Show price charts", value=True)
run_scan    = st.sidebar.button("🚀 Run Aggressive Scan", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Universe:** {len(symbols_to_scan)} symbols")
st.sidebar.caption(
    "⏱️ ~3–5 min for full scan. "
    "Best during NSE market hours 9:15–15:30 IST for live volume signals."
)

# ── Info cards ───────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.info(f"📊 **{len(symbols_to_scan)}** symbols queued")
c2.info("📡 Data: Shoonya Live API")
c3.info("🕐 Market: 9:15 – 15:30 IST")

with st.expander("📋 Screening Criteria & Risk Rules"):
    st.markdown("""
| # | Criterion | Rule |
|---|-----------|------|
| 1 | **Price** | ₹20 – ₹150 |
| 2 | **Liquidity** | 20-day avg volume > 1,000,000 |
| 3 | **Volume Surge** | Today's volume > 3× 20d avg |
| 4 | **Momentum** | RSI(14) daily: 60 – 80 |
| 5 | **Price Action** | Within 2% of 52W high  **OR**  4-week tight consolidation breakout |
| 6 | **Circuit Filter** | No upper/lower circuit in last 5 sessions |
| + | **Anti-Manipulation** | No pump >50%, no spike+dump, no frozen price days |

**Risk Management**
- **Stop-Loss**: tighter of `5% hard stop` vs `1.5× ATR stop`, floored at nearest support level
- **Target**: nearest historical resistance or `+20%` hard cap
- **R:R**: minimum 1:2 shown; only enter if R:R ≥ 1.5
    """)

st.markdown("---")

# ── Scan execution ────────────────────────────────────────────────────────────
if run_scan:
    progress_bar = st.progress(0)
    status_txt   = st.empty()
    all_results  = []

    for idx, sym in enumerate(symbols_to_scan):
        status_txt.markdown(f"⏳ `{sym}` ({idx + 1}/{len(symbols_to_scan)})…")
        try:
            result = screen_symbol(api, sym)
            all_results.append(result)
        except Exception as exc:
            all_results.append({
                "symbol": sym, "pass": False,
                "criteria_met": 0, "status": f"Error: {exc}",
            })
        progress_bar.progress((idx + 1) / len(symbols_to_scan))
        time.sleep(0.35)   # respect Shoonya rate limits

    status_txt.markdown("✅ **Scan complete!**")
    progress_bar.empty()

    # Categorise
    passing = [r for r in all_results if r.get("pass")]
    partial = [r for r in all_results
               if not r.get("pass") and r.get("criteria_met", 0) >= min_show]

    # ── Summary ──────────────────────────────────────────────────────────────
    st.markdown("---")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Scanned",        len(all_results))
    s2.metric("🟢 Actionable",  len(passing))
    s3.metric("🟡 Watchlist",   len(partial))
    s4.metric("🔴 Filtered Out", len(all_results) - len(passing) - len(partial))

    if not passing and not partial:
        st.error(
            "🚨 **HOLD CASH** — No stocks meet the criteria right now.\n\n"
            "Run during market hours (9:15–15:30 IST) for accurate volume surge signals."
        )

    # ── Full Pass — Actionable Stocks ─────────────────────────────────────────
    if passing:
        st.markdown(f"## 🟢 ACTIONABLE — {len(passing)} Stock(s) Passing ALL Criteria")

        # Summary table first
        tbl = []
        for r in sorted(passing, key=lambda x: x.get("rr_ratio", 0), reverse=True):
            tbl.append({
                "Symbol":     r["symbol"],
                "LTP (₹)":   r["ltp"],
                "RSI":        r["rsi"],
                "Vol Surge×": r["vol_surge"],
                "Stop-Loss":  r["stop_loss"],
                "Target":     r["target"],
                "R:R":        r["rr_ratio"],
                "Trend":      r["trend"],
                "Setup":      r.get("price_action", ""),
            })
        st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)
        st.markdown("---")

        # Detailed cards
        for res in sorted(passing, key=lambda x: x.get("rr_ratio", 0), reverse=True):
            sym = res["symbol"]
            st.markdown(f"### {sym} &nbsp; ₹{res['ltp']} &nbsp; {res.get('price_action','')} &nbsp; {res['trend']}")

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("LTP",        f"₹{res['ltp']}")
            m2.metric("RSI(14)",    f"{res['rsi']}")
            m3.metric("Vol Surge",  f"{res['vol_surge']}×")
            m4.metric(
                "Stop-Loss", f"₹{res['stop_loss']}",
                delta=f"−{round((res['ltp'] - res['stop_loss']) / res['ltp'] * 100, 1)}%",
                delta_color="inverse",
            )
            m5.metric(
                "Target", f"₹{res['target']}",
                delta=f"+{round((res['target'] - res['ltp']) / res['ltp'] * 100, 1)}%",
            )
            m6.metric("R:R Ratio", f"1 : {res['rr_ratio']}")

            with st.expander("📐 Full Risk Detail + Criteria Checklist"):
                cc = st.columns(3)
                for j, (name, val) in enumerate(res["criteria"].items()):
                    cc[j % 3].markdown(f"{'✅' if val else '❌'} {name}")

                st.markdown(f"""
---
| Field | Value |
|-------|-------|
| Entry (market) | ₹{res['ltp']} |
| Stop-Loss | ₹{res['stop_loss']} (−{round((res['ltp']-res['stop_loss'])/res['ltp']*100,1)}%) |
| Nearest Support | ₹{res['support']} |
| Target | ₹{res['target']} (+{round((res['target']-res['ltp'])/res['ltp']*100,1)}%) |
| Nearest Resistance | ₹{res['resistance']} |
| Risk ₹ | ₹{res['risk']} |
| Reward ₹ | ₹{res['reward']} |
| ATR(14) | ₹{res['atr']} |
| EMA20 | ₹{res['ema20']} |
| EMA50 | ₹{res['ema50']} |
| 52W High | ₹{res['high52']} |
| Avg 20d Volume | {res['avg_vol_20']:,} |
| Today's Volume | {res['today_vol']:,} |
                """)

            if show_charts and "df" in res:
                st.plotly_chart(build_chart(res), use_container_width=True)

            st.divider()

    # ── Partial Pass — Watchlist ──────────────────────────────────────────────
    if partial:
        st.markdown(f"## 🟡 WATCHLIST — {len(partial)} Stock(s) ({min_show}+ criteria)")
        wl_rows = []
        for r in sorted(partial, key=lambda x: x.get("criteria_met", 0), reverse=True):
            if "ltp" not in r:
                continue
            row = {
                "Symbol":       r["symbol"],
                "LTP (₹)":     r["ltp"],
                "RSI":          r.get("rsi", "—"),
                "Vol Surge×":   r.get("vol_surge", "—"),
                "Criteria":     f"{r.get('criteria_met',0)}/6",
                "Stop (₹)":    r.get("stop_loss", "—"),
                "Target (₹)":  r.get("target", "—"),
                "R:R":          r.get("rr_ratio", "—"),
                "Trend":        r.get("trend", "—"),
                "Manip Flags":  " | ".join(r.get("manip_flags", [])) or "Clean",
            }
            wl_rows.append(row)
        if wl_rows:
            st.dataframe(pd.DataFrame(wl_rows), use_container_width=True, hide_index=True)

    # ── Scan Log ─────────────────────────────────────────────────────────────
    with st.expander(f"📋 Full Scan Log ({len(all_results)} symbols)"):
        log = [
            {
                "Symbol":       r["symbol"],
                "LTP":          r.get("ltp", "—"),
                "Criteria Met": r.get("criteria_met", 0),
                "Status":       r.get("status", "—"),
                "Circuit":      "⚠️ Yes" if r.get("circuit_hit") else "OK",
                "Manip":        "⚠️ " + r.get("manip_flags", [""])[0]
                                if r.get("manip_flags") else "Clean",
            }
            for r in all_results
        ]
        st.dataframe(pd.DataFrame(log), use_container_width=True, hide_index=True)

else:
    # Landing page
    st.markdown("""
### 🚀 How to Use

1. Click **Run Aggressive Scan** in the sidebar
2. The screener queries **Shoonya live API** for every symbol — live price, volume, 52W high
3. Stocks passing **all 6 criteria with no manipulation flags** appear in 🟢 **ACTIONABLE**
4. Each stock shows: entry price, stop-loss (with support floor), target (resistance), R:R ratio
5. Stocks meeting {min_criteria}+ criteria appear in 🟡 **WATCHLIST** for monitoring

> ⚠️ **Volume surge criterion (C3) is only meaningful during market hours** (9:15–15:30 IST).
> After-hours scans will rarely show volume surges as cumulative volume is low.

---
**Manipulation guard removes stocks with:**
- 🔴 Pump pattern: >50% rise from 20-day low  
- 🔴 Spike-and-dump: >15% single-day spike followed by reversal  
- 🔴 Frozen price days: price doesn't move despite volume (circuit / operator hold)  
- 🔴 Erratic volume: coefficient of variation >3 (churning by operators)
    """)
