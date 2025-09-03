import numpy as np
import pandas as pd

def calculate_rsi(prices, period=14):
    delta = np.diff(prices, prepend=prices[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period, min_periods=1).mean().values
    avg_loss = pd.Series(loss).rolling(period, min_periods=1).mean().values
    avg_loss = np.where(avg_loss==0,1e-10,avg_loss)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    ema12 = pd.Series(prices).ewm(span=12, min_periods=1).mean()
    ema26 = pd.Series(prices).ewm(span=26, min_periods=1).mean()
    macd = ema12 - ema26
    signal = pd.Series(macd).ewm(span=9, min_periods=1).mean()
    return macd.values, signal.values

def calculate_smoothed_ma(prices, window=20):
    return pd.Series(prices).rolling(window, min_periods=1).mean().values
 
