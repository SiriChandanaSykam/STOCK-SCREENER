"""
Advanced Technical Indicators for Trading Strategies
Builds on existing technicals.py with additional indicators
"""

import numpy as np
import pandas as pd
from typing import Tuple


def calculate_ema(prices: np.ndarray, period: int = 20) -> np.ndarray:
    """
    Calculate Exponential Moving Average
    Used for trend identification and support/resistance
    """
    return pd.Series(prices).ewm(span=period, adjust=False, min_periods=period).mean().values


def calculate_vwap(df: pd.DataFrame) -> np.ndarray:
    """
    Calculate Volume Weighted Average Price (VWAP)
    Critical for intraday trading - institutional benchmark price
    
    Args:
        df: DataFrame with High, Low, Close, Volume columns
    """
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    vwap = (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()
    return vwap.values


def calculate_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """
    Calculate Average True Range (ATR)
    Used for stop-loss placement and volatility measurement
    """
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]  # First value has no previous close
    
    atr = pd.Series(tr).rolling(period, min_periods=1).mean().values
    return atr


def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands
    Used for volatility and overbought/oversold conditions
    
    Returns:
        upper_band, middle_band, lower_band
    """
    middle = pd.Series(prices).rolling(period, min_periods=period).mean()
    std = pd.Series(prices).rolling(period, min_periods=period).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper.values, middle.values, lower.values


def calculate_volume_sma(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """
    Calculate Simple Moving Average of Volume
    Used to identify unusual volume spikes
    """
    return pd.Series(volume).rolling(period, min_periods=1).mean().values


def calculate_relative_volume(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """
    Calculate Relative Volume (current volume / average volume)
    Values > 2.0 indicate strong unusual activity
    """
    avg_volume = calculate_volume_sma(volume, period)
    avg_volume = np.where(avg_volume == 0, 1, avg_volume)  # Avoid division by zero
    return volume / avg_volume


def identify_swing_highs_lows(prices: np.ndarray, window: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Identify swing highs and lows for support/resistance
    
    Returns:
        swing_highs (boolean array), swing_lows (boolean array)
    """
    highs = np.zeros(len(prices), dtype=bool)
    lows = np.zeros(len(prices), dtype=bool)
    
    for i in range(window, len(prices) - window):
        # Swing high: price higher than surrounding bars
        if prices[i] == np.max(prices[i-window:i+window+1]):
            highs[i] = True
        # Swing low: price lower than surrounding bars
        if prices[i] == np.min(prices[i-window:i+window+1]):
            lows[i] = True
    
    return highs, lows


def calculate_rsi_divergence(prices: np.ndarray, rsi: np.ndarray, lookback: int = 14) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect bullish and bearish RSI divergence
    Powerful reversal signal when price and RSI disagree
    
    Returns:
        bullish_divergence (boolean), bearish_divergence (boolean)
    """
    bullish_div = np.zeros(len(prices), dtype=bool)
    bearish_div = np.zeros(len(prices), dtype=bool)
    
    for i in range(lookback, len(prices)):
        recent_prices = prices[i-lookback:i+1]
        recent_rsi = rsi[i-lookback:i+1]
        
        # Bullish divergence: price making lower lows, RSI making higher lows
        if recent_prices[-1] < np.min(recent_prices[:-1]) and recent_rsi[-1] > np.min(recent_rsi[:-1]):
            bullish_div[i] = True
        
        # Bearish divergence: price making higher highs, RSI making lower highs
        if recent_prices[-1] > np.max(recent_prices[:-1]) and recent_rsi[-1] < np.max(recent_rsi[:-1]):
            bearish_div[i] = True
    
    return bullish_div, bearish_div


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate Supertrend indicator
    Excellent for trend identification and trailing stops
    
    Returns:
        supertrend (values), trend (1 for uptrend, -1 for downtrend)
    """
    hl2 = (df['High'] + df['Low']) / 2
    atr = calculate_atr(df, period)
    
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    supertrend = np.zeros(len(df))
    trend = np.zeros(len(df))
    
    # Initialize
    supertrend[0] = upper_band[0]
    trend[0] = 1
    
    for i in range(1, len(df)):
        close = df['Close'].iloc[i]
        prev_close = df['Close'].iloc[i-1]
        
        # Update bands
        if close > upper_band[i-1]:
            supertrend[i] = lower_band[i]
            trend[i] = 1
        elif close < lower_band[i-1]:
            supertrend[i] = upper_band[i]
            trend[i] = -1
        else:
            supertrend[i] = supertrend[i-1]
            trend[i] = trend[i-1]
            
            if trend[i] == 1 and close < supertrend[i]:
                trend[i] = -1
                supertrend[i] = upper_band[i]
            elif trend[i] == -1 and close > supertrend[i]:
                trend[i] = 1
                supertrend[i] = lower_band[i]
    
    return supertrend, trend


def detect_gap(df: pd.DataFrame, min_gap_percent: float = 1.0) -> np.ndarray:
    """
    Detect gap up/down at market open
    Gap % = ((Open - Previous Close) / Previous Close) * 100
    
    Returns:
        gap_percent array (positive for gap up, negative for gap down)
    """
    prev_close = df['Close'].shift(1)
    current_open = df['Open']
    
    gap_percent = ((current_open - prev_close) / prev_close) * 100
    gap_percent = gap_percent.fillna(0).values
    
    # Only consider gaps above threshold
    gap_percent = np.where(np.abs(gap_percent) >= min_gap_percent, gap_percent, 0)
    
    return gap_percent
