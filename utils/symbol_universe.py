# utils/symbol_universe.py

# Lint-safe import and cache decorator:
# - If Streamlit is available (normal app run), use st.cache_data.
# - If not (e.g., CI linting), provide a no-op decorator so flake8
#   does not complain and the module imports cleanly.

try:
    import streamlit as st
    cache_data = st.cache_data
except Exception:
    # Fallback no-op decorator for lint/test environments without Streamlit.
    def cache_data(*dargs, **dkwargs):
        def _wrap(func):
            return func
        return _wrap

import pandas as pd


@cache_data(ttl=3600, show_spinner=False)
def load_all_symbols():
    """
    Load symbol universe from assets/data/indian_stocks_full.csv.

    CSV must include columns:
      - symbol
      - company
      - sector
      - exchange

    Returns:
        all_symbols (dict): {symbol: company}
        sector_map (dict): {sector: {symbol: company}}
    """
    # Read the full Indian stocks CSV
    df = pd.read_csv("assets/data/indian_stocks_full.csv")

    # Map of all symbols to their company names
    all_symbols = dict(zip(df["symbol"], df["company"]))

    # Build sector-wise map of symbols to companies
    sector_map = {}
    for sector in df["sector"].unique():
        sector_df = df[df["sector"] == sector][["symbol", "company"]]
        sector_map[sector] = dict(sector_df.values)

    return all_symbols, sector_map
