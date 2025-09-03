from utils.technicals import calculate_rsi, calculate_macd, calculate_smoothed_ma
import numpy as np
import pandas as pd

def score_stock(df):
    if df.empty or len(df) < 20:
        return 0, []
    try:
        close = df['Close'].values
        high = df['High'].values
        volume = df['Volume'].values

        score = 0
        signals = []

        rsi = calculate_rsi(close)
        macd, signal = calculate_macd(close)
        sma20 = calculate_smoothed_ma(close, 20)
        sma50 = calculate_smoothed_ma(close, 50)

        # Volume surge points
        vol_ratio = np.mean(volume[-3:])/np.mean(volume[-20:])
        if vol_ratio > 3: score += 4; signals.append("🔥 Explosive Volume")
        elif vol_ratio > 2: score += 3; signals.append("📈 High Volume")
        elif vol_ratio > 1.5: score += 2; signals.append("🔵 Above Avg Volume")

        # RSI points
        if 55 < rsi[-1] < 75:
            score += 3; signals.append("💪 RSI Strong Momentum Zone")
        elif rsi[-1] < 30:
            score += 2; signals.append("📉 RSI Oversold")
        elif rsi[-1] > 80:
            score -= 1; signals.append("⚠️ RSI Overbought")

        # MACD points
        if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
            score += 3; signals.append("🎯 MACD Bullish Crossover")
        elif macd[-1] > signal[-1]:
            score += 2; signals.append("⚡ MACD Above Signal")

        # Price momentum
        price_change_1d = (close[-1] - close[-2]) / close[-2]
        if price_change_1d > 0.05:
            score += 2; signals.append("🚀 Strong 1 Day Price Move +5%")
        elif price_change_1d > 0.02:
            score += 1; signals.append("📈 Moderate 1 Day Move +2%")

        # Moving average alignment
        if close[-1] > sma20[-1] > sma50[-1]:
            score += 3; signals.append("✅ Bullish MA Alignment")

        # Breakout Detection
        high_20 = np.max(high[-20:])
        if close[-1] >= high_20:
            score += 2; signals.append("🎉 20-Day High Breakout")

        return score, signals
    except:
        return 0, []
 
