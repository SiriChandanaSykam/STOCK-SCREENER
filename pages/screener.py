import time
import streamlit as st

from utils.symbol_universe import load_all_symbols
from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.score_engine import score_stock
from utils.charting import create_tv_chart

# Always show a header so the page is never blank
st.title("🔥 Mega Stock Screener")

# Symbol selection
all_symbols, _ = load_all_symbols()
symbols = list(all_symbols.keys())
selected = st.multiselect("Pick stocks", symbols, default=symbols[:15])

# Minimum score filter in sidebar for consistency
min_score = st.sidebar.slider("Minimum Score", min_value=5, max_value=20, value=10)

# Run action
if st.button("Run Screener", type="primary"):
    results = []
    with st.spinner(f"Scanning {len(selected)} stocks..."):
        for sym in selected:
            try:
                df = fetch_stock_data_with_fallback(sym)
            except Exception as e:
                st.error(f"{sym}: fetch failed — {e}")
                time.sleep(0.1)
                continue

            if df is not None and not df.empty:
                try:
                    score, signals = score_stock(df)
                except Exception as e:
                    st.error(f"{sym}: scoring failed — {e}")
                    time.sleep(0.1)
                    continue

                if score >= min_score:
                    results.append({"symbol": sym, "score": score, "signals": signals, "df": df})

            # Gentle throttle to respect provider limits
            time.sleep(0.1)

    if results:
        for res in sorted(results, key=lambda x: x["score"], reverse=True):
            st.subheader(f"{res['symbol']} — Score: {res['score']}")
            if res.get("signals"):
                st.write(", ".join(res["signals"]))
            try:
                st.plotly_chart(create_tv_chart(res["df"], res["symbol"]), use_container_width=True)
            except Exception as e:
                st.error(f"{res['symbol']}: chart failed — {e}")
    else:
        st.info("No stocks matched the screening criteria. Try lowering the minimum score or adding more symbols.")
