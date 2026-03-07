# historical_data.py — Fetch historical OHLCV seed data at startup

import logging
import pandas as pd
import time
from data_ingestion import api, login
from config import SYMBOLS, EXCHANGE, WEEK52_PERIOD

logger = logging.getLogger(__name__)

# In-memory seed store: {symbol: pd.DataFrame}
seed_data = {}


def fetch_historical(symbol: str, days: int = WEEK52_PERIOD + 10) -> pd.DataFrame:
    """Fetch daily OHLCV from Shoonya for the given symbol."""
    try:
        end_ts = int(time.time())
        start_ts = end_ts - (days * 86400)
        ret = api.get_time_price_series(
            exchange=EXCHANGE,
            token=symbol,
            starttime=start_ts,
            endtime=end_ts,
            interval="1440"  # Daily bars
        )
        if not ret:
            logger.warning(f"No historical data returned for {symbol}")
            return pd.DataFrame()
        df = pd.DataFrame(ret)
        df.rename(columns={
            "time": "date", "into": "open", "inth": "high",
            "intl": "low", "intc": "close", "intv": "volume",
            "v": "volume"
        }, inplace=True, errors="ignore")
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df.dropna(subset=["close"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.info(f"Fetched {len(df)} bars for {symbol}")
        return df
    except Exception as e:
        logger.error(f"Error fetching history for {symbol}: {e}")
        return pd.DataFrame()


def load_all_seed_data():
    """Called once at app startup to load history for all symbols."""
    if not login():
        raise RuntimeError("Cannot load seed data: login failed.")
    for sym in SYMBOLS:
        df = fetch_historical(sym)
        if not df.empty:
            seed_data[sym] = df
        time.sleep(0.3)  # Rate-limit API calls
    logger.info(f"Seed data loaded for {len(seed_data)}/{len(SYMBOLS)} symbols.")
