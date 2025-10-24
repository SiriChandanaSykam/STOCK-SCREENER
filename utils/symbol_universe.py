import pandas as pd
import streamlit as st
from pathlib import Path

@st.cache_data
def load_all_symbols():
    """
    Loads stock symbols from CSV file.
    Adapted to work with the existing Excel/CSV format:
    - Uses 'Symbol' column (capital S)
    - Uses 'Name' column for company names
    - Creates a default 'ETF' sector for all entries since Sector column doesn't exist
    """
    try:
        # Construct path to CSV file
        project_root = Path(__file__).resolve().parent.parent
        csv_path = project_root / "assets" / "data" / "indian_stocks_full.csv"

        if not csv_path.is_file():
            st.error(f"CRITICAL: Symbol file not found at: {csv_path}")
            st.warning("Please ensure 'assets/data/indian_stocks_full.csv' exists.")
            return {}, {}

        # Read the CSV file
        df = pd.read_csv(csv_path)

        # Standardize column names to lowercase for consistent access
        df.columns = [str(col).strip().lower() for col in df.columns]

        # Check if we have the minimum required columns
        if 'symbol' not in df.columns or 'name' not in df.columns:
            st.error(f"CSV file must have 'Symbol' and 'Name' columns. Found: {list(df.columns)}")
            return {}, {}

        # Remove rows where symbol or name is blank
        df = df.dropna(subset=['symbol', 'name'])
        
        # Filter out rows with (blank) in symbol column
        df = df[df['symbol'] != '(blank)']
        df = df[df['symbol'].str.strip() != '']

        # If no 'sector' column exists, create one with default value
        if 'sector' not in df.columns:
            df['sector'] = 'ETF'  # Default sector for all stocks/ETFs
        else:
            # Fill any missing sector values with 'Uncategorized'
            df['sector'] = df['sector'].fillna('Uncategorized')

        # Create the symbols dictionary: symbol -> name
        all_symbols = dict(zip(df['symbol'], df['name']))

        # Create sector mapping: sector -> {symbol: name}
        sector_map = {}
        for sector, group in df.groupby('sector'):
            sector_map[sector] = dict(zip(group['symbol'], group['name']))

        return all_symbols, sector_map

    except Exception as e:
        st.error("Failed to load the stock symbol CSV file.")
        st.error(f"Error details: {e}")
        import traceback
        st.code(traceback.format_exc())
        return {}, {}
