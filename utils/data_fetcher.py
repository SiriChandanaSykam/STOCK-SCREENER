import yfinance as yf
import pandas as pd

def fetch_stock_data_with_fallback(symbol, period="6mo"):
    for p in [period, "3mo", "1y", "2y"]:
        try:
            df = yf.download(symbol, period=p, progress=False, auto_adjust=True)
            if not df.empty and len(df) >= 20:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [col[0] for col in df.columns]
                return df.dropna()
        except:
            continue
    return pd.DataFrame()
 
