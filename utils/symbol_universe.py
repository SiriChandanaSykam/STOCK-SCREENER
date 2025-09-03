import pandas as pd

@st.cache_data(ttl=3600, show_spinner=False)
def load_all_symbols():
    # Load from a comprehensive CSV in assets/data/
    # CSV must include columns: symbol, company, sector, exchange
    
    df = pd.read_csv("assets/data/indian_stocks_full.csv")
    all_symbols = dict(zip(df['symbol'], df['company']))
    sector_map = {}
    for sector in df['sector'].unique():
        sector_map[sector] = dict(df[df['sector'] == sector][['symbol', 'company']].values)
    return all_symbols, sector_map
 
