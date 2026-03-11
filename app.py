"""
app.py — Live Streamlit dashboard for the NSE Micro-Cap Momentum Screener
         ("Operation Compound").

Run with:
    streamlit run app.py

The dashboard auto-refreshes every REFRESH_INTERVAL_SECONDS seconds and
displays a master summary table of all NSE micro-cap stocks that pass the
6-criteria Shoonya-powered screener.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure the project root is on sys.path so sub-modules resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import SYMBOLS, REFRESH_INTERVAL_SECONDS, NIFTY50_TOKEN
from screener_engine import run_screener
from risk_manager import enrich_results

# Shoonya / data-ingestion imports (optional at import time)
try:
    from data_ingestion import ShoonyaDataIngestor, ws_connected, tick_data
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

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NSE Micro-Cap Screener — Operation Compound",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
if "ingestor" not in st.session_state:
    st.session_state.ingestor = None
if "ws_started" not in st.session_state:
    st.session_state.ws_started = False
if "seed_loaded" not in st.session_state:
    st.session_state.seed_loaded = False


# ---------------------------------------------------------------------------
# Helper: lazy Shoonya bootstrap (runs only once per session)
# ---------------------------------------------------------------------------
@st.cache_resource
def _get_ingestor():
    """
    Login to Shoonya, fetch seed data, and open the WebSocket.
    Returns None if NorenRestApiPy is not installed or login fails.
    """
    if not NOREN_AVAILABLE:
        st.sidebar.warning("NorenRestApiPy not installed — running in demo mode.")
        return None

    try:
        ingestor = ShoonyaDataIngestor()
        if not ingestor.shoonya_login():
            st.sidebar.error("Shoonya login failed — check your .env credentials.")
            return None

        ingestor.resolve_tokens()
        bootstrap_seed_data(api=ingestor)
        ingestor.start_websocket()
        return ingestor
    except Exception as exc:
        st.sidebar.error(f"Ingestor init failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Helper: compute market regime (Nifty 50 vs 20 DMA)
# ---------------------------------------------------------------------------
def _nifty_regime(ingestor) -> str:
    """
    Returns 'BULLISH' if Nifty 50 is above its 20-day MA, else 'BEARISH'.
    Falls back to 'N/A' if data is unavailable.
    """
    if ingestor is None or not HISTORICAL_AVAILABLE:
        return "N/A"

    try:
        # Try to get Nifty seed data by token
        nifty_df = get_seed_df(NIFTY50_TOKEN)
        if nifty_df.empty or len(nifty_df) < 20:
            return "N/A"

        close = nifty_df["close"].astype(float)
        ma20 = close.rolling(20).mean().iloc[-1]
        current = close.iloc[-1]

        return "BULLISH 📈" if current > ma20 else "BEARISH 📉"
    except Exception:
        return "N/A"


# ---------------------------------------------------------------------------
# Helper: colour rows based on criteria_met count
# ---------------------------------------------------------------------------
def _style_row(row):
    """Return a list of CSS background-colour strings for each cell in *row*."""
    if row.get("all_pass") or row.get("criteria_met", 0) == 6:
        colour = "background-color: #1a472a; color: #d4edda;"  # green
    elif row.get("criteria_met", 0) == 5:
        colour = "background-color: #533d00; color: #fff3cd;"  # yellow
    else:
        colour = ""
    return [colour] * len(row)


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------
def main():
    # --- Initialise ingestor once per session ---
    ingestor = _get_ingestor()
    is_connected = ws_connected if NOREN_AVAILABLE else False

    # --- Sidebar -----------------------------------------------------------
    st.sidebar.title("📊 Session Stats")
    st.sidebar.metric("Symbols Scanned", len(SYMBOLS))
    st.sidebar.markdown("---")

    if is_connected:
        st.sidebar.success("🟢 WebSocket Connected")
    else:
        st.sidebar.warning("🔴 WebSocket Disconnected")

    regime = _nifty_regime(ingestor)
    st.sidebar.markdown(f"**Market Regime (Nifty 50):** {regime}")
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Credentials are loaded from `shoonya.env`."
    )

    # --- Header ------------------------------------------------------------
    st.title("📈 NSE Micro-Cap Momentum Screener — Operation Compound")
    st.caption(
        "Powered by Shoonya (Finvasia) API  •  "
        "Filters: price ₹20–₹150, RSI 60–80, above EMA(50), "
        "volume surge 3×, within 2 % of 52-week high"
    )

    # --- Run screener ------------------------------------------------------
    with st.spinner("Running screener…"):
        raw_results = run_screener()

    enriched = enrich_results(raw_results)

    # Separate full-pass (green) from partial-pass (yellow)
    full_pass = [r for r in enriched if r.get("all_pass", False) or r.get("criteria_met", 0) == 6]
    partial_pass = [r for r in enriched if r.get("criteria_met", 0) == 5]

    # Update sidebar metric after screener runs
    st.sidebar.metric("Passing Filter", len(full_pass))

    # --- HOLD CASH banner --------------------------------------------------
    if not full_pass and not partial_pass:
        st.error(
            "🚨 **HOLD CASH** — No stocks currently meet all 6 screening criteria. "
            "Market conditions are unfavourable for new entries.",
            icon="🚨",
        )
    else:
        # --- Master summary table ------------------------------------------
        display_rows = full_pass + partial_pass
        rows_for_table = []
        for r in display_rows:
            rows_for_table.append({
                "Ticker": r.get("symbol", ""),
                "LTP (₹)": r.get("ltp", 0.0),
                "RSI": round(r.get("rsi") or 0, 2),
                "EMA(50)": round(r.get("ema50") or 0, 2),
                "Vol Surge (x)": r.get("volume_surge_multiple", 0.0),
                "Stop-Loss (₹)": r.get("stop_loss", 0.0),
                "Target (₹)": r.get("take_profit", 0.0),
                "R:R": r.get("risk_reward", 0.0),
                "52W High": round(r.get("high52") or 0, 2),
                "% from High": r.get("distance_from_52w_high", 0.0),
                "all_pass": r.get("all_pass", False) or r.get("criteria_met", 0) == 6,
                "criteria_met": r.get("criteria_met", 0),
            })

        table_df = pd.DataFrame(rows_for_table)

        # Apply row-level styling
        styled = (
            table_df.drop(columns=["all_pass", "criteria_met"])
            .style
            .apply(
                lambda row: _style_row(
                    table_df.loc[row.name].to_dict()
                ),
                axis=1,
            )
        )

        st.subheader(f"🏆 {len(full_pass)} stock(s) passing all 6 criteria")
        if partial_pass:
            st.caption(
                f"+ {len(partial_pass)} stock(s) meeting 5/6 criteria "
                "(highlighted in yellow)"
            )

        st.dataframe(styled, use_container_width=True)

    # --- Last updated timestamp --------------------------------------------
    st.markdown("---")
    st.caption(f"Last updated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

    # --- Auto-refresh ------------------------------------------------------
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()


if __name__ == "__main__":
    main()
