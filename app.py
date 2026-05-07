"""
app.py - Live Streamlit dashboard for the Shoonya stock screener.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import NIFTY50_TOKEN, REFRESH_INTERVAL_SECONDS, SYMBOLS
from risk_manager import enrich_results
from screener_engine import run_screener

try:
    from data_ingestion import ShoonyaDataIngestor, tick_data, ws_connected
    NOREN_AVAILABLE = True
except (ImportError, Exception):
    NOREN_AVAILABLE = False
    ws_connected = False
    tick_data = {}

try:
    from historical_data import bootstrap_seed_data, get_seed_df
    HISTORICAL_AVAILABLE = True
except (ImportError, Exception):
    HISTORICAL_AVAILABLE = False

    def bootstrap_seed_data(api=None):  # type: ignore[misc]
        pass

    def get_seed_df(symbol):  # type: ignore[misc]
        return pd.DataFrame()

logger = logging.getLogger(__name__)

ENGINE_OPTIONS = [
    "ALL",
    "ORIGINAL",
    "MACRO_FLOOR",
    "KINETIC_SQUEEZE",
    "STEALTH_ACCUMULATION",
    "BTST",
    "VCP_SETUP",
    "VCP_BREAKOUT",
]

st.set_page_config(
    page_title="NSE Micro-Cap Screener - Operation Compound",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "ingestor" not in st.session_state:
    st.session_state.ingestor = None
if "ws_started" not in st.session_state:
    st.session_state.ws_started = False
if "seed_loaded" not in st.session_state:
    st.session_state.seed_loaded = False


@st.cache_resource
def _get_ingestor():
    """
    Login to Shoonya, fetch seed data, and open the WebSocket.
    """
    if not NOREN_AVAILABLE:
        st.sidebar.warning("NorenRestApiPy not installed - running in demo mode.")
        return None

    try:
        ingestor = ShoonyaDataIngestor()
        if not ingestor.shoonya_login():
            st.sidebar.error("Shoonya login failed - check your .env credentials.")
            return None

        ingestor.resolve_tokens()
        bootstrap_seed_data(api=ingestor)
        ingestor.start_websocket()
        return ingestor
    except Exception as exc:
        st.sidebar.error(f"Ingestor init failed: {exc}")
        return None


def _nifty_regime(ingestor) -> str:
    """
    Returns BULLISH if Nifty 50 is above its 20-day MA, else BEARISH.
    """
    if ingestor is None or not HISTORICAL_AVAILABLE:
        return "N/A"

    try:
        nifty_df = get_seed_df(NIFTY50_TOKEN)
        if nifty_df.empty or len(nifty_df) < 20:
            return "N/A"

        close = nifty_df["close"].astype(float)
        ma20 = close.rolling(20).mean().iloc[-1]
        current = close.iloc[-1]
        return "BULLISH 📈" if current > ma20 else "BEARISH 📉"
    except Exception:
        return "N/A"


def _style_row(row):
    """Return CSS style strings for row-level highlighting."""
    engine = str(row.get("Engine") or row.get("engine") or "")
    engine_colours = {
        "MACRO_FLOOR": "background-color: #173b63; color: #dbeafe;",
        "KINETIC_SQUEEZE": "background-color: #14532d; color: #dcfce7;",
        "STEALTH_ACCUMULATION": "background-color: #533d00; color: #fff3cd;",
        "BTST": "background-color: #7c2d12; color: #ffedd5;",
        "VCP_SETUP": "background-color: #3b1a5f; color: #e9d5ff;",
        "VCP_BREAKOUT": "background-color: #6d28d9; color: #f5f3ff;",
    }
    for name, colour in engine_colours.items():
        if name in engine:
            return [colour] * len(row)

    if row.get("all_pass") or row.get("criteria_met", 0) == 6:
        colour = "background-color: #1a472a; color: #d4edda;"
    elif row.get("criteria_met", 0) == 5:
        colour = "background-color: #533d00; color: #fff3cd;"
    else:
        colour = ""
    return [colour] * len(row)


def main():
    ingestor = _get_ingestor()
    is_connected = ws_connected if NOREN_AVAILABLE else False

    st.sidebar.title("📊 Session Stats")
    st.sidebar.metric("Symbols Scanned", len(SYMBOLS))
    selected_engine = st.sidebar.selectbox(
        " Screening Engine",
        options=ENGINE_OPTIONS,
        index=0,
    )
    st.sidebar.markdown("---")

    if is_connected:
        st.sidebar.success("🟢 WebSocket Connected")
    else:
        st.sidebar.warning("🔴 WebSocket Disconnected")

    regime = _nifty_regime(ingestor)
    st.sidebar.markdown(f"**Market Regime (Nifty 50):** {regime}")
    st.sidebar.markdown("---")
    st.sidebar.caption("Credentials are loaded from `shoonya.env`.")

    st.title("📈 NSE Micro-Cap Momentum Screener - Operation Compound")
    st.caption(
        "Powered by Shoonya API. Select ORIGINAL for the legacy six-criteria "
        "filter or choose an institutional engine from the sidebar."
    )

    with st.spinner("Running screener..."):
        raw_results = run_screener(engine=selected_engine)

    enriched = enrich_results(raw_results)
    full_pass = [r for r in enriched if r.get("all_pass", False) or r.get("criteria_met", 0) == 6]
    partial_pass = [r for r in enriched if r.get("criteria_met", 0) == 5]

    st.sidebar.metric("Passing Filter", len(full_pass))

    if not full_pass and not partial_pass:
        st.error(
            "🚨 **HOLD CASH** - No stocks currently meet the selected screening criteria.",
            icon="🚨",
        )
    else:
        display_rows = full_pass + partial_pass
        rows_for_table = []
        for r in display_rows:
            rows_for_table.append({
                "Ticker": r.get("symbol", ""),
                "Engine": r.get("engine", "ORIGINAL"),
                "LTP": r.get("ltp", 0.0),
                "RSI": round(r.get("rsi") or 0, 2),
                "EMA(50)": round(r.get("ema50") or 0, 2),
                "EMA(200)": round(r.get("ema200") or 0, 2),
                "Vol Surge (x)": r.get("volume_surge_multiple", 0.0),
                "Rupee Turnover": round(r.get("rupee_turnover") or 0, 2),
                "Body %": round(r.get("candle_body_pct") or 0, 2),
                "Stop-Loss": r.get("stop_loss", 0.0),
                "Target": r.get("take_profit", 0.0),
                "R:R": r.get("risk_reward", 0.0),
                "52W High": round(r.get("high52") or 0, 2),
                "% from High": r.get("distance_from_52w_high", 0.0),
                "all_pass": r.get("all_pass", False) or r.get("criteria_met", 0) == 6,
                "criteria_met": r.get("criteria_met", 0),
            })

        table_df = pd.DataFrame(rows_for_table)
        styled = (
            table_df.drop(columns=["all_pass", "criteria_met"])
            .style
            .apply(lambda row: _style_row(table_df.loc[row.name].to_dict()), axis=1)
        )

        st.subheader(f"🏆 {len(full_pass)} stock(s) passing {selected_engine}")
        if partial_pass:
            st.caption(f"+ {len(partial_pass)} stock(s) meeting 5/6 ORIGINAL criteria")

        st.dataframe(styled, use_container_width=True)

    st.markdown("---")
    st.caption(f"Last updated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()


if __name__ == "__main__":
    main()
