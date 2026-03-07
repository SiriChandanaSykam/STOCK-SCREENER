# app.py — Streamlit live dashboard (auto-refreshes every 30 s)

import os
import time
import logging
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from config import SYMBOLS, REFRESH_INTERVAL_SECONDS
from data_ingestion import websocket_status
from historical_data import seed_data
from screener_engine import run_screener
from risk_manager import apply_risk_management

logging.basicConfig(level=logging.INFO)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ Operation Compound | NSE Screener",
    page_icon="📈",
    layout="wide"
)

# ── One-time session initialisation ─────────────────────────────────────────
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.init_error = None

if not st.session_state.initialized:
    with st.spinner("🔄 Connecting to Shoonya & loading historical data…"):
        try:
            from historical_data import load_all_seed_data
            from data_ingestion import start_streaming
            load_all_seed_data()
            start_streaming()
            st.session_state.initialized = True
        except Exception as exc:
            st.session_state.init_error = str(exc)

# ── Header ───────────────────────────────────────────────────────────────────
st.title("⚡ OPERATION COMPOUND — NSE Micro-Cap Momentum Screener")
st.caption(
    f"Live Dashboard  •  Auto-refreshes every {REFRESH_INTERVAL_SECONDS} s  •  "
    f"Last updated: {datetime.now().strftime('%d %b %Y  %H:%M:%S')}"
)

# ── Credential warning banner ────────────────────────────────────────────────
load_dotenv()

creds_present = all([
    os.getenv("SHOONYA_USER_ID"),
    os.getenv("SHOONYA_PASSWORD"),
    os.getenv("SHOONYA_TOTP_SECRET"),
])
if not creds_present:
    st.warning(
        "⚠️ **Shoonya credentials not found.**  "
        "Copy `.env.example` → `.env` and fill in your API keys, "
        "then restart the app to activate live data."
    )

# ── Init-error guard ─────────────────────────────────────────────────────────
if st.session_state.init_error:
    st.error(f"❌ Initialisation error: {st.session_state.init_error}")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📡 Session Stats")
    ws_label = "🟢 Connected" if websocket_status.get("connected") else "🔴 Disconnected"
    st.metric("WebSocket",       ws_label)
    st.metric("Symbols in List", len(SYMBOLS))
    st.metric("Seed Data Ready", len(seed_data))

    st.divider()
    st.header("⚙️ Active Filters")
    st.markdown("""
    | Filter | Value |
    |---|---|
    | Price | ₹20 – ₹150 |
    | Avg Vol | > 10 Lakh |
    | Vol Surge | > 3× Avg |
    | RSI (14) | 60 – 80 |
    | Price vs EMA | > EMA(50) |
    | 52W Proximity | ≥ 98% of High |
    """)

    st.divider()
    st.header("🛡️ Risk Rules")
    st.markdown("""
    - **Stop-Loss:** 5% below entry
    - **Take-Profit:** 20% above entry
    - **Min R:R:** 3 : 1
    """)
    st.caption("Strategy: Operation Compound")

# ── Run screener ─────────────────────────────────────────────────────────────
with st.spinner("🔍 Scanning…"):
    raw_df = run_screener()
    df = apply_risk_management(raw_df)

# ── KPI row ──────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
all6 = int(df["All 6 Met"].sum()) if not df.empty and "All 6 Met" in df.columns else 0
c1.metric("Symbols Scanned",    len(SYMBOLS))
c2.metric("Setups Found",       len(df))
c3.metric("Perfect (All 6 ✅)", all6)
st.divider()

# ── Main results table ───────────────────────────────────────────────────────
DISPLAY_COLS = [
    "Ticker", "LTP (₹)", "RSI", "EMA(50)", "Vol Surge (x)",
    "Stop-Loss (₹)", "Target (₹)", "R:R", "52W High", "% from High", "All 6 Met"
]

if df.empty:
    st.error("## 🔴 HOLD 100% CASH")
    st.warning(
        "No stocks meet all criteria right now.  "
        "Protect your capital — wait for the next scan."
    )
else:
    st.success(f"### ✅ {len(df)} Setup(s) Identified")

    show_df = df[[c for c in DISPLAY_COLS if c in df.columns]].copy()

    def _colour(row):
        colour = "#1a4a1a" if row.get("All 6 Met") else "#4a4a00"
        return [f"background-color:{colour}; color:white"] * len(row)

    st.dataframe(
        show_df.style.apply(_colour, axis=1),
        use_container_width=True,
        hide_index=True
    )

    # ── Per-stock trade cards ─────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Trade Cards")
    for _, row in df.iterrows():
        with st.expander(
            f"📌 {row['Ticker']}  —  "
            f"₹{row['LTP (₹)']}  |  RSI {row['RSI']}  |  "
            f"Vol Surge {row['Vol Surge (x)']}×"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Entry (LTP)",  f"₹{row['LTP (₹)']}")
            c2.metric("Stop-Loss",    f"₹{row['Stop-Loss (₹)']}", delta="-5%",
                      delta_color="inverse")
            c3.metric("Target",       f"₹{row['Target (₹)']}", delta="+20%")
            c4.metric("R:R Ratio",    f"{row['R:R']} : 1")

# ── Auto-refresh ─────────────────────────────────────────────────────────────
time.sleep(REFRESH_INTERVAL_SECONDS)
st.rerun()
