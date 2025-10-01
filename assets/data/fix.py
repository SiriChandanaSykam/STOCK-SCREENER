import pandas as pd

master = pd.read_csv("INDIA_STOCKS_MASTER.csv")

fixed = pd.DataFrame({
    'symbol': master['Symbol'].astype(str).str.strip(),
    'company': master['Name'].astype(str).str.strip(),
    'isin': master['ISIN'].astype(str).str.strip(),
    'exchange': 'NSE',
    'sector': 'Unknown'  # Add sector column with placeholder
})

fixed = fixed.dropna(subset=['symbol', 'company'])
fixed.to_csv("indian_stocks_full.csv", index=False)
print(f"✓ Created indian_stocks_full.csv with {len(fixed)} rows")
print("Columns:", list(fixed.columns))
