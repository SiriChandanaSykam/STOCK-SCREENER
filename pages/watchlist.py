import streamlit as st

from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.score_engine import score_stock
from utils.charting import create_tv_chart

# Always render a title so the page is never blank
st.title("⭐ Watchlist")

# Initialize session state
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]

# Add stocks
with st.form("add_form", clear_on_submit=True):
    new_stock = st.text_input("Add stock symbol (e.g., INFY.NS)")
    add = st.form_submit_button("Add to Watchlist")
    if add and new_stock:
        sym = new_stock.upper().strip()
        if sym and sym not in st.session_state["watchlist"]:
            st.session_state["watchlist"].append(sym)

# Remove stocks
if st.session_state["watchlist"]:
    remove = st.multiselect("Remove stocks", st.session_state["watchlist"])
    if st.button("Remove Selected") and remove:
        for stock in remove:
            if stock in st.session_state["watchlist"]:
                st.session_state["watchlist"].remove(stock)

# Show list
st.subheader("Your Watchlist")
if not st.session_state["watchlist"]:
    st.info("Watchlist is empty. Add symbols above to begin.")
else:
    for sym in st.session_state["watchlist"]:
        # Fetch data with guard
        try:
            df = fetch_stock_data_with_fallback(sym)
        except Exception as e:
            st.error(f"{sym}: data fetch failed — {e}")
            continue

        if df is None or df.empty:
            st.warning(f"No data for {sym}")
            continue

        # Score with guard
        try:
            score, signals = score_stock(df)
        except Exception as e:
            st.error(f"{sym}: scoring failed — {e}")
            continue

        st.markdown(f"**{sym} — Score: {score}**")
        if signals:
            st.write(", ".join(signals[:4]))

        # Chart with guard
        try:
            st.plotly_chart(create_tv_chart(df, sym), use_container_width=True)
        except Exception as e:
            st.error(f"{sym}: chart render failed — {e}")
