# historical_data.py — Fetch historical OHLCV seed data at startup

import logging
import time
import pandas as pd

from config import SYMBOLS, EXCHANGE, WEEK52_PERIOD

logger = logging.getLogger(__name__)

# In-memory seed store  {symbol: pd.DataFrame}
seed_data: dict = {}


def fetch_historical(symbol: str, days: int = WEEK52_PERIOD + 10) -> pd.DataFrame:
    """Fetch daily OHLCV from Shoonya for one symbol."""
    try:
        from data_ingestion import api, SHOONYA_AVAILABLE
        if not SHOONYA_AVAILABLE or api is None:
            return pd.DataFrame()

        end_ts = int(time.time())
        start_ts = end_ts - (days * 86_400)

        ret = api.get_time_price_series(
            exchange=EXCHANGE,
            token=symbol,
            starttime=start_ts,
            endtime=end_ts,
            interval="1440"          # Daily bars
        )
        if not ret:
            logger.warning(f"No historical data for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(ret)
        df.rename(columns={
            "time": "date",
            "into": "open",
            "inth": "high",
            "intl": "low",
            "intc": "close",
            "intv": "volume",
            "v":    "volume"
        }, inplace=True, errors="ignore")

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df.dropna(subset=["close"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.info(f"  {symbol}: {len(df)} daily bars loaded.")
        return df

    except Exception as exc:
        logger.error(f"Error fetching history for {symbol}: {exc}")
        return pd.DataFrame()


def load_all_seed_data():
    """Called once at app startup to seed indicators for all symbols."""
    from data_ingestion import login
    if not login():
        logger.warning(
            "Seed data not loaded — credentials missing. "
            "Screener will activate once credentials are supplied."
        )
        return

    logger.info(f"Loading seed data for {len(SYMBOLS)} symbols…")
    for sym in SYMBOLS:
        df = fetch_historical(sym)
        if not df.empty:
            seed_data[sym] = df
        time.sleep(0.3)   # Rate-limit API calls

    logger.info(
        f"✅ Seed data ready: {len(seed_data)}/{len(SYMBOLS)} symbols loaded."
    )
