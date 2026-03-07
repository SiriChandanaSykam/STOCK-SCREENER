# risk_manager.py — SL, TP, R:R auto-calculator for screened stocks

import pandas as pd


def apply_risk_management(df: pd.DataFrame) -> pd.DataFrame:
    """Add Stop-Loss, Take-Profit and Risk:Reward columns to screener output."""
    if df.empty:
        return df

    df = df.copy()
    df["Stop-Loss (₹)"] = (df["LTP (₹)"] * 0.95).round(2)
    df["Target (₹)"] = (df["LTP (₹)"] * 1.20).round(2)
    df["R:R"] = (
        (df["Target (₹)"] - df["LTP (₹)"]) /
        (df["LTP (₹)"] - df["Stop-Loss (₹)"])
    ).round(2)
    return df
