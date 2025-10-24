"""
Multi-Strategy Trading Screener
Real-time signal generation across multiple stocks
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import sys
sys.path.append('..')

from utils.signal_generator import MultiStrategySignalGenerator

st.set_page_config(page_title="Strategy Screener", layout="wide")

# Title
st.title("🎯 Multi-Strategy Trading Screener")
st.markdown("**Real-time signals from 12 proven trading strategies**")

# Initialize signal generator
@st.cache_resource
def get_signal_generator():
    return MultiStrategySignalGenerator()

signal_gen = get_signal_generator()

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

# Stock selection
stock_input = st.sidebar.text_input(
    "Enter Stock Symbols (comma-separated)", 
    value="RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, TATAMOTORS.NS"
)
stock_list = [s.strip() for s in stock_input.split(',')]

# Timeframe selection
timeframe = st.sidebar.selectbox(
    "Select Timeframe",
    options=['1d', '5d', '1mo', '3mo'],
    index=2,
    help="Data period for analysis"
)

interval = st.sidebar.selectbox(
    "Select Interval",
    options=['1m', '5m', '15m', '1h', '1d'],
    index=4,
    help="Bar interval (1m/5m only available for 1-7 days)"
)

# Strategy selection
st.sidebar.subheader("📊 Select Strategies")

strategy_categories = {
    "Momentum": ['Momentum Breakout', 'Opening Range Breakout', 'VWAP-EMA Trend', 'Pullback Buy'],
    "Reversal": ['RSI Reversal', 'Capitulation Reversal', 'Bollinger Squeeze', 'Supertrend Reversal'],
    "Volume": ['Volume Spike', 'F&O Buildup', 'Micro Breakout', 'Price-Volume Divergence']
}

selected_strategies = []
for category, strategies in strategy_categories.items():
    with st.sidebar.expander(f"{category} Strategies"):
        for strategy in strategies:
            if st.checkbox(strategy, value=True, key=strategy):
                selected_strategies.append(strategy)

# Minimum confidence filter
min_confidence = st.sidebar.slider(
    "Minimum Confidence Score",
    min_value=1,
    max_value=5,
    value=3,
    help="Filter signals by confidence (1=Low, 5=High)"
)

# Run button
run_scan = st.sidebar.button("🚀 Run Strategy Scan", type="primary")

# Main content
if run_scan:
    if not selected_strategies:
        st.error("❌ Please select at least one strategy!")
    else:
        st.info(f"🔍 Scanning {len(stock_list)} stocks with {len(selected_strategies)} strategies...")
        
        results_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, symbol in enumerate(stock_list):
            status_text.text(f"Analyzing {symbol}...")
            progress_bar.progress((idx + 1) / len(stock_list))
            
            try:
                # Download data
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=timeframe, interval=interval)
                
                if df.empty or len(df) < 20:
                    st.warning(f"⚠️ Insufficient data for {symbol}")
                    continue
                
                # Generate consensus signals
                consensus_df = signal_gen.create_consensus_signal(df, selected_strategies)
                
                # Get latest signal
                latest = consensus_df.iloc[-1]
                
                if (latest['Consensus_Signal'] in ['BUY', 'SELL'] and 
                    latest['Consensus_Confidence'] >= min_confidence):
                    
                    results_data.append({
                        'Symbol': symbol,
                        'Signal': latest['Consensus_Signal'],
                        'Confidence': f"{latest['Consensus_Confidence']:.1f}/5.0",
                        'Strength': f"{latest['Signal_Strength']:.0f}%",
                        'Buy_Votes': int(latest['Buy_Votes']),
                        'Sell_Votes': int(latest['Sell_Votes']),
                        'Close': f"₹{latest['Close']:.2f}",
                        'Volume': f"{latest['Volume']:,.0f}",
                        'Time': latest.name.strftime('%Y-%m-%d %H:%M') if hasattr(latest.name, 'strftime') else str(latest.name)
                    })
                
            except Exception as e:
                st.warning(f"⚠️ Error analyzing {symbol}: {str(e)}")
                continue
        
        progress_bar.empty()
        status_text.empty()
        
        # Display results
        if results_data:
            results_df = pd.DataFrame(results_data)
            
            st.success(f"✅ Found {len(results_df)} actionable signals!")
            
            # Separate BUY and SELL signals
            buy_signals = results_df[results_df['Signal'] == 'BUY']
            sell_signals = results_df[results_df['Signal'] == 'SELL']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"🟢 BUY Signals ({len(buy_signals)})")
                if not buy_signals.empty:
                    st.dataframe(
                        buy_signals.style.background_gradient(subset=['Strength'], cmap='Greens'),
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No BUY signals found")
            
            with col2:
                st.subheader(f"🔴 SELL Signals ({len(sell_signals)})")
                if not sell_signals.empty:
                    st.dataframe(
                        sell_signals.style.background_gradient(subset=['Strength'], cmap='Reds'),
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No SELL signals found")
            
            # Detailed view
            st.markdown("---")
            st.subheader("📈 Detailed Signal Analysis")
            
            selected_symbol = st.selectbox("Select stock for detailed view:", results_df['Symbol'].unique())
            
            if selected_symbol:
                try:
                    ticker = yf.Ticker(selected_symbol)
                    df = ticker.history(period=timeframe, interval=interval)
                    consensus_df = signal_gen.create_consensus_signal(df, selected_strategies)
                    
                    # Display latest signal details
                    latest = consensus_df.iloc[-1]
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Signal", latest['Consensus_Signal'])
                    col2.metric("Confidence", f"{latest['Consensus_Confidence']:.1f}/5.0")
                    col3.metric("Signal Strength", f"{latest['Signal_Strength']:.0f}%")
                    col4.metric("Close Price", f"₹{latest['Close']:.2f}")
                    
                    # Individual strategy signals
                    st.markdown("#### Individual Strategy Signals")
                    
                    strategy_signals = []
                    for strategy in selected_strategies:
                        safe_name = strategy.replace(' ', '_').replace('-', '_')
                        signal_col = f'{safe_name}_Signal'
                        conf_col = f'{safe_name}_Confidence'
                        
                        if signal_col in consensus_df.columns:
                            signal = latest[signal_col]
                            confidence = latest[conf_col]
                            
                            if signal in ['BUY', 'SELL']:
                                strategy_signals.append({
                                    'Strategy': strategy,
                                    'Signal': signal,
                                    'Confidence': f"{confidence:.0f}/5"
                                })
                    
                    if strategy_signals:
                        strategy_df = pd.DataFrame(strategy_signals)
                        st.dataframe(strategy_df, use_container_width=True)
                    
                    # Chart
                    st.markdown("#### Price Chart with Signals")
                    
                    chart_data = consensus_df[['Close']].copy()
                    chart_data.columns = ['Price']
                    
                    # Mark BUY and SELL signals
                    buy_points = consensus_df[consensus_df['Consensus_Signal'] == 'BUY']['Close']
                    sell_points = consensus_df[consensus_df['Consensus_Signal'] == 'SELL']['Close']
                    
                    st.line_chart(chart_data, use_container_width=True, height=400)
                    
                    if not buy_points.empty:
                        st.success(f"🟢 {len(buy_points)} BUY signals detected in the period")
                    if not sell_points.empty:
                        st.error(f"🔴 {len(sell_points)} SELL signals detected in the period")
                    
                except Exception as e:
                    st.error(f"Error loading detailed view: {str(e)}")
        
        else:
            st.warning("⚠️ No actionable signals found with current filters. Try:")
            st.markdown("- Lowering minimum confidence threshold")
            st.markdown("- Selecting more strategies")
            st.markdown("- Changing timeframe/interval")
            st.markdown("- Adding more stocks to scan")

else:
    # Initial instructions
    st.markdown("""
    ### 🚀 How to Use This Screener
    
    1. **Select Stocks**: Enter stock symbols in the sidebar (e.g., RELIANCE.NS, TCS.NS)
    2. **Choose Timeframe**: Select data period and bar interval
    3. **Pick Strategies**: Enable the strategies you want to use
    4. **Set Confidence**: Filter signals by minimum confidence score
    5. **Run Scan**: Click the button to analyze stocks
    
    ### 📊 Strategy Categories
    
    #### Momentum Strategies
    - **Momentum Breakout**: Catches price breaking recent highs with volume
    - **Opening Range Breakout**: Professional gap-and-go setup
    - **VWAP-EMA Trend**: Institutional trend following system
    - **Pullback Buy**: Buy dips in strong uptrends
    
    #### Reversal Strategies
    - **RSI Reversal**: Oversold/overbought reversals
    - **Capitulation Reversal**: Panic selling bottoms
    - **Bollinger Squeeze**: Breakouts from low volatility
    - **Supertrend Reversal**: Trend change detection
    
    #### Volume Strategies
    - **Volume Spike**: Unusual activity detection
    - **F&O Buildup**: Long/short buildup analysis
    - **Micro Breakout**: Quick scalping setups
    - **Price-Volume Divergence**: Warning signals
    
    ### 🎯 Confidence Scores
    
    - **5/5**: Extremely high probability setup
    - **4/5**: Strong signal with good confirmation
    - **3/5**: Decent setup, standard filters
    - **2/5**: Weak setup, needs caution
    - **1/5**: Very weak, avoid
    
    ### ⚠️ Important Notes
    
    - This is for educational purposes only
    - Always do your own research
    - Use proper risk management
    - Consider transaction costs
    - Test strategies before live trading
    """)

# Footer
st.markdown("---")
st.caption("💡 Tip: Start with high confidence signals (4-5) and gradually experiment with different strategy combinations")
