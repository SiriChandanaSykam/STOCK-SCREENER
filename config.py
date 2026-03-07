# config.py — All constants, watchlist, and filter parameters

# NSE Micro-Cap Watchlist
SYMBOLS = [
    "YESBANK", "SUZLON", "IDEA", "IRFC", "NHPC",
    "RECLTD", "PFC", "RVNL", "IREDA", "SJVN",
    "PNBHOUSING", "BANKINDIA", "UNIONBANK", "CANBK", "IOB",
    "NATIONALUM", "SAIL", "NMDC", "COALINDIA", "GMRINFRA"
]

EXCHANGE = "NSE"

# Price filter
PRICE_MIN = 20
PRICE_MAX = 150

# Volume filters
AVG_VOLUME_MIN = 1_000_000          # 10 Lakh minimum average daily volume
VOLUME_SURGE_MULTIPLIER = 3         # Today's volume must be > 3x average

# Momentum filters
RSI_MIN = 60
RSI_MAX = 80

# Risk management
STOP_LOSS_PCT = 0.05    # 5% stop-loss
TAKE_PROFIT_PCT = 0.20  # 20% take-profit

# Indicator periods
RSI_PERIOD = 14
EMA_PERIOD = 50
VOLUME_AVG_PERIOD = 20
WEEK52_PERIOD = 252   # Trading days in 1 year
WEEK52_HIGH_THRESHOLD = 0.98  # LTP must be >= 98% of 52-week high
MIN_FILTERS_REQUIRED = 5      # Minimum filters that must pass to show a stock

# App settings
REFRESH_INTERVAL_SECONDS = 30
DEQUE_MAXLEN = 390   # 1 full trading day of 1-min bars
