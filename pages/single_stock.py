import streamlit as st

from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.score_engine import score_stock
from utils.charting import create_tv_chart

# Always render a title so the page is never blank
st.title("🔬 Single Stock Analysis")

# Input
sym = st.text_input("Enter Stock Symbol (e.g., RELIANCE.NS)", value="RELIANCE.NS")

if sym:
    # Fetch data with error surface
    try:
        df = fetch_stock_data_with_fallback(sym)
    except Exception as e:
        df = None
        st.error(f"Data fetch failed for {sym}: {e}")

    if df is None or df.empty:
        st.error(f"No data found for {sym}. Please check the symbol and try again.")
    else:
        # Score with guard
        try:
            score, signals = score_stock(df)
        except Exception as e:
            score, signals = None, None
            st.error(f"Scoring failed for {sym}: {e}")

        if score is not None:
            st.subheader(f"{sym} — Score: {score}")
            if signals:
                st.write("Signals:", ", ".join(signals))

        # Chart with guard
        try:
            st.plotly_chart(create_tv_chart(df, sym), use_container_width=True)
        except Exception as e:
            st.error(f"Chart render failed for {sym}: {e}")

        # Show a quick data peek
        with st.expander("Recent data (last 5 rows)", expanded=False):
            st.write(df.tail(5))
else:
    st.info("Enter a stock symbol to begin analysis.")
