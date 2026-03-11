"""
pages/aggressive_screener.py

🎯 Aggressive Full-Market Screener — TradingView-Style
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data source   : Shoonya (Finvasia) API — 100 % live
Universe      : ALL ~2 400 NSE equities (auto-loaded from scripmaster)
Screening     : Progressive 3-phase filter → fast full-market scan
Risk Mgmt     : ATR stop, swing S/R levels, manipulation guard
"""

from __future__ import annotations

import io
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyotp
import requests as _requests
import streamlit as st
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Aggressive Screener", layout="wide", page_icon="🎯")

# ─────────────────────────────────────────────────────────────────────────────
# TradingView Dark CSS
# ─────────────────────────────────────────────────────────────────────────────
TV_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── global overrides ─────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] { background: #131722; }
[data-testid="stSidebar"]         { background: #1e222d; border-right: 1px solid #2a2e39; }
[data-testid="stHeader"]          { background: transparent; }
header                             { background: transparent !important; }
section[data-testid="stSidebar"] > div { padding-top: 1rem; }

/* fonts */
html, body, [class*="css"] {
    font-family: 'Inter', 'Trebuchet MS', sans-serif;
    color: #d1d4dc;
}

/* headings */
h1, h2, h3 { color: #d1d4dc !important; font-weight: 600 !important; letter-spacing: -0.5px; }
h1 { font-size: 1.7rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }

/* ── metric cards ─────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #1e222d;
    border: 1px solid #2a2e39;
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.3);
}
[data-testid="stMetricLabel"]  { color: #787b86 !important; font-size: .78rem !important; }
[data-testid="stMetricValue"]  { color: #d1d4dc !important; font-size: 1.15rem !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"]  { font-size: .78rem !important; }

/* ── dataframes ───────────────────────────────────────────────────── */
[data-testid="stDataFrame"], .stDataFrame {
    border-radius: 8px;
    overflow: hidden;
}
[data-testid="stDataFrame"] table { background: #1e222d !important; }
[data-testid="stDataFrame"] th   { background: #2a2e39 !important; color: #787b86 !important; font-weight: 600; font-size: .78rem; }
[data-testid="stDataFrame"] td   { border-color: #2a2e39 !important; font-size: .82rem; }

/* ── buttons ──────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #2962ff, #1e53e5) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1rem !important;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    box-shadow: 0 0 20px rgba(41,98,255,.4) !important;
    transform: translateY(-1px);
}

/* ── expanders ────────────────────────────────────────────────────── */
[data-testid="stExpander"]       { background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; }
[data-testid="stExpanderToggle"] { color: #787b86 !important; }

/* ── info / success / error ───────────────────────────────────────── */
.stAlert { border-radius: 8px !important; }

/* ── progress bar ─────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div { background: #2962ff !important; }

/* ── dividers ─────────────────────────────────────────────────────── */
hr { border-color: #2a2e39 !important; }

/* ── stock card ───────────────────────────────────────────────────── */
.tv-stock-card {
    background: #1e222d;
    border: 1px solid #2a2e39;
    border-radius: 10px;
    padding: 18px 22px;
    margin: 8px 0;
    box-shadow: 0 4px 16px rgba(0,0,0,.25);
    transition: border-color .2s, box-shadow .2s;
}
.tv-stock-card:hover {
    border-color: #2962ff;
    box-shadow: 0 4px 24px rgba(41,98,255,.15);
}
.tv-header {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 10px;
}
.tv-ticker {
    font-size: 1.15rem; font-weight: 700; color: #d1d4dc;
    letter-spacing: -.3px;
}
.tv-badge {
    display: inline-block; padding: 2px 10px; border-radius: 4px;
    font-size: .72rem; font-weight: 600; letter-spacing: .5px;
}
.tv-buy   { background: rgba(38,166,154,.15); color: #26a69a; border: 1px solid #26a69a; }
.tv-sell  { background: rgba(239,83,80,.15);  color: #ef5350; border: 1px solid #ef5350; }
.tv-watch { background: rgba(255,183,77,.15); color: #ffb74d; border: 1px solid #ffb74d; }
.tv-clean { background: rgba(38,166,154,.08); color: #26a69a; }
.tv-warn  { background: rgba(239,83,80,.08);  color: #ef5350; }

.tv-price {
    font-size: 1.5rem; font-weight: 700; color: #d1d4dc;
}
.tv-change-up   { color: #26a69a; font-weight: 600; }
.tv-change-down { color: #ef5350; font-weight: 600; }
.tv-label  { color: #787b86; font-size: .75rem; font-weight: 500; }
.tv-value  { color: #d1d4dc; font-size: .88rem; font-weight: 600; }

/* risk grid */
.tv-risk-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px; margin-top: 10px;
}
.tv-risk-item {
    background: #131722;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: center;
}

/* pulse animation for live indicator */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.tv-live { animation: pulse 2s infinite; color: #26a69a; font-weight: 700; }

/* heatmap cells */
.tv-heat-strong { background: rgba(38,166,154,.25); }
.tv-heat-weak   { background: rgba(239,83,80,.12); }

/* scrollbar */
::-webkit-scrollbar       { width: 6px; }
::-webkit-scrollbar-track { background: #131722; }
::-webkit-scrollbar-thumb { background: #434651; border-radius: 3px; }
</style>
"""
st.markdown(TV_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Shoonya API — login once per session
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_shoonya_api():
    try:
        from NorenRestApiPy.NorenApi import NorenApi
    except ImportError:
        return None, "NorenRestApiPy not installed"

    env_path = Path(__file__).resolve().parent.parent / "shoonya.env"
    load_dotenv(dotenv_path=env_path, override=True)

    uid  = os.getenv("SHOONYA_USER_ID", "")
    pwd  = os.getenv("SHOONYA_PASSWORD", "")
    totp = os.getenv("SHOONYA_TOTP_SECRET", "").replace("-", "").replace(" ", "").strip()
    vc   = os.getenv("SHOONYA_VENDOR_CODE", "")
    api_s = os.getenv("SHOONYA_API_SECRET", "")
    imei = os.getenv("SHOONYA_IMEI", "")

    twoFA = totp if totp.isdigit() else pyotp.TOTP(totp.upper()).now()

    class _Api(NorenApi):
        def __init__(self):
            super().__init__(
                host="https://api.shoonya.com/NorenWClientTP/",
                websocket="wss://api.shoonya.com/NorenWSTP/",
            )
    api = _Api()
    ret = api.login(userid=uid, password=pwd, twoFA=twoFA,
                    vendor_code=vc, api_secret=api_s, imei=imei)
    if ret and ret.get("stat") == "Ok":
        return api, ret.get("uname", uid)
    return None, ret.get("emsg") if ret else "No response"


# ─────────────────────────────────────────────────────────────────────────────
# Scripmaster — download ALL NSE equity tokens (cached daily)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def load_nse_scripmaster() -> pd.DataFrame:
    """Download Shoonya's NSE scripmaster and return EQ-only rows."""
    urls = [
        "https://api.shoonya.com/NSE_symbols.txt.zip",
        "https://shoonya.finvasia.com/NSE_symbols.txt.zip",
    ]
    for url in urls:
        try:
            r = _requests.get(url, timeout=20)
            if r.status_code != 200 or len(r.content) < 5000:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            txt = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
            lines = txt.strip().split("\n")
            header = [h.strip() for h in lines[0].split(",")]
            rows = []
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= len(header):
                    rows.append(dict(zip(header, [p.strip() for p in parts])))
            df = pd.DataFrame(rows)
            # Filter to equity only
            eq = df[df["Instrument"] == "EQ"].copy()
            eq["Token"] = eq["Token"].astype(str)
            # Clean trading symbol (remove -EQ suffix for display)
            eq["CleanSymbol"] = eq["TradingSymbol"].str.replace("-EQ", "", regex=False)
            return eq.reset_index(drop=True)
        except Exception:
            continue
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────
def _quote(api, token: str, exch: str = "NSE") -> dict:
    try:
        q = api.get_quotes(exchange=exch, token=token)
        if q and q.get("stat") == "Ok":
            return {
                "ltp":   float(q.get("lp",  0) or 0),
                "vol":   int(q.get("v",   0) or 0),
                "h52":   float(q.get("h52", 0) or 0),
                "l52":   float(q.get("l52", 0) or 0),
                "open":  float(q.get("o",   0) or 0),
                "high":  float(q.get("h",   0) or 0),
                "low":   float(q.get("l",   0) or 0),
                "pc":    float(q.get("pc",  0) or 0),
                "pdcl":  float(q.get("pdcl", 0) or 0),
            }
    except Exception:
        pass
    return {}


def _ohlcv(api, token: str, exch: str = "NSE", days: int = 290) -> pd.DataFrame:
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=int(days * 1.5))
    try:
        raw = api.get_time_price_series(
            exchange=exch, token=token,
            starttime=start_dt.strftime("%d-%m-%Y %H:%M:%S"),
            endtime=end_dt.strftime("%d-%m-%Y %H:%M:%S"),
            interval=1440,
        )
        if not isinstance(raw, list) or not raw:
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
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Indicators
# ─────────────────────────────────────────────────────────────────────────────
def _rsi(close: pd.Series, n: int = 14) -> float:
    d = close.diff()
    g = d.clip(lower=0).ewm(com=n - 1, min_periods=n).mean()
    l = (-d).clip(lower=0).ewm(com=n - 1, min_periods=n).mean()
    rs = g / l.replace(0, 1e-10)
    s = 100 - 100 / (1 + rs)
    return float(s.iloc[-1]) if len(s) >= n else 0.0


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"]  - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return float(tr.ewm(com=n - 1, min_periods=n).mean().iloc[-1])


def _ema(s: pd.Series, n: int) -> float:
    return float(s.ewm(span=n, min_periods=1).mean().iloc[-1])


# ─────────────────────────────────────────────────────────────────────────────
# Criteria checks
# ─────────────────────────────────────────────────────────────────────────────
def _consol_breakout(df: pd.DataFrame) -> bool:
    if len(df) < 25:
        return False
    consol = df.tail(21).iloc[:-1]
    mx, mn = float(consol["close"].max()), float(consol["close"].min())
    if mn <= 0:
        return False
    return ((mx - mn) / mn < 0.08) and float(df["close"].iloc[-1]) > mx


def _circuit_hit(df: pd.DataFrame, n: int = 5) -> bool:
    if len(df) < n + 2:
        return False
    r = df.tail(n + 1).copy()
    pct = r["close"].pct_change().abs()
    hl  = (r["high"] - r["low"]) / r["close"].replace(0, 1e-10)
    return bool((pct.tail(n) >= 0.19).any() | (hl.tail(n) < 0.001).any())


def _manip_flags(df: pd.DataFrame, ltp: float) -> list[str]:
    if len(df) < 20:
        return []
    flags = []
    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)
    # Pump >50% from 20d low
    trough = float(close.tail(20).min())
    if trough > 0 and (ltp - trough) / trough > 0.50:
        flags.append(f"PUMP +{round((ltp-trough)/trough*100)}%")
    # Spike-and-dump
    pct = close.pct_change().tail(12).values
    for i in range(len(pct) - 1):
        if pct[i] > 0.15 and pct[i + 1] < -0.05:
            flags.append("Spike+Dump")
            break
    # Zero-vol days
    zd = int((volume.tail(20) == 0).sum())
    if zd > 2:
        flags.append(f"{zd} zero-vol days")
    # Erratic volume
    mu = float(volume.tail(20).mean())
    sd = float(volume.tail(20).std())
    if mu > 0 and sd / mu > 3.0:
        flags.append("Erratic vol")
    # Frozen candles
    hl_pct = ((df["high"] - df["low"]) / df["close"].replace(0, 1e-10)).tail(10)
    if int((hl_pct < 0.005).sum()) > 2:
        flags.append("Frozen candles")
    return flags


def _support_resistance(df: pd.DataFrame, ltp: float):
    close = df["close"].astype(float)
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    recent_low  = float(df["low"].tail(20).min())
    recent_high = float(df["high"].tail(60).max())
    h52 = float(close.tail(252).max())

    sup_cands = [s for s in [recent_low, ema20, ema50] if 0 < s < ltp]
    support = max(sup_cands) if sup_cands else round(ltp * 0.95, 2)

    res_cands = [r for r in [h52, recent_high] if r > ltp]
    resistance = min(res_cands) if res_cands else round(ltp * 1.20, 2)

    return round(support, 2), round(resistance, 2), round(ema20, 2), round(ema50, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 3-Phase progressive screener
# ─────────────────────────────────────────────────────────────────────────────
def phase1_price_filter(api, tokens_df: pd.DataFrame, price_min: float,
                        price_max: float, progress_cb=None) -> list[dict]:
    """Phase 1: Fetch live quotes for ALL stocks, keep those in price range."""
    results = []
    total = len(tokens_df)

    def fetch_one(row):
        q = _quote(api, row["Token"])
        if q and price_min <= q["ltp"] <= price_max:
            return {**row.to_dict(), **q}
        return None

    # Use threads for speed (10 workers ~ 3x faster)
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_one, row): idx
                   for idx, row in tokens_df.iterrows()}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if progress_cb and done % 25 == 0:
                progress_cb(done / total,
                            f"Phase 1: Price scan {done}/{total}")
            res = fut.result()
            if res:
                results.append(res)

    if progress_cb:
        progress_cb(1.0, f"Phase 1 done — {len(results)} in price range")
    return results


def phase2_volume_filter(results: list[dict], min_avg_vol: int) -> list[dict]:
    """Phase 2: Quick volume check from live quote data."""
    # We only have today's volume from quote; avg_vol needs history.
    # For now, keep stocks with today's volume > min_avg_vol / 5
    # (conservative pre-filter; phase 3 will verify properly).
    out = []
    for r in results:
        if r.get("vol", 0) >= min_avg_vol // 5:
            out.append(r)
    return out


def phase3_deep_analysis(api, candidates: list[dict], progress_cb=None) -> list[dict]:
    """Phase 3: Fetch OHLCV + compute all indicators + criteria."""
    results = []
    total = len(candidates)

    for idx, cand in enumerate(candidates):
        if progress_cb and idx % 3 == 0:
            progress_cb(idx / max(total, 1),
                        f"Phase 3: Deep analysis {idx}/{total} — {cand.get('CleanSymbol','')}")

        token = cand["Token"]
        sym   = cand.get("CleanSymbol", cand.get("Symbol", ""))
        ltp   = cand.get("ltp", 0.0)

        df = _ohlcv(api, token, days=290)
        if df.empty or len(df) < 60:
            continue

        # Inject live data
        today = pd.Timestamp.now().normalize()
        last_d = df.iloc[-1]["date"]
        if hasattr(last_d, "normalize") and last_d.normalize() == today:
            df.loc[df.index[-1], "close"] = ltp
            if cand.get("vol", 0) > 0:
                df.loc[df.index[-1], "volume"] = cand["vol"]

        close  = df["close"].astype(float)
        volume = df["volume"].astype(float)

        # Indicators
        avg_vol20 = float(volume.tail(20).mean())
        rsi       = _rsi(close, 14)
        ema20     = _ema(close, 20)
        ema50     = _ema(close, 50)
        atr       = _atr(df, 14)
        h52       = float(close.tail(252).max())
        today_vol = cand.get("vol", int(volume.iloc[-1]))

        vol_surge = today_vol / max(avg_vol20, 1)
        near_52w  = h52 > 0 and ltp >= 0.98 * h52
        breakout  = _consol_breakout(df)
        circuit   = _circuit_hit(df)
        m_flags   = _manip_flags(df, ltp)

        criteria = {
            "Price range":        20.0 <= ltp <= 150.0,
            "Avg Vol > 1M":       avg_vol20 >= 1_000_000,
            "Vol Surge 3x":       vol_surge >= 3.0,
            "RSI 60-80":          60 < rsi < 80,
            "52W High/Breakout":  near_52w or breakout,
            "No Circuit":         not circuit,
        }
        crit_met = sum(criteria.values())
        is_clean = len(m_flags) == 0
        full_pass = crit_met == 6 and is_clean

        # Risk
        sup, res_level, _, _ = _support_resistance(df, ltp)
        hard_stop = ltp * 0.95
        atr_stop  = ltp - 1.5 * atr
        sl = max(min(hard_stop, atr_stop), sup)
        sl = min(sl, ltp * 0.95)
        tgt = res_level if ltp < res_level <= ltp * 1.32 else ltp * 1.20
        risk   = ltp - sl
        reward = tgt - ltp
        rr = round(reward / max(risk, 0.01), 2)

        trend = ("UP" if (ltp > ema50 and ema20 > ema50) else
                 "SIDE" if ltp > ema50 else "DOWN")

        pct_chg = ((ltp - cand.get("pdcl", ltp)) / max(cand.get("pdcl", ltp), 0.01)) * 100

        results.append({
            "symbol":      sym,
            "token":       token,
            "ltp":         round(ltp, 2),
            "pct_chg":     round(pct_chg, 1),
            "rsi":         round(rsi, 1),
            "ema20":       round(ema20, 2),
            "ema50":       round(ema50, 2),
            "atr":         round(atr, 2),
            "avg_vol20":   int(avg_vol20),
            "today_vol":   today_vol,
            "vol_surge":   round(vol_surge, 1),
            "h52":         round(h52, 2),
            "near_52w":    near_52w,
            "breakout":    breakout,
            "circuit":     circuit,
            "support":     sup,
            "resistance":  res_level,
            "stop_loss":   round(sl, 2),
            "target":      round(tgt, 2),
            "risk":        round(risk, 2),
            "reward":      round(reward, 2),
            "rr":          rr,
            "trend":       trend,
            "criteria":    criteria,
            "crit_met":    crit_met,
            "full_pass":   full_pass,
            "is_clean":    is_clean,
            "m_flags":     m_flags,
            "df":          df,
        })
        time.sleep(0.25)

    if progress_cb:
        progress_cb(1.0, f"Phase 3 done — {len(results)} analysed")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Chart builder (TradingView-style)
# ─────────────────────────────────────────────────────────────────────────────
def _tv_chart(res: dict) -> go.Figure:
    df_c  = res["df"].tail(60).copy()
    close = df_c["close"].astype(float)
    vol   = df_c["volume"].astype(float)
    ema20 = close.ewm(span=20, min_periods=1).mean()
    ema50 = close.ewm(span=50, min_periods=1).mean()

    fig = go.Figure()

    # Volume bars (background)
    colors_v = ["rgba(38,166,154,.25)" if close.iloc[i] >= close.iloc[max(i-1,0)]
                else "rgba(239,83,80,.25)" for i in range(len(close))]
    fig.add_trace(go.Bar(
        x=df_c["date"], y=vol, name="Volume", yaxis="y2",
        marker_color=colors_v, showlegend=False,
    ))

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df_c["date"],
        open=df_c["open"], high=df_c["high"],
        low=df_c["low"],   close=close,
        increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
        name="Price", showlegend=False,
    ))

    # EMAs
    fig.add_trace(go.Scatter(
        x=df_c["date"], y=ema20, name="EMA 20",
        line=dict(color="#ff9800", width=1.3, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=df_c["date"], y=ema50, name="EMA 50",
        line=dict(color="#2962ff", width=1.3),
    ))

    # S/R lines
    fig.add_hline(y=res["stop_loss"], line=dict(color="#ef5350", dash="dash", width=1),
                  annotation_text=f"SL {res['stop_loss']}", annotation_font_color="#ef5350",
                  annotation_font_size=10)
    fig.add_hline(y=res["target"], line=dict(color="#26a69a", dash="dash", width=1),
                  annotation_text=f"TGT {res['target']}", annotation_font_color="#26a69a",
                  annotation_font_size=10)

    fig.update_layout(
        height=350,
        template="plotly_dark",
        paper_bgcolor="#131722",
        plot_bgcolor="#131722",
        font=dict(family="Inter, Trebuchet MS", size=11, color="#787b86"),
        xaxis=dict(
            gridcolor="#1e222d", rangeslider_visible=False,
            showline=True, linecolor="#2a2e39",
        ),
        yaxis=dict(gridcolor="#1e222d", side="right", showline=True, linecolor="#2a2e39"),
        yaxis2=dict(overlaying="y", side="left", showgrid=False, visible=False,
                    range=[0, float(vol.max()) * 4]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        margin=dict(l=0, r=50, t=10, b=0),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Stock card renderer
# ─────────────────────────────────────────────────────────────────────────────
def render_stock_card(r: dict, show_chart: bool = True):
    chg_cls = "tv-change-up" if r["pct_chg"] >= 0 else "tv-change-down"
    chg_sign = "+" if r["pct_chg"] >= 0 else ""
    badge = ('<span class="tv-badge tv-buy">BUY ZONE</span>' if r["full_pass"]
             else '<span class="tv-badge tv-watch">WATCHLIST</span>')
    clean = ('<span class="tv-badge tv-clean">CLEAN</span>' if r["is_clean"]
             else '<span class="tv-badge tv-warn">FLAGS</span>')
    setup_parts = []
    if r["near_52w"]:
        setup_parts.append("Near 52W High")
    if r["breakout"]:
        setup_parts.append("Breakout")
    setup = " | ".join(setup_parts) if setup_parts else ""

    sl_pct = round((r["ltp"] - r["stop_loss"]) / r["ltp"] * 100, 1)
    tgt_pct = round((r["target"] - r["ltp"]) / r["ltp"] * 100, 1)

    st.markdown(f"""
<div class="tv-stock-card">
    <div class="tv-header">
        <span class="tv-ticker">{r['symbol']}</span>
        {badge} {clean}
        <span style="margin-left:auto; font-size:.8rem; color:#787b86">{r['trend']}</span>
    </div>
    <div style="display:flex; align-items:baseline; gap:12px; margin-bottom:6px;">
        <span class="tv-price">₹{r['ltp']}</span>
        <span class="{chg_cls}">{chg_sign}{r['pct_chg']}%</span>
        <span style="color:#787b86; font-size:.78rem">{setup}</span>
    </div>
    <div class="tv-risk-grid">
        <div class="tv-risk-item">
            <div class="tv-label">RSI(14)</div>
            <div class="tv-value">{r['rsi']}</div>
        </div>
        <div class="tv-risk-item">
            <div class="tv-label">Vol Surge</div>
            <div class="tv-value">{r['vol_surge']}x</div>
        </div>
        <div class="tv-risk-item">
            <div class="tv-label">Stop-Loss</div>
            <div class="tv-value" style="color:#ef5350">₹{r['stop_loss']} (-{sl_pct}%)</div>
        </div>
        <div class="tv-risk-item">
            <div class="tv-label">Target</div>
            <div class="tv-value" style="color:#26a69a">₹{r['target']} (+{tgt_pct}%)</div>
        </div>
        <div class="tv-risk-item">
            <div class="tv-label">R : R</div>
            <div class="tv-value">1 : {r['rr']}</div>
        </div>
        <div class="tv-risk-item">
            <div class="tv-label">ATR(14)</div>
            <div class="tv-value">₹{r['atr']}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    if show_chart and "df" in r and not r["df"].empty:
        st.plotly_chart(_tv_chart(r), use_container_width=True, key=f"chart_{r['symbol']}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN UI
# ═════════════════════════════════════════════════════════════════════════════

# Header
now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
is_market = 9 * 60 + 15 <= now_ist.hour * 60 + now_ist.minute <= 15 * 60 + 30
mkt_badge = ('<span class="tv-live">● MARKET OPEN</span>'
             if is_market else '<span style="color:#ef5350">● MARKET CLOSED</span>')

st.markdown(f"""
<div style="display:flex; align-items:center; gap:16px; margin-bottom:4px;">
    <span style="font-size:1.6rem; font-weight:700; color:#d1d4dc;">🎯 Aggressive Screener</span>
    {mkt_badge}
    <span style="margin-left:auto; color:#787b86; font-size:.82rem;">
        {now_ist.strftime('%d %b %Y  %H:%M IST')}
    </span>
</div>
<div style="color:#787b86; font-size:.82rem; margin-bottom:16px;">
    Full-Market NSE Scan · Shoonya Live API ·
    6-Criteria + Anti-Manipulation · ATR Risk Management
</div>
""", unsafe_allow_html=True)

# Login
api, login_info = get_shoonya_api()
if not api:
    st.error(f"Shoonya login failed: {login_info}")
    st.stop()

# Load scripmaster
with st.spinner("Loading NSE scripmaster (all equities)..."):
    scripmaster = load_nse_scripmaster()

if scripmaster.empty:
    st.error("Could not load NSE scripmaster. Check internet connection.")
    st.stop()

total_stocks = len(scripmaster)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding:8px 0;">
        <div style="font-size:.75rem; color:#787b86;">LOGGED IN</div>
        <div style="font-size:.95rem; font-weight:600; color:#d1d4dc;">{login_info}</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### Settings")

    price_min = st.slider("Min Price", 5, 100, 20, format="₹%d")
    price_max = st.slider("Max Price", 50, 500, 150, format="₹%d")
    min_vol   = st.number_input("Min 20d Avg Volume", value=1_000_000, step=100_000,
                                format="%d")
    min_show  = st.slider("Min criteria for watchlist", 3, 6, 5)
    show_ch   = st.checkbox("Show charts", value=True)

    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center;">
        <div style="font-size:2rem; font-weight:700; color:#2962ff;">{total_stocks:,}</div>
        <div style="font-size:.78rem; color:#787b86;">NSE Equities Loaded</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    run_btn = st.button("🚀 SCAN ENTIRE MARKET", type="primary", use_container_width=True)

    st.caption(
        "Estimated time: ~3-5 min for full market.\n"
        "Run during market hours for live volume signals."
    )

# ── Criteria info ─────────────────────────────────────────────────────────────
with st.expander("📋 Screening Criteria & Risk Rules", expanded=False):
    st.markdown(f"""
| # | Filter | Rule |
|---|--------|------|
| 1 | **Price** | ₹{price_min} - ₹{price_max} |
| 2 | **Liquidity** | 20d avg vol > {min_vol:,} |
| 3 | **Volume Surge** | Today vol > 3x 20d avg |
| 4 | **Momentum** | RSI(14): 60 - 80 |
| 5 | **Price Action** | Within 2% of 52W high OR 4-week consolidation breakout |
| 6 | **Circuit** | No upper/lower circuit in last 5 sessions |
| + | **Anti-Manipulation** | No pump, no spike+dump, no frozen candles, no erratic volume |

**Risk**: SL = min(5% hard, 1.5x ATR) floored at support. Target = nearest resistance or +20%
    """)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# Scan execution
# ═════════════════════════════════════════════════════════════════════════════
if run_btn:
    t0 = time.time()
    prog = st.progress(0)
    status = st.empty()

    def update_progress(pct, msg):
        prog.progress(min(pct, 1.0))
        status.markdown(f"<div style='color:#787b86; font-size:.85rem;'>{msg}</div>",
                        unsafe_allow_html=True)

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    update_progress(0, f"Phase 1: Scanning {total_stocks:,} stocks for price ₹{price_min}-{price_max}...")
    p1 = phase1_price_filter(api, scripmaster, price_min, price_max, update_progress)

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    update_progress(0, f"Phase 2: Volume pre-filter on {len(p1)} stocks...")
    p2 = phase2_volume_filter(p1, min_vol)
    update_progress(1.0, f"Phase 2 done — {len(p2)} pass volume pre-filter")

    # ── Phase 3 ───────────────────────────────────────────────────────────────
    update_progress(0, f"Phase 3: Deep analysis on {len(p2)} stocks...")
    p3 = phase3_deep_analysis(api, p2, update_progress)

    elapsed = round(time.time() - t0, 1)
    prog.empty()
    status.empty()

    # Categorise
    actionable = sorted([r for r in p3 if r["full_pass"]],
                        key=lambda x: x["rr"], reverse=True)
    watchlist  = sorted([r for r in p3 if not r["full_pass"] and r["crit_met"] >= min_show],
                        key=lambda x: x["crit_met"], reverse=True)

    # ── Summary bar ───────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="background:#1e222d; border:1px solid #2a2e39; border-radius:10px;
            padding:16px 24px; display:flex; justify-content:space-between;
            align-items:center; margin:12px 0;">
    <div style="text-align:center;">
        <div style="font-size:1.5rem; font-weight:700; color:#2962ff;">{total_stocks:,}</div>
        <div style="font-size:.72rem; color:#787b86;">SCANNED</div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:1.5rem; font-weight:700; color:#d1d4dc;">{len(p1)}</div>
        <div style="font-size:.72rem; color:#787b86;">IN PRICE RANGE</div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:1.5rem; font-weight:700; color:#ffb74d;">{len(p2)}</div>
        <div style="font-size:.72rem; color:#787b86;">VOLUME OK</div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:1.5rem; font-weight:700; color:#26a69a;">{len(actionable)}</div>
        <div style="font-size:.72rem; color:#787b86;">ACTIONABLE</div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:1.5rem; font-weight:700; color:#ffb74d;">{len(watchlist)}</div>
        <div style="font-size:.72rem; color:#787b86;">WATCHLIST</div>
    </div>
    <div style="text-align:center;">
        <div style="font-size:.9rem; color:#787b86;">{elapsed}s</div>
        <div style="font-size:.72rem; color:#787b86;">ELAPSED</div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── No results ────────────────────────────────────────────────────────────
    if not actionable and not watchlist:
        st.markdown("""
<div style="background:#1e222d; border:1px solid #ef5350; border-radius:10px;
            padding:24px; text-align:center; margin:16px 0;">
    <div style="font-size:1.3rem; font-weight:700; color:#ef5350;">HOLD CASH</div>
    <div style="color:#787b86; margin-top:8px;">
        No stocks pass all 6 criteria with clean manipulation status.<br>
        Run during market hours (9:15-15:30 IST) for live volume data.
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Actionable ────────────────────────────────────────────────────────────
    if actionable:
        st.markdown(f"""
<div style="margin:20px 0 10px;">
    <span style="font-size:1.2rem; font-weight:700; color:#26a69a;">
        ACTIONABLE — {len(actionable)} Stock{'s' if len(actionable)>1 else ''}
    </span>
    <span style="color:#787b86; font-size:.82rem; margin-left:8px;">
        All 6 criteria passed - No manipulation flags - Trade-ready
    </span>
</div>
""", unsafe_allow_html=True)

        # Summary table
        tbl = []
        for r in actionable:
            chg_s = f"+{r['pct_chg']}%" if r["pct_chg"] >= 0 else f"{r['pct_chg']}%"
            tbl.append({
                "Symbol":    r["symbol"],
                "LTP":       r["ltp"],
                "Change":    chg_s,
                "RSI":       r["rsi"],
                "VolSurge":  r["vol_surge"],
                "SL":        r["stop_loss"],
                "TGT":       r["target"],
                "R:R":       r["rr"],
                "Trend":     r["trend"],
            })
        st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

        # Cards
        for r in actionable:
            render_stock_card(r, show_chart=show_ch)

            with st.expander(f"📐 {r['symbol']} — Full Detail"):
                dc1, dc2, dc3 = st.columns(3)
                for j, (name, val) in enumerate(r["criteria"].items()):
                    [dc1, dc2, dc3][j % 3].markdown(f"{'✅' if val else '❌'} {name}")
                st.markdown(f"""
| Field | Value |  | Field | Value |
|-------|-------|--|-------|-------|
| Entry | ₹{r['ltp']} | | ATR(14) | ₹{r['atr']} |
| Stop-Loss | ₹{r['stop_loss']} (-{round((r['ltp']-r['stop_loss'])/r['ltp']*100,1)}%) | | EMA20 | ₹{r['ema20']} |
| Target | ₹{r['target']} (+{round((r['target']-r['ltp'])/r['ltp']*100,1)}%) | | EMA50 | ₹{r['ema50']} |
| Risk | ₹{r['risk']} | | 52W High | ₹{r['h52']} |
| Reward | ₹{r['reward']} | | Avg 20d Vol | {r['avg_vol20']:,} |
| R:R | 1 : {r['rr']} | | Today Vol | {r['today_vol']:,} |
                """)

    # ── Watchlist ─────────────────────────────────────────────────────────────
    if watchlist:
        st.markdown(f"""
<div style="margin:24px 0 10px;">
    <span style="font-size:1.2rem; font-weight:700; color:#ffb74d;">
        WATCHLIST — {len(watchlist)} Stock{'s' if len(watchlist)>1 else ''}
    </span>
    <span style="color:#787b86; font-size:.82rem; margin-left:8px;">
        {min_show}+ criteria met - Monitor for entry
    </span>
</div>
""", unsafe_allow_html=True)

        wl_tbl = []
        for r in watchlist:
            chg_s = f"+{r['pct_chg']}%" if r["pct_chg"] >= 0 else f"{r['pct_chg']}%"
            wl_tbl.append({
                "Symbol":   r["symbol"],
                "LTP":      r["ltp"],
                "Change":   chg_s,
                "RSI":      r["rsi"],
                "VolSurge": r["vol_surge"],
                "Criteria": f"{r['crit_met']}/6",
                "SL":       r["stop_loss"],
                "TGT":      r["target"],
                "R:R":      r["rr"],
                "Flags":    " | ".join(r["m_flags"]) or "Clean",
            })
        st.dataframe(pd.DataFrame(wl_tbl), use_container_width=True, hide_index=True)

        for r in watchlist:
            render_stock_card(r, show_chart=show_ch)

    # ── Full scan log ─────────────────────────────────────────────────────────
    with st.expander(f"📋 Full Scan Log — {len(p3)} stocks deep-analysed"):
        log_tbl = [{
            "Symbol":  r["symbol"],
            "LTP":     r["ltp"],
            "RSI":     r["rsi"],
            "VolSurge":r["vol_surge"],
            "Crit":    f"{r['crit_met']}/6",
            "Clean":   "Y" if r["is_clean"] else "N",
            "Flags":   ", ".join(r["m_flags"][:2]) or "-",
        } for r in sorted(p3, key=lambda x: x["crit_met"], reverse=True)]
        st.dataframe(pd.DataFrame(log_tbl), use_container_width=True, hide_index=True)

else:
    # ── Landing page ──────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="background:#1e222d; border:1px solid #2a2e39; border-radius:12px;
            padding:30px; text-align:center; margin:20px 0;">
    <div style="font-size:2.5rem; font-weight:700; color:#2962ff;">{total_stocks:,}</div>
    <div style="color:#787b86; font-size:1rem; margin-top:4px;">NSE Equities Ready to Scan</div>
    <div style="margin-top:16px; color:#787b86; font-size:.85rem;">
        Click <b style="color:#2962ff;">SCAN ENTIRE MARKET</b> in the sidebar to begin
    </div>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
<div class="tv-stock-card" style="text-align:center;">
    <div style="font-size:1.5rem;">⚡</div>
    <div style="font-weight:600; color:#d1d4dc; margin:6px 0;">3-Phase Progressive Scan</div>
    <div style="color:#787b86; font-size:.82rem;">
        Price filter → Volume filter → Deep analysis<br>
        Scans 2,400+ stocks in ~3 min
    </div>
</div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
<div class="tv-stock-card" style="text-align:center;">
    <div style="font-size:1.5rem;">🛡️</div>
    <div style="font-weight:600; color:#d1d4dc; margin:6px 0;">Anti-Manipulation Guard</div>
    <div style="color:#787b86; font-size:.82rem;">
        Pump detection · Spike+dump filter<br>
        Circuit guard · Operator volume check
    </div>
</div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""
<div class="tv-stock-card" style="text-align:center;">
    <div style="font-size:1.5rem;">📐</div>
    <div style="font-weight:600; color:#d1d4dc; margin:6px 0;">Smart Risk Management</div>
    <div style="color:#787b86; font-size:.82rem;">
        ATR-based stop-loss · Swing S/R levels<br>
        R:R ratio · Position sizing ready
    </div>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div style="background:#131722; border:1px solid #2a2e39; border-radius:8px;
            padding:16px 20px; margin-top:16px; color:#787b86; font-size:.82rem;">
    <b style="color:#ffb74d;">Best during market hours (9:15-15:30 IST)</b><br>
    Volume surge criterion is only meaningful with live intraday volume data.
    After-hours scans won't trigger Volume Surge 3x criteria.
</div>
""", unsafe_allow_html=True)
