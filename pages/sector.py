import streamlit as st
from utils.symbol_universe import load_all_symbols
from utils.score_engine import score_stock
from utils.data_fetcher import fetch_stock_data_with_fallback
from utils.charting import create_tv_chart

def app():
    st.header("🏭 Sector Analysis")
    all_symbols, sector_map = load_all_symbols()
    sectors = list(sector_map.keys())
    
    selected_sectors = st.multiselect("Select Sectors to Analyze", sectors, default=sectors[:3])
    min_score = st.slider("Minimum Score Filter", 5, 20, 10)
    
    if st.button("Run Sector Analysis"):
        sector_performance = {}
        for sector in selected_sectors:
            st.subheader(sector)
            stocks = sector_map[sector]
            
            filtered_results = []
            for sym, name in stocks.items():
                df = fetch_stock_data_with_fallback(sym)
                if df.empty:
                    continue
                score, signals = score_stock(df)
                if score >= min_score:
                    filtered_results.append((sym, name, score, signals, df))
            
            if filtered_results:
                filtered_results.sort(key=lambda x: x[2], reverse=True)
                
                for sym, name, score, signals, df in filtered_results[:10]:
                    st.markdown(f"**{sym} - {name}** | Score: {score}")
                    st.write(", ".join(signals[:4]))
                    st.plotly_chart(create_tv_chart(df, sym), use_container_width=True)
            else:
                st.info(f"No stocks passed scoring for sector {sector} with min score {min_score}.")
 
