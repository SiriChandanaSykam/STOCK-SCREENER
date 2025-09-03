import streamlit as st
from utils.symbol_universe import load_all_symbols
from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.technicals import calculate_rsi, calculate_macd
from utils.score_engine import score_stock
from utils.charting import create_tv_chart
import time

def app():
    st.header("🔥 Mega Stock Screener")
    all_symbols, _ = load_all_symbols()
    symbols = list(all_symbols.keys())
    selected = st.multiselect("Pick stocks", symbols, default=symbols[:15])
    
    min_score = st.sidebar.slider("Minimum Score", min_value=5, max_value=20, value=10)

    if st.button("Run Screener"):
        results = []
        with st.spinner(f"Scanning {len(selected)} stocks..."):
            for sym in selected:
                df = fetch_stock_data_with_fallback(sym)
                if not df.empty:
                    score, signals = score_stock(df)
                    if score >= min_score:
                        results.append({'symbol': sym, 'score': score, 'signals': signals, 'df': df})
                time.sleep(0.1)  # To reduce API rate limits
                
        if results:
            for res in sorted(results, key=lambda x: x['score'], reverse=True):
                st.subheader(f"{res['symbol']} - Score: {res['score']}")
                st.write(", ".join(res['signals']))
                st.plotly_chart(create_tv_chart(res['df'], res['symbol']), use_container_width=True)
        else:
            st.info("No stocks matched the screening criteria.")
 
