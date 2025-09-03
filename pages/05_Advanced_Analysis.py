import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.technicals import calculate_rsi, calculate_macd, calculate_smoothed_ma

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Market Predictor Pro", layout="wide")

# CSS Styling
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0c1426 0%, #131722 25%, #1a1e2e 100%);
    color: #d1d4dc;
    font-family: 'Inter', sans-serif;
}
h1 {
    background: linear-gradient(45deg, #2962ff, #00d4aa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    text-align: center;
}
.prediction-card {
    background: linear-gradient(135deg, #1a1e2e 0%, #161b2b 100%);
    border: 2px solid #2962ff;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    margin: 1rem 0;
}
.prediction-card h4 { color: #8b949e; font-size: 0.9rem; margin-bottom: 0.5rem; }
.prediction-card h2 { color: #ffffff; font-size: 2rem; margin: 0; }
.prediction-card p { color: #8b949e; font-size: 0.85rem; margin-top: 0.5rem; }
.bullish { border-color: #00d4aa; }
.bullish h2 { color: #00d4aa; }
.bearish { border-color: #ff4976; }
.bearish h2 { color: #ff4976; }
.neutral { border-color: #ffa726; }
.neutral h2 { color: #ffa726; }
.stButton > button {
    background: linear-gradient(45deg, #2962ff 0%, #00d4aa 100%);
    border: none;
    border-radius: 12px;
    color: #ffffff;
    font-weight: 700;
    text-transform: uppercase;
}
</style>
""", unsafe_allow_html=True)

def simple_prediction_model(df):
    """Prediction model - uses pre-calculated indicators."""
    try:
        if df.empty or len(df) < 30:
            return 0, 0, ["Insufficient data"]
        
        latest_idx = df.index[-1]
        
        def safe_get(column_name, default=0):
            try:
                if column_name in df.columns:
                    value = df.loc[latest_idx, column_name]
                    return float(value) if pd.notna(value) else default
                return default
            except:
                return default
        
        score = 0
        signals = []
        
        # RSI signals
        rsi = safe_get('RSI', 50)
        if rsi < 30:
            score += 15
            signals.append("RSI Oversold - Buy Signal")
        elif rsi > 70:
            score -= 10
            signals.append("RSI Overbought - Caution")
        elif 45 <= rsi <= 55:
            score += 5
            signals.append("RSI Neutral")
        
        # MACD signals
        macd = safe_get('MACD', 0)
        macd_signal = safe_get('MACD_Signal', 0)
        if macd > macd_signal:
            score += 15
            signals.append("MACD Bullish")
        else:
            score -= 5
            signals.append("MACD Bearish")
        
        # Moving average signals
        close = safe_get('Close', 0)
        sma20 = safe_get('SMA_20', 0)
        sma50 = safe_get('SMA_50', 0)
        
        if close > 0 and sma20 > 0 and sma50 > 0:
            if close > sma20 and sma20 > sma50:
                score += 20
                signals.append("Strong Uptrend")
            elif close > sma20:
                score += 10
                signals.append("Short-term Bullish")
            else:
                score -= 10
                signals.append("Below Moving Averages")
        
        # You might need to add Volume_Ratio calculation if you use it here
        
        score = max(0, min(100, score))
        confidence = score
        
        close_series = df['Close']
        returns = close_series.pct_change().dropna()
        recent_changes = float(returns.tail(5).mean()) if len(returns) >= 5 else 0
        
        if score > 70:
            predicted_change = recent_changes * 1.5 + 0.01
        elif score < 30:
            predicted_change = recent_changes * 0.5 - 0.01
        else:
            predicted_change = recent_changes
            
        predicted_change = max(-0.1, min(0.1, predicted_change))
        
        return predicted_change, confidence, signals
        
    except Exception as e:
        st.error(f"Prediction error: {str(e)}")
        return 0, 50, ["Error in analysis"]

def monte_carlo_simple(current_price, volatility, drift, days=30, simulations=1000):
    """Monte Carlo simulation"""
    try:
        if np.isnan(current_price) or np.isnan(volatility) or np.isnan(drift):
            return np.array([current_price] * simulations)
        
        results = []
        dt = 1.0/252.0
        
        for _ in range(simulations):
            price = float(current_price)
            for day in range(days):
                random_shock = np.random.normal(0, 1)
                price_change = price * (drift * dt + volatility * np.sqrt(dt) * random_shock)
                price = max(price + price_change, 0.01)
            results.append(price)
        
        return np.array(results)
        
    except Exception as e:
        st.error(f"Monte Carlo error: {str(e)}")
        return np.array([current_price] * simulations)

# MAIN UI
st.title('🚀 Market Predictor Pro')

with st.sidebar:
    st.markdown("### 🎯 Settings")
    symbol = st.text_input("Stock Symbol:", "RELIANCE.NS")
    period = st.selectbox("Data Period:", ["3mo", "6mo", "1y", "2y"], index=2)
    show_details = st.checkbox("Show Details", True)

tab1, tab2, tab3 = st.tabs(["🔮 Predictions", "📊 Technical Analysis", "🎲 Monte Carlo"])

with tab1:
    st.markdown("### 🔮 **AI Price Predictions**")
    
    if st.button("🚀 **GENERATE PREDICTIONS**", type="primary"):
        with st.spinner(f'🧠 Analyzing {symbol}...'):
            df = fetch_stock_data_with_fallback(symbol, period=period)
            
            if df.empty:
                st.error("❌ Could not fetch data. Please check the symbol.")
            else:
                st.success(f"✅ Loaded {len(df)} days of data")
                
                df_with_indicators = df.copy()
                close_prices = df_with_indicators['Close'].values
                
                df_with_indicators['RSI'] = pd.Series(calculate_rsi(close_prices), index=df_with_indicators.index)
                macd_line, signal_line = calculate_macd(close_prices)
                df_with_indicators['MACD'] = pd.Series(macd_line, index=df_with_indicators.index)
                df_with_indicators['MACD_Signal'] = pd.Series(signal_line, index=df_with_indicators.index)
                df_with_indicators['SMA_20'] = pd.Series(calculate_smoothed_ma(close_prices, 20), index=df_with_indicators.index)
                df_with_indicators['SMA_50'] = pd.Series(calculate_smoothed_ma(close_prices, 50), index=df_with_indicators.index)
                
                df_with_indicators.dropna(inplace=True)
                
                predicted_change, confidence, signals = simple_prediction_model(df_with_indicators)
                
                try:
                    current_price = float(df_with_indicators['Close'].iloc[-1])
                    predicted_price = current_price * (1 + predicted_change)
                    current_rsi = float(df_with_indicators['RSI'].iloc[-1]) if 'RSI' in df_with_indicators.columns else 50
                except IndexError:
                    st.error("Not enough data to make a prediction after calculating indicators.")
                    st.stop()
                except Exception as e:
                    st.error(f"Price calculation error: {str(e)}")
                    st.stop()

                # ... (rest of the UI code for displaying cards, forecasts, etc.) ...

# ... (The code for Tab 2 and Tab 3 would follow a similar refactoring pattern) ...

st.markdown("""
---
<div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #161b2b, #1a1e2e); 
            border-radius: 16px; margin-top: 2rem; border: 1px solid #2962ff;'>
    <h3 style='color: #2962ff; margin-bottom: 1rem;'>🚀 Market Predictor Pro</h3>
    <p style='margin-bottom: 1rem;'><strong>Features:</strong> AI Predictions • Technical Analysis • Monte Carlo Simulation • Risk Assessment</p>
    <p style='font-size: 0.8rem; color: #8b949e;'>
        ⚠️ <strong>Disclaimer:</strong> This tool provides predictions for educational purposes only. Always consult financial advisors before investing.
    </p>
</div>
""", unsafe_allow_html=True)
