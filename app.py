# app.py — Streamlit live dashboard with auto-refresh every 30 seconds

import streamlit as st
import time
import logging
from datetime import datetime

from config import SYMBOLS, REFRESH_INTERVAL_SECONDS
from data_ingestion import start_streaming, websocket_status
from historical_data import load_all_seed_data, seed_data
from screener_engine import run_screener
from risk_manager import apply_risk_management

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="⚡ Operation Compound | NSE Screener",
    page_icon="📈",
    layout="wide"
)

# ── Session-state bootstrap (runs once per session) ─────────────────────────
if "initialized" not in st.session_state:
    st.session_state.initialized = False

if not st.session_state.initialized:
    with st.spinner("🔄 Logging into Shoonya & loading historical seed data..."):
        try:
            load_all_seed_data()
            start_streaming()
            st.session_state.initialized = True
            st.session_state.init_error = None
        except Exception as e:
            st.session_state.init_error = str(e)
            st.session_state.initialized = False

# ── Header ───────────────────────────────────────────────────────────────────
st.title("⚡ OPERATION COMPOUND — NSE Micro-Cap Momentum Screener")
st.caption(
    f"Live Dashboard | Auto-refreshes every {REFRESH_INTERVAL_SECONDS}s | "
    f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
)

# ── Init error guard ─────────────────────────────────────────────────────────
if st.session_state.get("init_error"):
    st.error(f"❌ Initialization failed: {st.session_state.init_error}")
    st.info("Check your .env credentials and Shoonya API access.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📡 Session Stats")
    ws_status = "🟢 Connected" if websocket_status.get("connected") else "🔴 Disconnected"
    st.metric("WebSocket", ws_status)
    st.metric("Total Symbols", len(SYMBOLS))
    st.metric("Seed Data Loaded", len(seed_data))
    st.divider()
    st.header("⚙️ Active Filters")
    st.markdown("""
    - Price: ₹20 – ₹150
    - Avg Volume > 10 Lakh
    - Live Vol > 3× Avg Vol
    - RSI(14): 60 – 80
    - Price > EMA(50)
    - Price ≥ 98% of 52W High
    """)
    st.divider()
    st.caption("Strategy: Operation Compound | SL: 5% | TP: 20% | R:R > 3:1")

# ── Run screener ─────────────────────────────────────────────────────────────
with st.spinner("🔍 Scanning market..."):
    raw_df = run_screener()
    df = apply_risk_management(raw_df)

# ── Metrics row ──────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
passing_all6 = int(df["All 6 Met"].sum()) if not df.empty and "All 6 Met" in df.columns else 0
col1.metric("Symbols Scanned", len(SYMBOLS))
col2.metric("Setups Found", len(df))
col3.metric("Perfect (All 6 ✅)", passing_all6)

st.divider()

# ── Main table or HOLD CASH ──────────────────────────────────────────────────
if df.empty:
    st.error("## 🔴 HOLD 100% CASH — No stocks meet the criteria right now.")
    st.warning("Market regime may be unfavourable. Protect your capital. Wait for next scan.")
else:
    st.success(f"### ✅ {len(df)} Setup(s) Identified")

    display_cols = [
        "Ticker", "LTP (₹)", "RSI", "EMA(50)", "Vol Surge (x)",
        "Stop-Loss (₹)", "Target (₹)", "R:R", "52W High", "% from High", "All 6 Met"
    ]
    display_df = df[[c for c in display_cols if c in df.columns]].copy()

    def _style_row(row):
        if row.get("All 6 Met") is True:
            return ["background-color: #1a4a1a; color: white"] * len(row)
        else:
            return ["background-color: #4a4a00; color: white"] * len(row)

    styled = display_df.style.apply(_style_row, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📋 Trade Cards")
    for _, row in df.iterrows():
        with st.expander(
            f"📌 {row['Ticker']} — ₹{row['LTP (₹)']} | "
            f"RSI: {row['RSI']} | Vol Surge: {row['Vol Surge (x)']}x"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Entry (LTP)", f"₹{row['LTP (₹)']}")
            c2.metric("Stop-Loss", f"₹{row['Stop-Loss (₹)']}", delta="-5%", delta_color="inverse")
            c3.metric("Target", f"₹{row['Target (₹)']}", delta="+20%")
            c4.metric("R:R Ratio", f"{row['R:R']} : 1")

# ── Auto-refresh ─────────────────────────────────────────────────────────────
time.sleep(REFRESH_INTERVAL_SECONDS)
st.rerun()
