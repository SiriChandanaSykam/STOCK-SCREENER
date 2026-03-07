# risk_manager.py — Automatic SL / TP / R:R calculator

import pandas as pd

from config import STOP_LOSS_PCT, TAKE_PROFIT_PCT


def apply_risk_management(df: pd.DataFrame) -> pd.DataFrame:
    """Append Stop-Loss, Take-Profit and Risk:Reward columns."""
    if df.empty:
        return df

    df = df.copy()
    df["Stop-Loss (₹)"] = (df["LTP (₹)"] * (1 - STOP_LOSS_PCT)).round(2)
    df["Target (₹)"] = (df["LTP (₹)"] * (1 + TAKE_PROFIT_PCT)).round(2)
    df["R:R"] = (
        (df["Target (₹)"] - df["LTP (₹)"]) /
        (df["LTP (₹)"] - df["Stop-Loss (₹)"])
    ).round(2)
    return df
