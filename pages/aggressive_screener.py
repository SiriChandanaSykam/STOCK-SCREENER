"""
pages/aggressive_screener.py

🎯 Full-Market Aggressive Screener — TradingView Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Exchanges  : NSE (EQ + SME + BE) + BSE (A, B, M, T, Z groups)
Indices    : NIFTY 50 · BANK NIFTY · FINNIFTY · MIDCAP NIFTY · INDIA VIX · NIFTY NEXT 50
Universe   : ~5 300+ stocks (all penny, micro, small, mid-cap)
Live data  : Shoonya (Finvasia) API — 100 % live
"""

from __future__ import annotations

import io, os, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pyotp
import requests as _requests
import streamlit as st
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="🎯 Full Market Screener", layout="wide", page_icon="🎯")

# ═══════════════════════════════════════════════════════════════════════════
# TRADINGVIEW CSS — pixel-perfect dark theme
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root {
  --tv-bg:         #131722;
  --tv-bg2:        #1e222d;
  --tv-bg3:        #1c2030;
  --tv-border:     #2a2e39;
  --tv-text:       #d1d4dc;
  --tv-text2:      #787b86;
  --tv-blue:       #2962ff;
  --tv-blue-glow:  rgba(41,98,255,.35);
  --tv-green:      #26a69a;
  --tv-red:        #ef5350;
  --tv-orange:     #ff9800;
  --tv-yellow:     #ffb74d;
  --tv-green-bg:   rgba(38,166,154,.12);
  --tv-red-bg:     rgba(239,83,80,.12);
}

/* ── Reset & Global ─────────────────────────────────────────── */
[data-testid="stAppViewContainer"]       { background: var(--tv-bg) !important; }
[data-testid="stSidebar"]               { background: var(--tv-bg2) !important; border-right: 1px solid var(--tv-border); }
[data-testid="stHeader"], header         { background: transparent !important; }
section[data-testid="stSidebar"] > div   { padding-top: .6rem; }
html, body, [class*="css"]              { font-family: 'Inter', -apple-system, sans-serif !important; color: var(--tv-text); }

h1, h2, h3 { color: var(--tv-text) !important; font-weight: 700 !important; letter-spacing: -.5px; }
h1 { font-size: 1.55rem !important; }
h2 { font-size: 1.15rem !important; }
h3 { font-size: 1.0rem !important; }
hr { border-color: var(--tv-border) !important; margin: 8px 0 !important; }

/* ── Metric cards ─────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--tv-bg2); border: 1px solid var(--tv-border); border-radius: 8px;
  padding: 10px 14px; box-shadow: 0 2px 8px rgba(0,0,0,.25);
}
[data-testid="stMetricLabel"]  { color: var(--tv-text2) !important; font-size: .72rem !important; text-transform: uppercase; letter-spacing: .5px; }
[data-testid="stMetricValue"]  { color: var(--tv-text) !important; font-size: 1.05rem !important; font-weight: 700 !important; }

/* ── Dataframes ───────────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
[data-testid="stDataFrame"] th { background: #2a2e39 !important; color: var(--tv-text2) !important; font-weight: 600; font-size: .72rem; text-transform: uppercase; letter-spacing: .4px; }
[data-testid="stDataFrame"] td { border-color: var(--tv-border) !important; font-size: .8rem; }

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {
  background: linear-gradient(135deg, #2962ff, #1e53e5) !important; color: #fff !important;
  border: none !important; border-radius: 8px !important; font-weight: 600 !important;
  padding: .55rem .9rem !important; transition: all .2s ease; letter-spacing: .3px;
}
.stButton > button:hover { box-shadow: 0 0 24px var(--tv-blue-glow) !important; transform: translateY(-1px); }

/* ── Expanders ────────────────────────────────────────────── */
[data-testid="stExpander"]       { background: var(--tv-bg2); border: 1px solid var(--tv-border); border-radius: 8px; }
[data-testid="stExpanderToggle"] { color: var(--tv-text2) !important; }
.stAlert { border-radius: 8px !important; }
[data-testid="stProgress"] > div > div { background: var(--tv-blue) !important; }

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid var(--tv-border); }
.stTabs [data-baseweb="tab"]      {
  background: transparent; color: var(--tv-text2); border: none;
  padding: 8px 18px; font-weight: 500; font-size: .85rem; border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] { color: var(--tv-blue) !important; border-bottom: 2px solid var(--tv-blue) !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 12px; }

/* ── Scrollbar ────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--tv-bg); }
::-webkit-scrollbar-thumb { background: #434651; border-radius: 3px; }

/* ── Ticker tape ──────────────────────────────────────────── */
.tv-tape { display: flex; gap: 24px; overflow-x: auto; padding: 10px 0; }
.tv-tape-item {
  flex-shrink: 0; background: var(--tv-bg2); border: 1px solid var(--tv-border);
  border-radius: 8px; padding: 10px 18px; min-width: 160px; text-align: center;
  transition: border-color .2s;
}
.tv-tape-item:hover { border-color: var(--tv-blue); }
.tv-tape-name  { font-size: .7rem; color: var(--tv-text2); font-weight: 500; text-transform: uppercase; letter-spacing: .5px; }
.tv-tape-price { font-size: 1.15rem; font-weight: 700; color: var(--tv-text); margin: 2px 0; }
.tv-tape-chg   { font-size: .78rem; font-weight: 600; }
.tv-up   { color: var(--tv-green); }
.tv-down { color: var(--tv-red); }
.tv-flat { color: var(--tv-text2); }

/* ── Stock cards ──────────────────────────────────────────── */
.tv-card {
  background: var(--tv-bg2); border: 1px solid var(--tv-border); border-radius: 10px;
  padding: 16px 20px; margin: 6px 0; box-shadow: 0 4px 16px rgba(0,0,0,.2);
  transition: border-color .2s, box-shadow .2s;
}
.tv-card:hover { border-color: var(--tv-blue); box-shadow: 0 4px 24px var(--tv-blue-glow); }
.tv-row  { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.tv-sym  { font-size: 1.1rem; font-weight: 700; color: var(--tv-text); letter-spacing: -.3px; }
.tv-exch { font-size: .65rem; color: var(--tv-text2); background: var(--tv-bg); border-radius: 3px; padding: 1px 6px; font-weight: 600; }
.tv-badge { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: .68rem; font-weight: 600; letter-spacing: .4px; }
.tv-buy    { background: var(--tv-green-bg); color: var(--tv-green); border: 1px solid var(--tv-green); }
.tv-watch  { background: rgba(255,183,77,.12); color: var(--tv-yellow); border: 1px solid var(--tv-yellow); }
.tv-clean  { background: var(--tv-green-bg); color: var(--tv-green); }
.tv-dirty  { background: var(--tv-red-bg); color: var(--tv-red); }
.tv-price  { font-size: 1.4rem; font-weight: 700; color: var(--tv-text); }
.tv-lbl    { color: var(--tv-text2); font-size: .7rem; font-weight: 500; text-transform: uppercase; letter-spacing: .3px; }
.tv-val    { color: var(--tv-text); font-size: .85rem; font-weight: 600; }
.tv-grid   { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 6px; margin-top: 10px; }
.tv-cell   { background: var(--tv-bg); border-radius: 6px; padding: 7px 10px; text-align: center; }

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }
.tv-live { animation: pulse 2s infinite; color: var(--tv-green); font-weight: 700; font-size: .8rem; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SHOONYA LOGIN (cached per session)
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def _login():
    try:
        from NorenRestApiPy.NorenApi import NorenApi
    except ImportError:
        return None, "NorenRestApiPy not installed"
    env_path = Path(__file__).resolve().parent.parent / "shoonya.env"
    load_dotenv(dotenv_path=env_path, override=True)
    uid   = os.getenv("SHOONYA_USER_ID", "")
    pwd   = os.getenv("SHOONYA_PASSWORD", "")
    totp  = os.getenv("SHOONYA_TOTP_SECRET", "").replace("-", "").replace(" ", "").strip()
    vc    = os.getenv("SHOONYA_VENDOR_CODE", "")
    api_s = os.getenv("SHOONYA_API_SECRET", "")
    imei  = os.getenv("SHOONYA_IMEI", "")
    twoFA = totp if totp.isdigit() else pyotp.TOTP(totp.upper()).now()

    class _A(NorenApi):
        def __init__(self):
            super().__init__(host="https://api.shoonya.com/NorenWClientTP/",
                             websocket="wss://api.shoonya.com/NorenWSTP/")
    api = _A()
    ret = api.login(userid=uid, password=pwd, twoFA=twoFA,
                    vendor_code=vc, api_secret=api_s, imei=imei)
    if ret and ret.get("stat") == "Ok":
        return api, ret.get("uname", uid)
    return None, ret.get("emsg") if ret else "No response"


# ═══════════════════════════════════════════════════════════════════════════
# SCRIPMASTER LOADER — NSE + BSE (cached daily)
# ═══════════════════════════════════════════════════════════════════════════
INDICES = [
    ("NIFTY 50",      "NSE", "26000"),
    ("BANK NIFTY",    "NSE", "26009"),
    ("FINNIFTY",      "NSE", "26037"),
    ("MIDCAP NIFTY",  "NSE", "26074"),
    ("NIFTY NEXT 50", "NSE", "26013"),
    ("INDIA VIX",     "NSE", "26017"),
]

@st.cache_data(ttl=86400, show_spinner=False)
def _load_scripmaster():
    """Download NSE + BSE scripmaster ZIPs, return combined EQ DataFrame."""
    all_rows = []
    configs = [
        ("NSE", "https://api.shoonya.com/NSE_symbols.txt.zip",
         {"EQ", "SM", "ST", "BE"}),          # equity, SME, startup, trade-to-trade
        ("BSE", "https://api.shoonya.com/BSE_symbols.txt.zip",
         {"A", "B", "M", "T", "Z"}),         # all BSE groups
    ]
    for exch, url, valid_inst in configs:
        try:
            r = _requests.get(url, timeout=25)
            if r.status_code != 200 or len(r.content) < 2000:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            txt = z.read(z.namelist()[0]).decode("utf-8", "replace")
            lines = txt.strip().split("\n")
            hdr = [h.strip() for h in lines[0].split(",")]
            for ln in lines[1:]:
                parts = ln.split(",")
                if len(parts) < len(hdr):
                    continue
                row = dict(zip(hdr, [p.strip() for p in parts]))
                inst = row.get("Instrument", "")
                if inst in valid_inst:
                    row["Exchange"] = exch
                    # Normalise symbol
                    sym = row.get("Symbol", row.get("TradingSymbol", ""))
                    tsym = row.get("TradingSymbol", sym)
                    row["CleanSymbol"] = (
                        sym.replace("-EQ", "").replace("-BE", "")
                           .replace("-SM", "").replace("-ST", "").strip()
                    )
                    row["TradSym"] = tsym
                    all_rows.append(row)
        except Exception:
            continue
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df["Token"] = df["Token"].astype(str)
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _q(api, exch, token):
    try:
        r = api.get_quotes(exchange=exch, token=str(token))
        if r and r.get("stat") == "Ok":
            return {
                "ltp":  float(r.get("lp",0) or 0),
                "vol":  int(r.get("v",0) or 0),
                "h52":  float(r.get("h52",0) or 0),
                "l52":  float(r.get("l52",0) or 0),
                "open": float(r.get("o",0) or 0),
                "high": float(r.get("h",0) or 0),
                "low":  float(r.get("l",0) or 0),
                "pc":   float(r.get("pc",0) or 0),
                "pdcl": float(r.get("pdcl",0) or 0),
            }
    except Exception:
        pass
    return {}


def _ohlcv(api, exch, token, days=290):
    end = datetime.now()
    start = end - timedelta(days=int(days * 1.5))
    try:
        raw = api.get_time_price_series(
            exchange=exch, token=str(token),
            starttime=start.strftime("%d-%m-%Y %H:%M:%S"),
            endtime=end.strftime("%d-%m-%Y %H:%M:%S"),
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


# ═══════════════════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════════════════
def _rsi(c, n=14):
    d = c.diff()
    g = d.clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    l = (-d).clip(lower=0).ewm(com=n-1, min_periods=n).mean()
    return float((100 - 100/(1+g/l.replace(0,1e-10))).iloc[-1]) if len(c) >= n else 0

def _atr(df, n=14):
    tr = pd.concat([df["high"]-df["low"],
                     (df["high"]-df["close"].shift(1)).abs(),
                     (df["low"]-df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return float(tr.ewm(com=n-1, min_periods=n).mean().iloc[-1])

def _ema(s, n):
    return float(s.ewm(span=n, min_periods=1).mean().iloc[-1])


# ═══════════════════════════════════════════════════════════════════════════
# CRITERIA CHECKS
# ═══════════════════════════════════════════════════════════════════════════
def _consol_breakout(df):
    if len(df) < 25: return False
    c = df.tail(21).iloc[:-1]
    mx, mn = float(c["close"].max()), float(c["close"].min())
    return mn > 0 and (mx-mn)/mn < 0.08 and float(df["close"].iloc[-1]) > mx

def _circuit_hit(df, n=5):
    if len(df) < n+2: return False
    r = df.tail(n+1)
    pct = r["close"].pct_change().abs()
    hl  = (r["high"]-r["low"])/r["close"].replace(0,1e-10)
    return bool((pct.tail(n)>=.19).any() | (hl.tail(n)<.001).any())

def _manip(df, ltp):
    if len(df) < 20: return []
    fl = []; c = df["close"].astype(float); v = df["volume"].astype(float)
    tr = float(c.tail(20).min())
    if tr > 0 and (ltp-tr)/tr > .50: fl.append(f"PUMP +{round((ltp-tr)/tr*100)}%")
    pct = c.pct_change().tail(12).values
    for i in range(len(pct)-1):
        if pct[i] > .15 and pct[i+1] < -.05: fl.append("Spike+Dump"); break
    zd = int((v.tail(20)==0).sum())
    if zd > 2: fl.append(f"{zd} zero-vol")
    mu = float(v.tail(20).mean()); sd = float(v.tail(20).std())
    if mu > 0 and sd/mu > 3: fl.append("Erratic vol")
    hl = ((df["high"]-df["low"])/df["close"].replace(0,1e-10)).tail(10)
    if int((hl<.005).sum()) > 2: fl.append("Frozen")
    return fl

def _sr(df, ltp):
    c = df["close"].astype(float)
    e20, e50 = _ema(c,20), _ema(c,50)
    rl = float(df["low"].tail(20).min())
    rh = float(df["high"].tail(60).max())
    h52 = float(c.tail(252).max())
    sc = [s for s in [rl,e20,e50] if 0<s<ltp]
    sup = max(sc) if sc else round(ltp*.95,2)
    rc = [r for r in [h52,rh] if r>ltp]
    res = min(rc) if rc else round(ltp*1.20,2)
    return round(sup,2), round(res,2), round(e20,2), round(e50,2)


# ═══════════════════════════════════════════════════════════════════════════
# PROGRESSIVE SCAN ENGINE
# ═══════════════════════════════════════════════════════════════════════════
def phase1(api, df, pmin, pmax, cb=None):
    results = []; total = len(df)
    def _one(row):
        q = _q(api, row["Exchange"], row["Token"])
        if q and pmin <= q["ltp"] <= pmax:
            return {**row.to_dict(), **q}
        return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(_one, r): i for i, r in df.iterrows()}
        done = 0
        for f in as_completed(futs):
            done += 1
            if cb and done % 50 == 0:
                cb(done/total, f"Phase 1 · price scan {done:,}/{total:,}")
            r = f.result()
            if r: results.append(r)
    if cb: cb(1.0, f"Phase 1 done — {len(results):,} in price range")
    return results

def phase2(results, min_vol):
    return [r for r in results if r.get("vol",0) >= min_vol // 5]

def phase3(api, cands, cb=None):
    out = []; total = len(cands)
    for i, cd in enumerate(cands):
        if cb and i % 3 == 0:
            cb(i/max(total,1), f"Phase 3 · deep {i}/{total} — {cd.get('CleanSymbol','')}")
        exch, tok, sym, ltp = cd["Exchange"], cd["Token"], cd.get("CleanSymbol",""), cd.get("ltp",0)
        df = _ohlcv(api, exch, tok, 290)
        if df.empty or len(df) < 50: continue
        # inject live
        td = pd.Timestamp.now().normalize()
        ld = df.iloc[-1]["date"]
        if hasattr(ld,"normalize") and ld.normalize()==td:
            df.loc[df.index[-1],"close"] = ltp
            if cd.get("vol",0)>0: df.loc[df.index[-1],"volume"] = cd["vol"]
        c = df["close"].astype(float); v = df["volume"].astype(float)
        av20 = float(v.tail(20).mean()); rsi = _rsi(c); e20 = _ema(c,20); e50 = _ema(c,50)
        atr = _atr(df); h52 = float(c.tail(252).max()); tv = cd.get("vol", int(v.iloc[-1]))
        vs = tv/max(av20,1); n52 = h52>0 and ltp>=.98*h52; bo = _consol_breakout(df)
        cir = _circuit_hit(df); mf = _manip(df, ltp)
        crit = {"Price": 20<=ltp<=150, "AvgVol>1M": av20>=1e6, "VolSurge3x": vs>=3,
                "RSI60-80": 60<rsi<80, "52W/BO": n52 or bo, "NoCircuit": not cir}
        cm = sum(crit.values()); clean = len(mf)==0; fp = cm==6 and clean
        sup,res_l,_,_ = _sr(df,ltp)
        sl = min(max(min(ltp*.95, ltp-1.5*atr), sup), ltp*.95)
        tgt = res_l if ltp<res_l<=ltp*1.32 else ltp*1.20
        risk = ltp-sl; rew = tgt-ltp; rr = round(rew/max(risk,.01),2)
        trend = "UP" if ltp>e50 and e20>e50 else ("SIDE" if ltp>e50 else "DOWN")
        pdcl = cd.get("pdcl", ltp); pchg = round((ltp-pdcl)/max(pdcl,.01)*100, 1)
        out.append({
            "symbol": sym, "token": tok, "exchange": exch,
            "ltp": round(ltp,2), "pct_chg": pchg, "rsi": round(rsi,1),
            "ema20": round(e20,2), "ema50": round(e50,2), "atr": round(atr,2),
            "avg_vol20": int(av20), "today_vol": tv, "vol_surge": round(vs,1),
            "h52": round(h52,2), "near_52w": n52, "breakout": bo, "circuit": cir,
            "support": sup, "resistance": res_l, "stop_loss": round(sl,2),
            "target": round(tgt,2), "risk": round(risk,2), "reward": round(rew,2),
            "rr": rr, "trend": trend, "criteria": crit, "crit_met": cm,
            "full_pass": fp, "is_clean": clean, "m_flags": mf, "df": df,
        })
        time.sleep(0.2)
    if cb: cb(1.0, f"Phase 3 done — {len(out)} analysed")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# CHART BUILDERS
# ═══════════════════════════════════════════════════════════════════════════
def _tv_chart(res, height=340):
    d = res["df"].tail(60).copy()
    c = d["close"].astype(float); v = d["volume"].astype(float)
    e20 = c.ewm(span=20, min_periods=1).mean()
    e50 = c.ewm(span=50, min_periods=1).mean()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.78,.22],
                        vertical_spacing=0.02)
    # Volume
    vc = [f"rgba(38,166,154,.3)" if c.iloc[i]>=c.iloc[max(i-1,0)]
          else f"rgba(239,83,80,.3)" for i in range(len(c))]
    fig.add_trace(go.Bar(x=d["date"], y=v, marker_color=vc, showlegend=False), row=2, col=1)
    # Candles
    fig.add_trace(go.Candlestick(
        x=d["date"], open=d["open"], high=d["high"], low=d["low"], close=c,
        increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
        decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
        showlegend=False), row=1, col=1)
    # EMAs
    fig.add_trace(go.Scatter(x=d["date"], y=e20, name="EMA 20",
                             line=dict(color="#ff9800", width=1.2, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=d["date"], y=e50, name="EMA 50",
                             line=dict(color="#2962ff", width=1.2)), row=1, col=1)
    # SL / TGT
    fig.add_hline(y=res["stop_loss"], line=dict(color="#ef5350", dash="dash", width=1),
                  annotation_text=f"SL ₹{res['stop_loss']}", annotation_font_color="#ef5350",
                  annotation_font_size=9, row=1, col=1)
    fig.add_hline(y=res["target"], line=dict(color="#26a69a", dash="dash", width=1),
                  annotation_text=f"TGT ₹{res['target']}", annotation_font_color="#26a69a",
                  annotation_font_size=9, row=1, col=1)
    fig.update_layout(
        height=height, template="plotly_dark", paper_bgcolor="#131722", plot_bgcolor="#131722",
        font=dict(family="Inter", size=10, color="#787b86"),
        xaxis2=dict(gridcolor="#1e222d", showline=True, linecolor="#2a2e39"),
        yaxis=dict(gridcolor="#1e222d", side="right", showline=True, linecolor="#2a2e39"),
        yaxis2=dict(gridcolor="#1e222d", showticklabels=False),
        xaxis=dict(gridcolor="#1e222d", rangeslider_visible=False),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)",
                    font=dict(size=9)),
        margin=dict(l=0, r=50, t=6, b=0),
    )
    return fig


def _index_chart(api, name, exch, token, height=260):
    df = _ohlcv(api, exch, token, 120)
    if df.empty or len(df) < 5:
        return None
    c = df["close"].astype(float)
    v = df["volume"].astype(float)
    e20 = c.ewm(span=20, min_periods=1).mean()
    color = "#26a69a" if float(c.iloc[-1]) >= float(c.iloc[-2]) else "#ef5350"
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.8,.2],
                        vertical_spacing=0.02)
    fig.add_trace(go.Scatter(x=df["date"], y=c, name=name,
                             line=dict(color=color, width=1.8),
                             fill="tozeroy", fillcolor=color.replace(")", ",.06)").replace("rgb","rgba")),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=e20, name="EMA 20",
                             line=dict(color="#787b86", width=1, dash="dot")), row=1, col=1)
    vc = ["rgba(100,100,100,.3)"] * len(v)
    fig.add_trace(go.Bar(x=df["date"], y=v, marker_color=vc, showlegend=False), row=2, col=1)
    fig.update_layout(
        height=height, template="plotly_dark", paper_bgcolor="#131722", plot_bgcolor="#131722",
        font=dict(family="Inter", size=9, color="#787b86"),
        yaxis=dict(gridcolor="#1e222d", side="right"), yaxis2=dict(showticklabels=False, gridcolor="#1e222d"),
        xaxis=dict(gridcolor="#1e222d", rangeslider_visible=False), xaxis2=dict(gridcolor="#1e222d"),
        legend=dict(orientation="h", y=1.03, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)", font=dict(size=9)),
        margin=dict(l=0, r=40, t=4, b=0),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# CARD RENDERER
# ═══════════════════════════════════════════════════════════════════════════
def _card(r, chart=True):
    chg_cls = "tv-up" if r["pct_chg"] >= 0 else "tv-down"
    chg_s   = f"+{r['pct_chg']}%" if r["pct_chg"] >= 0 else f"{r['pct_chg']}%"
    badge   = '<span class="tv-badge tv-buy">BUY ZONE</span>' if r["full_pass"] else '<span class="tv-badge tv-watch">WATCHLIST</span>'
    cl_badge = '<span class="tv-badge tv-clean">CLEAN</span>' if r["is_clean"] else '<span class="tv-badge tv-dirty">FLAGS</span>'
    tags = []
    if r["near_52w"]: tags.append("52W HIGH")
    if r["breakout"]: tags.append("BREAKOUT")
    tag_html = " ".join(f'<span style="color:#787b86;font-size:.68rem;background:#131722;padding:1px 6px;border-radius:3px">{t}</span>' for t in tags)
    sl_p = round((r["ltp"]-r["stop_loss"])/r["ltp"]*100,1)
    tgt_p = round((r["target"]-r["ltp"])/r["ltp"]*100,1)

    st.markdown(f"""
<div class="tv-card">
  <div class="tv-row" style="margin-bottom:6px;">
    <span class="tv-sym">{r['symbol']}</span>
    <span class="tv-exch">{r['exchange']}</span>
    {badge} {cl_badge} {tag_html}
    <span style="margin-left:auto;font-size:.75rem;color:#787b86">{r['trend']}</span>
  </div>
  <div class="tv-row" style="margin-bottom:8px;">
    <span class="tv-price">₹{r['ltp']}</span>
    <span class="{chg_cls}" style="font-size:.9rem;font-weight:600">{chg_s}</span>
  </div>
  <div class="tv-grid">
    <div class="tv-cell"><div class="tv-lbl">RSI</div><div class="tv-val">{r['rsi']}</div></div>
    <div class="tv-cell"><div class="tv-lbl">Vol Surge</div><div class="tv-val">{r['vol_surge']}×</div></div>
    <div class="tv-cell"><div class="tv-lbl">Stop-Loss</div><div class="tv-val" style="color:#ef5350">₹{r['stop_loss']} <small>−{sl_p}%</small></div></div>
    <div class="tv-cell"><div class="tv-lbl">Target</div><div class="tv-val" style="color:#26a69a">₹{r['target']} <small>+{tgt_p}%</small></div></div>
    <div class="tv-cell"><div class="tv-lbl">R : R</div><div class="tv-val">1 : {r['rr']}</div></div>
    <div class="tv-cell"><div class="tv-lbl">ATR</div><div class="tv-val">₹{r['atr']}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

    if chart and "df" in r and not r["df"].empty:
        st.plotly_chart(_tv_chart(r), use_container_width=True, key=f"ch_{r['exchange']}_{r['symbol']}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN UI
# ═══════════════════════════════════════════════════════════════════════════
now = datetime.utcnow() + timedelta(hours=5, minutes=30)
is_mkt = 9*60+15 <= now.hour*60+now.minute <= 15*60+30
mkt_html = '<span class="tv-live">● LIVE</span>' if is_mkt else '<span style="color:#ef5350;font-weight:600;font-size:.8rem">● CLOSED</span>'

st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:2px;">
  <span style="font-size:1.5rem;font-weight:800;color:#d1d4dc;letter-spacing:-.5px">🎯 Aggressive Screener</span>
  {mkt_html}
  <span style="margin-left:auto;color:#787b86;font-size:.78rem">{now.strftime('%d %b %Y  %H:%M IST')}</span>
</div>
<div style="color:#787b86;font-size:.78rem;margin-bottom:12px;">
  NSE + BSE Full Market · All Penny & Mid-Cap · Shoonya Live API · 6-Criteria + Anti-Manipulation
</div>
""", unsafe_allow_html=True)

# Login
api, uname = _login()
if not api:
    st.error(f"Login failed: {uname}"); st.stop()

# Scripmaster
with st.spinner("Loading NSE + BSE scripmaster…"):
    scrip = _load_scripmaster()
if scrip.empty:
    st.error("Could not load scripmaster"); st.stop()

nse_count = int((scrip["Exchange"]=="NSE").sum())
bse_count = int((scrip["Exchange"]=="BSE").sum())
total = len(scrip)

# ═══════════════════════════════════════════════════════════════════════════
# INDEX TICKER TAPE
# ═══════════════════════════════════════════════════════════════════════════
idx_data = []
for name, exch, tok in INDICES:
    q = _q(api, exch, tok)
    if q:
        idx_data.append({"name": name, "ltp": q["ltp"],
                         "pct": round(((q["ltp"]-q["pdcl"])/max(q["pdcl"],.01))*100, 2) if q.get("pdcl") else 0})

if idx_data:
    items = ""
    for d in idx_data:
        cls = "tv-up" if d["pct"] >= 0 else "tv-down"
        sign = "+" if d["pct"] >= 0 else ""
        val = f"{d['ltp']:,.2f}"
        items += f"""
        <div class="tv-tape-item">
          <div class="tv-tape-name">{d['name']}</div>
          <div class="tv-tape-price">{val}</div>
          <div class="tv-tape-chg {cls}">{sign}{d['pct']}%</div>
        </div>"""
    st.markdown(f'<div class="tv-tape">{items}</div>', unsafe_allow_html=True)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════
tab_idx, tab_scan, tab_about = st.tabs(["📊 Index Charts", "🔍 Full Market Scan", "ℹ️ About"])

# ── Tab 1: Index Charts ──────────────────────────────────────────────────
with tab_idx:
    st.markdown("### Market Indices — Live Charts")
    cols = st.columns(2)
    for i, (name, exch, tok) in enumerate(INDICES):
        if name == "INDIA VIX":
            continue  # VIX has no OHLCV
        with cols[i % 2]:
            # header
            q = _q(api, exch, tok)
            if q:
                cls = "tv-up" if q.get("ltp",0) >= q.get("pdcl", q.get("ltp",0)) else "tv-down"
                pct = round(((q["ltp"]-q.get("pdcl",q["ltp"]))/max(q.get("pdcl",q["ltp"]),.01))*100, 2)
                sign = "+" if pct >= 0 else ""
                st.markdown(f"""
<div style="background:#1e222d;border:1px solid #2a2e39;border-radius:8px;padding:10px 16px;margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-weight:700;color:#d1d4dc;font-size:1rem;">{name}</span>
    <span style="font-weight:700;color:#d1d4dc;font-size:1.1rem;">{q['ltp']:,.2f}</span>
    <span class="{cls}" style="font-weight:600;font-size:.85rem;">{sign}{pct}%</span>
    <span style="margin-left:auto;color:#787b86;font-size:.7rem;">O {q.get('open',0):,.2f}  H {q.get('high',0):,.2f}  L {q.get('low',0):,.2f}</span>
  </div>
</div>""", unsafe_allow_html=True)
            fig = _index_chart(api, name, exch, tok)
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=f"idx_{tok}")

# ── Tab 2: Full Market Scan ──────────────────────────────────────────────
with tab_scan:
    # Sidebar
    with st.sidebar:
        st.markdown(f"""
<div style="text-align:center;padding:6px 0;">
  <div style="font-size:.7rem;color:#787b86;">LOGGED IN</div>
  <div style="font-weight:600;color:#d1d4dc;font-size:.9rem;">{uname}</div>
</div>""", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### ⚙️ Scan Settings")
        exch_opt = st.multiselect("Exchanges", ["NSE", "BSE"], default=["NSE", "BSE"])
        price_min = st.slider("Min Price ₹", 1, 100, 10)
        price_max = st.slider("Max Price ₹", 20, 500, 150)
        min_vol   = st.number_input("Min 20d Avg Volume", value=500_000, step=100_000, format="%d")
        min_show  = st.slider("Min criteria for watchlist", 3, 6, 4)
        show_ch   = st.checkbox("Show charts", value=True)

        st.markdown("---")
        st.markdown(f"""
<div style="text-align:center;">
  <div style="display:flex;justify-content:center;gap:20px;">
    <div>
      <div style="font-size:1.5rem;font-weight:700;color:#2962ff;">{nse_count:,}</div>
      <div style="font-size:.68rem;color:#787b86;">NSE</div>
    </div>
    <div>
      <div style="font-size:1.5rem;font-weight:700;color:#ff9800;">{bse_count:,}</div>
      <div style="font-size:.68rem;color:#787b86;">BSE</div>
    </div>
    <div>
      <div style="font-size:1.5rem;font-weight:700;color:#26a69a;">{total:,}</div>
      <div style="font-size:.68rem;color:#787b86;">TOTAL</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("---")
        run = st.button("🚀 SCAN ENTIRE MARKET", type="primary", use_container_width=True)
        st.caption("~4-8 min for full NSE+BSE scan.\nBest during market hours 9:15-15:30 IST.")

    # Criteria info
    with st.expander("📋 Screening Criteria & Risk Rules", expanded=False):
        st.markdown(f"""
| # | Filter | Rule |
|---|--------|------|
| 1 | **Price** | ₹{price_min} – ₹{price_max} |
| 2 | **Liquidity** | 20d avg vol > {min_vol:,} |
| 3 | **Volume Surge** | Today vol > 3× 20d avg |
| 4 | **Momentum** | RSI(14): 60 – 80 |
| 5 | **Price Action** | Within 2% of 52W high OR consolidation breakout |
| 6 | **Circuit** | No circuit hit in last 5 sessions |
| + | **Anti-Manipulation** | No pump, spike+dump, frozen candles, erratic vol |

**Risk**: SL = min(5% hard, 1.5× ATR) floored at support · Target = resistance or +20%
        """)

    st.markdown("---")

    if run:
        # Filter by selected exchanges
        scan_df = scrip[scrip["Exchange"].isin(exch_opt)].reset_index(drop=True)
        scan_total = len(scan_df)

        t0 = time.time()
        prog = st.progress(0); status = st.empty()
        def cb(p, m):
            prog.progress(min(p,1.0))
            status.markdown(f"<div style='color:#787b86;font-size:.82rem;'>{m}</div>", unsafe_allow_html=True)

        cb(0, f"Phase 1: Scanning {scan_total:,} stocks across {', '.join(exch_opt)}…")
        p1 = phase1(api, scan_df, price_min, price_max, cb)
        cb(0, f"Phase 2: Volume pre-filter on {len(p1):,} stocks…")
        p2 = phase2(p1, min_vol)
        cb(1.0, f"Phase 2 done — {len(p2):,} pass volume pre-filter")
        cb(0, f"Phase 3: Deep analysis on {len(p2):,} stocks…")
        p3 = phase3(api, p2, cb)
        elapsed = round(time.time()-t0, 1)
        prog.empty(); status.empty()

        actionable = sorted([r for r in p3 if r["full_pass"]], key=lambda x: x["rr"], reverse=True)
        watchlist  = sorted([r for r in p3 if not r["full_pass"] and r["crit_met"]>=min_show],
                            key=lambda x: x["crit_met"], reverse=True)

        # Summary bar
        st.markdown(f"""
<div style="background:#1e222d;border:1px solid #2a2e39;border-radius:10px;padding:14px 20px;
            display:flex;justify-content:space-between;align-items:center;margin:10px 0;">
  <div style="text-align:center"><div style="font-size:1.4rem;font-weight:700;color:#2962ff">{scan_total:,}</div><div style="font-size:.68rem;color:#787b86">SCANNED</div></div>
  <div style="text-align:center"><div style="font-size:1.4rem;font-weight:700;color:#d1d4dc">{len(p1):,}</div><div style="font-size:.68rem;color:#787b86">PRICE RANGE</div></div>
  <div style="text-align:center"><div style="font-size:1.4rem;font-weight:700;color:#ffb74d">{len(p2):,}</div><div style="font-size:.68rem;color:#787b86">VOL PRE-PASS</div></div>
  <div style="text-align:center"><div style="font-size:1.4rem;font-weight:700;color:#26a69a">{len(actionable)}</div><div style="font-size:.68rem;color:#787b86">ACTIONABLE</div></div>
  <div style="text-align:center"><div style="font-size:1.4rem;font-weight:700;color:#ffb74d">{len(watchlist)}</div><div style="font-size:.68rem;color:#787b86">WATCHLIST</div></div>
  <div style="text-align:center"><div style="font-size:.85rem;color:#787b86">{elapsed}s</div><div style="font-size:.68rem;color:#787b86">TIME</div></div>
</div>""", unsafe_allow_html=True)

        if not actionable and not watchlist:
            st.markdown("""
<div style="background:#1e222d;border:1px solid #ef5350;border-radius:10px;padding:20px;text-align:center;margin:14px 0;">
  <div style="font-size:1.2rem;font-weight:700;color:#ef5350">🚨 HOLD CASH</div>
  <div style="color:#787b86;margin-top:6px;">No stocks pass all 6 criteria. Try during market hours for live volume data.</div>
</div>""", unsafe_allow_html=True)

        if actionable:
            st.markdown(f"""
<div style="margin:16px 0 8px;">
  <span style="font-size:1.1rem;font-weight:700;color:#26a69a">🟢 ACTIONABLE — {len(actionable)} Stock{'s' if len(actionable)>1 else ''}</span>
  <span style="color:#787b86;font-size:.78rem;margin-left:8px;">All 6 criteria · No manipulation · Trade-ready</span>
</div>""", unsafe_allow_html=True)
            tbl = [{
                "Symbol": r["symbol"], "Exch": r["exchange"], "LTP": r["ltp"],
                "Chg%": f"+{r['pct_chg']}%" if r["pct_chg"]>=0 else f"{r['pct_chg']}%",
                "RSI": r["rsi"], "Vol×": r["vol_surge"],
                "SL": r["stop_loss"], "TGT": r["target"], "R:R": r["rr"], "Trend": r["trend"],
            } for r in actionable]
            st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)
            for r in actionable:
                _card(r, show_ch)

        if watchlist:
            st.markdown(f"""
<div style="margin:20px 0 8px;">
  <span style="font-size:1.1rem;font-weight:700;color:#ffb74d">🟡 WATCHLIST — {len(watchlist)} Stock{'s' if len(watchlist)>1 else ''}</span>
  <span style="color:#787b86;font-size:.78rem;margin-left:8px;">{min_show}+ criteria met · Monitor for entry</span>
</div>""", unsafe_allow_html=True)
            wl = [{
                "Symbol": r["symbol"], "Exch": r["exchange"], "LTP": r["ltp"],
                "Chg%": f"+{r['pct_chg']}%" if r["pct_chg"]>=0 else f"{r['pct_chg']}%",
                "RSI": r["rsi"], "Vol×": r["vol_surge"], "Crit": f"{r['crit_met']}/6",
                "SL": r["stop_loss"], "TGT": r["target"], "R:R": r["rr"],
                "Flags": " | ".join(r["m_flags"][:2]) or "Clean",
            } for r in watchlist]
            st.dataframe(pd.DataFrame(wl), use_container_width=True, hide_index=True)
            for r in watchlist:
                _card(r, show_ch)

        with st.expander(f"📋 Full Scan Log — {len(p3)} stocks"):
            log = [{
                "Symbol": r["symbol"], "Exch": r["exchange"], "LTP": r["ltp"],
                "RSI": r["rsi"], "Vol×": r["vol_surge"], "Crit": f"{r['crit_met']}/6",
                "Clean": "✅" if r["is_clean"] else "⚠️",
            } for r in sorted(p3, key=lambda x: x["crit_met"], reverse=True)]
            st.dataframe(pd.DataFrame(log), use_container_width=True, hide_index=True)

    else:
        # Landing
        st.markdown(f"""
<div style="background:#1e222d;border:1px solid #2a2e39;border-radius:12px;padding:28px;text-align:center;margin:16px 0;">
  <div style="display:flex;justify-content:center;gap:36px;margin-bottom:12px;">
    <div>
      <div style="font-size:2.2rem;font-weight:800;color:#2962ff">{nse_count:,}</div>
      <div style="font-size:.8rem;color:#787b86;">NSE Stocks</div>
    </div>
    <div style="font-size:2.2rem;color:#2a2e39;font-weight:300">+</div>
    <div>
      <div style="font-size:2.2rem;font-weight:800;color:#ff9800">{bse_count:,}</div>
      <div style="font-size:.8rem;color:#787b86;">BSE Stocks</div>
    </div>
    <div style="font-size:2.2rem;color:#2a2e39;font-weight:300">=</div>
    <div>
      <div style="font-size:2.2rem;font-weight:800;color:#26a69a">{total:,}</div>
      <div style="font-size:.8rem;color:#787b86;">Total Universe</div>
    </div>
  </div>
  <div style="color:#787b86;font-size:.85rem;margin-top:8px;">
    Click <b style="color:#2962ff">🚀 SCAN ENTIRE MARKET</b> in the sidebar
  </div>
</div>""", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
<div class="tv-card" style="text-align:center;"><div style="font-size:1.4rem">⚡</div>
<div style="font-weight:600;color:#d1d4dc;margin:4px 0">3-Phase Progressive Scan</div>
<div style="color:#787b86;font-size:.78rem">Price → Volume → Deep Analysis<br>12 concurrent threads for speed</div></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown("""
<div class="tv-card" style="text-align:center;"><div style="font-size:1.4rem">🛡️</div>
<div style="font-weight:600;color:#d1d4dc;margin:4px 0">Anti-Manipulation Guard</div>
<div style="color:#787b86;font-size:.78rem">Pump · Spike+Dump · Frozen candles<br>Circuit breaker · Erratic volume</div></div>""", unsafe_allow_html=True)
        with c3:
            st.markdown("""
<div class="tv-card" style="text-align:center;"><div style="font-size:1.4rem">📐</div>
<div style="font-weight:600;color:#d1d4dc;margin:4px 0">ATR Risk Management</div>
<div style="color:#787b86;font-size:.78rem">Smart stop-loss · Support/Resistance<br>R:R ratio · Position sizing ready</div></div>""", unsafe_allow_html=True)

        st.markdown("""
<div style="background:#131722;border:1px solid #2a2e39;border-radius:8px;padding:14px 18px;margin-top:14px;color:#787b86;font-size:.78rem;">
  <b style="color:#ffb74d">Best during market hours (9:15-15:30 IST)</b><br>
  Volume surge is only meaningful with live intraday data. Penny stocks (₹1-20) included with BSE exchange.
</div>""", unsafe_allow_html=True)

# ── Tab 3: About ─────────────────────────────────────────────────────────
with tab_about:
    st.markdown("""
### How It Works

**3-Phase Progressive Scan** ensures speed even with 5,300+ stocks:

1. **Phase 1 — Price Filter** (12 threads)
   - Fetches live quotes for every NSE + BSE equity simultaneously
   - Drops everything outside your price range instantly

2. **Phase 2 — Volume Pre-Filter**
   - Uses today's volume as a quick proxy
   - Eliminates illiquid stocks before expensive OHLCV fetch

3. **Phase 3 — Deep Analysis**
   - Fetches 290-day OHLCV history for survivors
   - Computes RSI, ATR, EMA 20/50, volume averages
   - Checks consolidation breakout, 52W proximity, circuit history
   - Runs anti-manipulation scan (5 checks)
   - Calculates ATR-based stop-loss, support/resistance target, R:R ratio

### Exchanges

| Exchange | Instruments | Types |
|----------|-------------|-------|
| **NSE** | ~3,100 | EQ (main), SM (SME), ST (startup), BE (trade-to-trade) |
| **BSE** | ~2,900 | Groups A, B, M, T, Z — all penny stocks included |

### Indices Tracked

| Index | Description |
|-------|-------------|
| NIFTY 50 | Top 50 large-cap |
| BANK NIFTY | Banking sector |
| FINNIFTY | Financial services |
| MIDCAP NIFTY | Mid-cap select |
| NIFTY NEXT 50 | Next 50 after NIFTY |
| INDIA VIX | Volatility index |
    """)
