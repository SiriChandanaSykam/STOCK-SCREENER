import pandas as pd

master = pd.read_csv("INDIA_STOCKS_MASTER.csv")

# Use lowercase column names that symbol_universe.py expects
screener = pd.DataFrame({
    'symbol': master['Symbol'],      # lowercase
    'company': master['Name'],       # 'company' not 'Name'
    'isin': master['ISIN'],
    'exchange': master.apply(lambda r: 
        'Both' if pd.notna(r.get('Symbol_NSE')) and pd.notna(r.get('Symbol_BSE'))
        else ('NSE' if pd.notna(r.get('Symbol_NSE')) else 'BSE'), axis=1)
})

screener = screener.dropna(subset=['symbol', 'company'])
screener.to_csv("indian_stocks_full.csv", index=False)
print(f"✓ Saved {len(screener)} stocks with columns: {list(screener.columns)}")
