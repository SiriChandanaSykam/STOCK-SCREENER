import yfinance as yf

def fetch_stock_data_with_fallback(symbol, period="6mo"):
    """
    Fetch stock data with automatic NSE/BSE suffix handling
    """
    # Auto-append .NS for NSE if not already present
    if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
        symbol = f"{symbol}.NS"
    
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        
        if df.empty:
            raise ValueError(f"No data for {symbol}")
        
        return df
    
    except Exception as e:
        # Fallback to BSE if NSE fails
        if symbol.endswith('.NS'):
            bse_symbol = symbol.replace('.NS', '.BO')
            try:
                ticker = yf.Ticker(bse_symbol)
                df = ticker.history(period=period)
                if not df.empty:
                    return df
            except:
                pass
        
        raise Exception(f"Failed to fetch data for {symbol}: {e}")
