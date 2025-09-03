import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings

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

def calculate_technical_indicators(df):
    """Calculate technical indicators - SYNTAX ERROR FIXED"""
    if df.empty or len(df) < 20:
        return df
    
    try:
        result_df = df.copy()
        
        # RSI calculation
        close_series = result_df['Close']
        delta = close_series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        
        loss = loss.replace(0, 1e-10)
        rs = gain / loss
        result_df['RSI'] = 100 - (100 / (1 + rs))
        
        # Moving averages
        result_df['SMA_20'] = close_series.rolling(20, min_periods=1).mean()
        result_df['SMA_50'] = close_series.rolling(50, min_periods=1).mean()
        result_df['EMA_20'] = close_series.ewm(span=20, adjust=False).mean()
        
        # MACD
        ema12 = close_series.ewm(span=12, adjust=False).mean()
        ema26 = close_series.ewm(span=26, adjust=False).mean()
        result_df['MACD'] = ema12 - ema26
        result_df['MACD_Signal'] = result_df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Volume indicators
        volume_series = result_df['Volume']
        volume_ma = volume_series.rolling(20, min_periods=1).mean()
        result_df['Volume_MA'] = volume_ma
        volume_ma_safe = volume_ma.replace(0, 1e-10)
        result_df['Volume_Ratio'] = volume_series / volume_ma_safe
        
        # Volatility
        result_df['Volatility'] = close_series.rolling(20, min_periods=1).std()
        
        # Fill NaN values
        numeric_columns = ['RSI', 'SMA_20', 'SMA_50', 'EMA_20', 'MACD', 'MACD_Signal', 'Volume_MA', 'Volume_Ratio', 'Volatility']
        for col in numeric_columns:
            if col in result_df.columns:
                result_df[col] = result_df[col].fillna(method='forward').fillna(method='backward').fillna(0)
        
        return result_df
        
    except Exception as e:
        st.error(f"Technical indicator error: {str(e)}")
        return df

def simple_prediction_model(df):
    """Prediction model - SYNTAX ERROR FIXED"""
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
        
        # Volume signals
        volume_ratio = safe_get('Volume_Ratio', 1)
        if volume_ratio > 2.0:
            score += 15
            signals.append("Volume Explosion")
        elif volume_ratio > 1.5:
            score += 10
            signals.append("High Volume")
        
        # Price momentum
        if len(df) >= 5:
            current_price = close
            try:
                prev_price_idx = df.index[-5]
                prev_price = float(df.loc[prev_price_idx, 'Close'])
                if prev_price > 0:
                    price_change_5d = (current_price - prev_price) / prev_price
                    if price_change_5d > 0.05:
                        score += 15
                        signals.append("Strong Momentum")
                    elif price_change_5d > 0.02:
                        score += 10
                        signals.append("Positive Momentum")
                    elif price_change_5d < -0.05:
                        score -= 15
                        signals.append("Negative Momentum")
            except:
                pass  # ← FIXED: Replaced 'continue' with 'pass'
        
        score = max(0, min(100, score))
        confidence = score
        
        try:
            close_series = df['Close']
            returns = close_series.pct_change().dropna()
            if len(returns) >= 5:
                recent_changes = float(returns.tail(5).mean())
            else:
                recent_changes = 0
        except:
            recent_changes = 0
        
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
        try:
            with st.spinner(f'🧠 Analyzing {symbol}...'):
                try:
                    df = yf.download(symbol, period=period, progress=False, auto_adjust=True)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [col[0] for col in df.columns.values]
                except Exception as e:
                    st.error(f"Data fetch error: {str(e)}")
                    df = pd.DataFrame()
                
                if df.empty:
                    st.error("❌ Could not fetch data. Please check the symbol.")
                else:
                    st.success(f"✅ Loaded {len(df)} days of data")
                    
                    df_with_indicators = calculate_technical_indicators(df)
                    predicted_change, confidence, signals = simple_prediction_model(df_with_indicators)
                    
                    try:
                        current_price = float(df_with_indicators['Close'].iloc[-1])
                        predicted_price = current_price * (1 + predicted_change)
                        current_rsi = float(df_with_indicators['RSI'].iloc[-1]) if 'RSI' in df_with_indicators.columns else 50
                    except Exception as e:
                        st.error(f"Price calculation error: {str(e)}")
                        st.stop()  # ← FIXED: Using st.stop() instead of continue
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        pred_class = "bullish" if predicted_change > 0.02 else "bearish" if predicted_change < -0.02 else "neutral"
                        st.markdown(f'''
                        <div class="prediction-card {pred_class}">
                            <h4>Next Day Prediction</h4>
                            <h2>₹{predicted_price:.2f}</h2>
                            <p>{predicted_change*100:+.2f}%</p>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    with col2:
                        conf_class = "bullish" if confidence >= 70 else "neutral" if confidence >= 50 else "bearish"
                        st.markdown(f'''
                        <div class="prediction-card {conf_class}">
                            <h4>Confidence Level</h4>
                            <h2>{confidence:.0f}%</h2>
                            <p>Prediction Strength</p>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    with col3:
                        rsi_class = "bearish" if current_rsi > 70 else "bullish" if current_rsi < 30 else "neutral"
                        rsi_status = "Overbought" if current_rsi > 70 else "Oversold" if current_rsi < 30 else "Neutral"
                        st.markdown(f'''
                        <div class="prediction-card {rsi_class}">
                            <h4>Current RSI</h4>
                            <h2>{current_rsi:.0f}</h2>
                            <p>{rsi_status}</p>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    if signals and show_details:
                        st.markdown("### 📊 **Key Signals**")
                        for signal in signals:
                            if any(word in signal for word in ["Buy", "Bullish", "Strong", "Momentum"]):
                                st.success(f"🟢 {signal}")
                            elif any(word in signal for word in ["Sell", "Bearish", "Caution", "Negative"]):
                                st.error(f"🔴 {signal}")
                            else:
                                st.info(f"⚪ {signal}")
                    
                    if show_details:
                        st.markdown("### 📈 **Extended Forecast**")
                        
                        forecast_data = []
                        for days in [1, 3, 5, 7]:
                            decay_factor = 0.8 ** (days - 1)
                            extended_change = predicted_change * decay_factor
                            extended_price = current_price * (1 + extended_change)
                            forecast_data.append({
                                'Period': f"{days} Day{'s' if days > 1 else ''}",
                                'Target Price': f"₹{extended_price:.2f}",
                                'Expected Return': f"{extended_change*100:+.2f}%",
                                'Confidence': f"{confidence * decay_factor:.0f}%"
                            })
                        
                        forecast_df = pd.DataFrame(forecast_data)
                        st.dataframe(forecast_df, use_container_width=True, hide_index=True)
        
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")

with tab2:
    st.markdown("### 📊 **Technical Analysis**")
    
    if st.button("📈 **ANALYZE TECHNICALS**"):
        try:
            df = yf.download(symbol, period=period, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns.values]
            
            if not df.empty:
                df_with_indicators = calculate_technical_indicators(df)
                
                fig = make_subplots(
                    rows=3, cols=1, 
                    shared_xaxes=True,
                    row_heights=[0.6, 0.2, 0.2],
                    subplot_titles=(f'{symbol} - Price Action', 'RSI (14)', 'MACD (12,26,9)'),
                    vertical_spacing=0.03
                )
                
                fig.add_trace(go.Candlestick(
                    x=df_with_indicators.index,
                    open=df_with_indicators['Open'],
                    high=df_with_indicators['High'],
                    low=df_with_indicators['Low'],
                    close=df_with_indicators['Close'],
                    name='Price',
                    increasing_line_color='#00d4aa',
                    decreasing_line_color='#ff4976'
                ), row=1, col=1)
                
                if 'SMA_20' in df_with_indicators.columns:
                    fig.add_trace(go.Scatter(
                        x=df_with_indicators.index, 
                        y=df_with_indicators['SMA_20'],
                        name='SMA 20',
                        line=dict(color='orange', width=2)
                    ), row=1, col=1)
                
                if 'SMA_50' in df_with_indicators.columns:
                    fig.add_trace(go.Scatter(
                        x=df_with_indicators.index, 
                        y=df_with_indicators['SMA_50'],
                        name='SMA 50',
                        line=dict(color='blue', width=2)
                    ), row=1, col=1)
                
                if 'RSI' in df_with_indicators.columns:
                    fig.add_trace(go.Scatter(
                        x=df_with_indicators.index, 
                        y=df_with_indicators['RSI'],
                        name='RSI',
                        line=dict(color='purple', width=2)
                    ), row=2, col=1)
                    fig.add_hline(y=70, line=dict(color='red', dash='dash'), row=2, col=1)
                    fig.add_hline(y=30, line=dict(color='green', dash='dash'), row=2, col=1)
                
                if all(col in df_with_indicators.columns for col in ['MACD', 'MACD_Signal']):
                    fig.add_trace(go.Scatter(
                        x=df_with_indicators.index, 
                        y=df_with_indicators['MACD'],
                        name='MACD',
                        line=dict(color='cyan', width=2)
                    ), row=3, col=1)
                    fig.add_trace(go.Scatter(
                        x=df_with_indicators.index, 
                        y=df_with_indicators['MACD_Signal'],
                        name='Signal',
                        line=dict(color='red', width=2)
                    ), row=3, col=1)
                
                fig.update_layout(
                    height=800,
                    template='plotly_dark',
                    showlegend=True,
                    title=f"{symbol} - Professional Technical Analysis"
                )
                
                fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
                fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
                fig.update_yaxes(title_text="MACD", row=3, col=1)
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Could not fetch data for technical analysis")
        
        except Exception as e:
            st.error(f"Technical analysis error: {str(e)}")

with tab3:
    st.markdown("### 🎲 **Monte Carlo Simulation**")
    
    if st.button("🎯 **RUN SIMULATION**"):
        try:
            df = yf.download(symbol, period=period, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns.values]
            
            if not df.empty:
                current_price = float(df['Close'].iloc[-1])
                returns = df['Close'].pct_change().dropna()
                
                if len(returns) > 10:
                    volatility = float(returns.std() * np.sqrt(252))
                    drift = float(returns.mean() * 252)
                    
                    results = monte_carlo_simple(current_price, volatility, drift, 30, 1000)
                    percentiles = np.percentile(results, [5, 25, 50, 75, 95])
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    cards = [
                        ("5th Percentile", percentiles[0], "bearish"),
                        ("25th Percentile", percentiles[1], "neutral"),
                        ("Median", percentiles[2], "neutral"),
                        ("75th Percentile", percentiles[3], "neutral"),
                        ("95th Percentile", percentiles[4], "bullish")
                    ]
                    
                    for i, (label, value, card_class) in enumerate(cards):
                        change_pct = (value - current_price) / current_price * 100
                        with [col1, col2, col3, col4, col5][i]:
                            st.markdown(f'''
                            <div class="prediction-card {card_class}">
                                <h4>{label}</h4>
                                <h2>₹{value:.2f}</h2>
                                <p>{change_pct:+.1f}%</p>
                            </div>
                            ''', unsafe_allow_html=True)
                    
                    st.markdown("### 📊 **Risk Metrics**")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        prob_loss = float((results < current_price).mean() * 100)
                        st.metric("Probability of Loss", f"{prob_loss:.1f}%")
                    
                    with col2:
                        var_5 = float((current_price - percentiles[0]) / current_price * 100)
                        st.metric("Value at Risk (5%)", f"{var_5:.1f}%")
                    
                    with col3:
                        max_gain = float(((results.max() - current_price) / current_price) * 100)
                        st.metric("Maximum Potential Gain", f"{max_gain:.1f}%")
                else:
                    st.error("Insufficient return data for simulation")
            else:
                st.error("Could not fetch data for Monte Carlo")
        
        except Exception as e:
            st.error(f"Monte Carlo error: {str(e)}")

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
