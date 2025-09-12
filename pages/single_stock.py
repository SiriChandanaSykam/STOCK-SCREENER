import streamlit as st
from utils.data_fetcher import fetch_stock_data_with_fallback

from utils.score_engine import score_stock
from utils.charting import create_tv_chart

def app():
    st.header("🔬 Single Stock Analysis")
    sym = st.text_input("Enter Stock Symbol (e.g., RELIANCE.NS)", value="RELIANCE.NS")
    
    if sym:
        df = fetch_stock_data(sym)
        if df.empty:
            st.error(f"No data found for {sym}. Please check symbol and try again.")
            return
        
        score, signals = score_stock(df)
        st.subheader(f"{sym} - Score: {score}")
        st.write("Signals:", ", ".join(signals))
        
        st.plotly_chart(create_tv_chart(df, sym), use_container_width=True)
        
        st.markdown("### Technical Details")
        st.write(df.tail(5))
 
