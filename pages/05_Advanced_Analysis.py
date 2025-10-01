import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Local utils
from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.technicals import calculate_rsi, calculate_macd, calculate_smoothed_ma

# Always render a title so page is never blank
st.title("🚀 Market Predictor Pro")

# Sidebar controls
with st.sidebar:
    st.subheader("🎯 Settings")
    symbol = st.text_input("Stock Symbol", "RELIANCE.NS")
    period = st.selectbox("Data Period", ["3mo", "6mo", "1y", "2y"], index=2)
    show_details = st.checkbox("Show Details", True)

# Tabs
tab1, tab2, tab3 = st.tabs(["🔮 Predictions", "📊 Technical Analysis", "🎲 Monte Carlo"])

def _safe_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute indicators safely and align indices."""
    out = df.copy()
    if out.empty or "Close" not in out.columns:
        return out

    close = out["Close"].astype(float).values

    # RSI
    try:
        out["RSI"] = pd.Series(calculate_rsi(close), index=out.index)
    except Exception as e:
        st.warning(f"RSI calc failed: {e}")

    # MACD
    try:
        macd_line, sig_line = calculate_macd(close)
        out["MACD"] = pd.Series(macd_line, index=out.index)
        out["MACD_Signal"] = pd.Series(sig_line, index=out.index)
    except Exception as e:
        st.warning(f"MACD calc failed: {e}")

    # Smoothed MAs
    try:
        out["SMA_20"] = pd.Series(calculate_smoothed_ma(close, 20), index=out.index)
        out["SMA_50"] = pd.Series(calculate_smoothed_ma(close, 50), index=out.index)
    except Exception as e:
        st.warning(f"SMA calc failed: {e}")

    return out

def _simple_prediction(df: pd.DataFrame):
    """Very simple heuristic: scores based on RSI/MACD/MAs."""
    if df.empty or len(df) < 30:
        return 0.0, 0.0, ["Insufficient data"]

    latest = df.index[-1]
    def g(col, default=0.0):
        try:
            return float(df.at[latest, col]) if col in df.columns and pd.notna(df.at[latest, col]) else default
        except Exception:
            return default

    score = 0.0
    signals = []

    rsi = g("RSI", 50.0)
    if rsi < 30: score += 15; signals.append("RSI Oversold")
    elif rsi > 70: score -= 10; signals.append("RSI Overbought")
    else: score += 5; signals.append("RSI Neutral")

    macd = g("MACD", 0.0)
    macd_sig = g("MACD_Signal", 0.0)
    if macd > macd_sig: score += 15; signals.append("MACD Bullish")
    else: score -= 5; signals.append("MACD Bearish")

    close = g("Close", 0.0)
    sma20 = g("SMA_20", 0.0)
    sma50 = g("SMA_50", 0.0)
    if close and sma20 and sma50:
        if close > sma20 > sma50:
            score += 20; signals.append("Strong Uptrend")
        elif close > sma20:
            score += 10; signals.append("Short-term Bullish")
        else:
            score -= 10; signals.append("Below MAs")

    score = max(0.0, min(100.0, score))
    confidence = score

    returns = df["Close"].pct_change().dropna()
    recent = float(returns.tail(5).mean()) if len(returns) >= 5 else 0.0
    if score > 70: pred = recent * 1.5 + 0.01
    elif score < 30: pred = recent * 0.5 - 0.01
    else: pred = recent
    pred = max(-0.1, min(0.1, pred))
    return pred, confidence, signals

# Tab 1: Predictions
with tab1:
    st.markdown("### 🔮 AI Price Predictions")
    if st.button("🚀 Generate Predictions", type="primary"):
        with st.spinner(f"Fetching {symbol}..."):
            try:
                df = fetch_stock_data_with_fallback(symbol, period=period)
            except Exception as e:
                df = pd.DataFrame()
                st.error(f"Data fetch failed: {e}")

        if df.empty:
            st.error("No data fetched. Check the symbol or period.")
        else:
            st.success(f"Loaded {len(df)} rows")
            df_i = _safe_indicators(df).dropna()

            if df_i.empty or len(df_i) < 30:
                st.warning("Not enough data after indicators; try a longer period.")
            else:
                pred_change, conf, sigs = _simple_prediction(df_i)
                current = float(df_i["Close"].iloc[-1])
                predicted = current * (1.0 + pred_change)

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Current Price", f"{current:,.2f}")
                with c2:
                    st.metric("Predicted Change (≈)", f"{pred_change*100:.2f}%")
                with c3:
                    st.metric("Confidence", f"{conf:.0f}/100")

                if show_details and sigs:
                    st.write("Signals:")
                    for s in sigs:
                        st.write(f"- {s}")

# Tab 2: Technical Analysis (minimal, safe)
with tab2:
    st.markdown("### 📊 Technical Analysis")
    try:
        df_ta = fetch_stock_data_with_fallback(symbol, period=period)
        if not df_ta.empty:
            df_ta = _safe_indicators(df_ta).dropna()
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(
                x=df_ta.index, open=df_ta["Open"], high=df_ta["High"],
                low=df_ta["Low"], close=df_ta["Close"], name="Price"
            ), row=1, col=1)
            if "SMA_20" in df_ta: fig.add_trace(go.Scatter(x=df_ta.index, y=df_ta["SMA_20"], name="SMA 20"), row=1, col=1)
            if "SMA_50" in df_ta: fig.add_trace(go.Scatter(x=df_ta.index, y=df_ta["SMA_50"], name="SMA 50"), row=1, col=1)
            if "RSI" in df_ta: fig.add_trace(go.Scatter(x=df_ta.index, y=df_ta["RSI"], name="RSI"), row=2, col=1)
            fig.update_layout(height=600, margin=dict(l=40, r=20, t=30, b=40))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Fetch some data in Predictions first or change period.")
    except Exception as e:
        st.error(f"TA error: {e}")

# Tab 3: Monte Carlo (placeholder, safe)
with tab3:
    st.markdown("### 🎲 Monte Carlo")
    st.info("Monte Carlo simulation coming next. Use Predictions and Technical Analysis tabs in the meantime.")
