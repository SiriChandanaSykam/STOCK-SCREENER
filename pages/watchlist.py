import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

import streamlit as st
from utils.data_fetcher import fetch_stock_data
from utils.score_engine import score_stock
from utils.charting import create_tv_chart

def app():
    st.header("⭐ Watchlist")
    
    if 'watchlist' not in st.session_state:
        st.session_state['watchlist'] = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
    
    new_stock = st.text_input("Add Stock Symbol (e.g., INFY.NS)")
    if st.button("Add to Watchlist") and new_stock:
        if new_stock.upper() not in st.session_state['watchlist']:
            st.session_state['watchlist'].append(new_stock.upper())
    
    remove = st.multiselect("Remove Stocks", st.session_state['watchlist'])
    if st.button("Remove Selected"):
        for stock in remove:
            if stock in st.session_state['watchlist']:
                st.session_state['watchlist'].remove(stock)
    
    st.write("## Your Watchlist")
    for sym in st.session_state['watchlist']:
        df = fetch_stock_data(sym)
        if df.empty:
            st.warning(f"No data for {sym}")
            continue
        
        score, signals = score_stock(df)
        st.markdown(f"**{sym} - Score: {score}**")
        st.write(", ".join(signals[:4]))
        st.plotly_chart(create_tv_chart(df, sym), use_container_width=True)
