"""
config.py — Central configuration for the NSE Micro-Cap Momentum Screener.

All symbol lists and screener parameters live here so that the rest of the
codebase never contains hard-coded magic numbers.
"""

# ---------------------------------------------------------------------------
# NSE micro-cap watchlist
# ---------------------------------------------------------------------------
SYMBOLS = [
    "YESBANK", "SUZLON", "IDEA", "IRFC", "NHPC",
    "RECLTD", "PFC", "RVNL", "IREDA", "SJVN",
    "PNBHOUSING", "BANKINDIA", "UNIONBANK", "CANBK", "IOB",
    "NATIONALUM", "SAIL", "NMDC", "COALINDIA", "GMRINFRA",
]

# Nifty 50 index token used for the market-regime indicator
NIFTY50_TOKEN = "26000"
NIFTY50_EXCHANGE = "NSE"

# ---------------------------------------------------------------------------
# Price filter
# ---------------------------------------------------------------------------
PRICE_MIN = 20          # Minimum price (₹)
PRICE_MAX = 150         # Maximum price (₹)

# ---------------------------------------------------------------------------
# Volume filter
# ---------------------------------------------------------------------------
AVG_VOLUME_MIN = 1_000_000          # 1-month average daily volume threshold
VOLUME_SURGE_MULTIPLIER = 3         # Today's volume must be > N × 20-day avg

# ---------------------------------------------------------------------------
# Momentum / technical filters
# ---------------------------------------------------------------------------
RSI_MIN = 60            # RSI lower bound (exclusive)
RSI_MAX = 80            # RSI upper bound (exclusive)

# ---------------------------------------------------------------------------
# Risk management
# ---------------------------------------------------------------------------
STOP_LOSS_PCT = 0.05    # 5 % below current price
TAKE_PROFIT_PCT = 0.20  # 20 % above current price

# ---------------------------------------------------------------------------
# Indicator periods
# ---------------------------------------------------------------------------
RSI_PERIOD = 14
EMA_PERIOD = 50
EMA200_PERIOD = 200
SMA20_PERIOD = 20
SMA50_PERIOD = 50
VOLUME_AVG_PERIOD = 20
WEEK52_PERIOD = 252     # Trading days in a 52-week window
HIGH10_PERIOD = 10
HIGH5_PERIOD = 5
LOW10_PERIOD = 10
LOW5_PERIOD = 5

RUPEE_TURNOVER_FLOORS = {
    "MACRO_FLOOR": 20_000_000,
    "KINETIC_SQUEEZE": 30_000_000,
    "STEALTH_ACCUMULATION": 15_000_000,
    "BTST": 50_000_000,
    "VCP_SETUP": 10_000_000,
    "VCP_BREAKOUT": 25_000_000,
}

ENGINE_NAMES = [
    "MACRO_FLOOR",
    "KINETIC_SQUEEZE",
    "STEALTH_ACCUMULATION",
    "BTST",
    "VCP_SETUP",
    "VCP_BREAKOUT",
    "ORIGINAL",
]

# ---------------------------------------------------------------------------
# Dashboard refresh
# ---------------------------------------------------------------------------
REFRESH_INTERVAL_SECONDS = 30

# ---------------------------------------------------------------------------
# Shoonya exchange / token metadata
# ---------------------------------------------------------------------------
# Exchange segment for NSE equities used in WebSocket subscriptions
NSE_EXCHANGE = "NSE"
