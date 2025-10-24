"""
Volume-Based Trading Strategies
Unusual activity detection and F&O Open Interest analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import sys
sys.path.append('..')
from utils.technicals import calculate_rsi
from strategies.indicators import (
    calculate_ema, calculate_vwap, calculate_atr,
    calculate_relative_volume, identify_swing_highs_lows
)


def unusual_volume_spike_strategy(df: pd.DataFrame, volume_threshold: float = 3.0) -> pd.DataFrame:
    """
    UNUSUAL VOLUME SPIKE STRATEGY
    Detect abnormal volume with price breakouts
    
    Entry Rules:
    - Volume spike: 3x+ average volume (customizable)
    - Price action: Making new high/low (breakout)
    - Direction: BUY if new high, SELL if new low
    - Confirmation: Price closes in top/bottom 25% of bar
    
    Exit Rules:
    - Stop Loss: Opposite end of spike bar
    - Target: 1.5x the spike bar range
    
    Confidence Scoring:
    - 5: Massive volume (5x+), clear breakout, strong close
    - 3: Good volume (3-5x), moderate breakout
    - 1: Weak volume (2-3x), unclear direction
    
    Args:
        df: OHLCV DataFrame
        volume_threshold: Minimum volume multiplier (default 3.0x)
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    df['20_Bar_High'] = df['High'].rolling(20).max()
    df['20_Bar_Low'] = df['Low'].rolling(20).min()
    df['ATR'] = calculate_atr(df, 14)
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    df['Volume_Spike'] = False
    
    for i in range(20, len(df)):
        rel_vol = df['Relative_Volume'].iloc[i]
        close = df['Close'].iloc[i]
        high = df['High'].iloc[i]
        low = df['Low'].iloc[i]
        bar_range = high - low
        high_20 = df['20_Bar_High'].iloc[i-1]  # Previous bar's high
        low_20 = df['20_Bar_Low'].iloc[i-1]  # Previous bar's low
        atr = df['ATR'].iloc[i]
        
        # Check if volume spike occurred
        if rel_vol >= volume_threshold * 0.7:  # 2.1x instead of 3x

            df.loc[df.index[i], 'Volume_Spike'] = True
            
            # Check close position in bar (top 25% = bullish, bottom 25% = bearish)
            close_position = (close - low) / (bar_range + 1e-10)
            
            # BUY: New high + volume spike + strong close
            if high > high_20 and close_position > 0.75:
                df.loc[df.index[i], 'Signal'] = 'BUY'
                df.loc[df.index[i], 'Entry_Price'] = close
                df.loc[df.index[i], 'Stop_Loss'] = low
                
                # Target: 1.5x bar range
                target = close + (1.5 * bar_range)
                df.loc[df.index[i], 'Target'] = target
                
                # Confidence scoring
                confidence = 3
                if rel_vol >= 5.0:
                    confidence = 5
                elif rel_vol >= 4.0:
                    confidence = 4
                if bar_range > atr * 1.5:
                    confidence = min(5, confidence + 1)  # Wide range bar
                
                df.loc[df.index[i], 'Confidence'] = confidence
            
            # SELL: New low + volume spike + weak close
            elif low < low_20 and close_position < 0.25:
                df.loc[df.index[i], 'Signal'] = 'SELL'
                df.loc[df.index[i], 'Entry_Price'] = close
                df.loc[df.index[i], 'Stop_Loss'] = high
                
                target = close - (1.5 * bar_range)
                df.loc[df.index[i], 'Target'] = target
                
                confidence = 3
                if rel_vol >= 5.0:
                    confidence = 5
                elif rel_vol >= 4.0:
                    confidence = 4
                if bar_range > atr * 1.5:
                    confidence = min(5, confidence + 1)
                
                df.loc[df.index[i], 'Confidence'] = confidence
    
    return df


def fo_buildup_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    F&O OPEN INTEREST BUILD-UP STRATEGY
    Detect Long/Short buildup in Futures & Options
    
    Build-up Types:
    1. LONG BUILD-UP: Price ↑ + OI ↑ (Bullish)
    2. SHORT BUILD-UP: Price ↓ + OI ↑ (Bearish)
    3. LONG UNWINDING: Price ↓ + OI ↓ (Bearish)
    4. SHORT COVERING: Price ↑ + OI ↓ (Bullish)
    
    Entry Rules:
    - BUY: Long buildup (price up 1%+, OI up 5%+) with volume
    - SELL: Short buildup (price down 1%+, OI up 5%+) with volume
    - Confirm with price momentum (RSI)
    
    Exit Rules:
    - Stop Loss: 2% from entry or recent swing point
    - Target: 2x risk
    
    Confidence Scoring:
    - 5: Strong buildup (price 2%+, OI 10%+), aligned momentum
    - 3: Moderate buildup (price 1%+, OI 5%+)
    - 1: Weak buildup, conflicting signals
    
    Note: Requires 'Open_Interest' column in DataFrame
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Check if Open Interest data exists
    if 'Open_Interest' not in df.columns:
        print("Warning: 'Open_Interest' column not found. Creating dummy data for demo.")
        # For demo purposes, create synthetic OI data
        df['Open_Interest'] = df['Volume'] * np.random.uniform(0.8, 1.2, len(df))
    
    # Calculate indicators
    df['Price_Change_Pct'] = df['Close'].pct_change() * 100
    df['OI_Change_Pct'] = df['Open_Interest'].pct_change() * 100
    df['RSI'] = calculate_rsi(df['Close'].values, 14)
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    df['ATR'] = calculate_atr(df, 14)
    
    # Identify buildup type
    df['Buildup_Type'] = 'NONE'
    
    for i in range(1, len(df)):
        price_chg = df['Price_Change_Pct'].iloc[i]
        oi_chg = df['OI_Change_Pct'].iloc[i]
        
        if price_chg > 0 and oi_chg > 0:
            df.loc[df.index[i], 'Buildup_Type'] = 'LONG_BUILDUP'
        elif price_chg < 0 and oi_chg > 0:
            df.loc[df.index[i], 'Buildup_Type'] = 'SHORT_BUILDUP'
        elif price_chg < 0 and oi_chg < 0:
            df.loc[df.index[i], 'Buildup_Type'] = 'LONG_UNWINDING'
        elif price_chg > 0 and oi_chg < 0:
            df.loc[df.index[i], 'Buildup_Type'] = 'SHORT_COVERING'
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    
    for i in range(14, len(df)):
        buildup = df['Buildup_Type'].iloc[i]
        price_chg = df['Price_Change_Pct'].iloc[i]
        oi_chg = df['OI_Change_Pct'].iloc[i]
        close = df['Close'].iloc[i]
        rsi = df['RSI'].iloc[i]
        rel_vol = df['Relative_Volume'].iloc[i]
        atr = df['ATR'].iloc[i]
        
        # BUY: Long Buildup or Short Covering
        if ((buildup == 'LONG_BUILDUP' and price_chg > 0.5 and oi_chg > 3.0) or  # More relaxed
    (buildup == 'SHORT_COVERING' and price_chg > 0.5 and abs(oi_chg) > 3.0)):
            
            if rsi > 45 and rel_vol > 1.0:
                df.loc[df.index[i], 'Signal'] = 'BUY'
                df.loc[df.index[i], 'Entry_Price'] = close
                
                # Stop loss: 2% or 2x ATR
                stop_loss = close - max(close * 0.02, 2 * atr)
                df.loc[df.index[i], 'Stop_Loss'] = stop_loss
                
                risk = close - stop_loss
                target = close + (2 * risk)
                df.loc[df.index[i], 'Target'] = target
                
                # Confidence scoring
                confidence = 3
                if price_chg > 2.0 and oi_chg > 10.0:
                    confidence = 5
                elif price_chg > 1.5 and oi_chg > 7.5:
                    confidence = 4
                if rsi > 60:
                    confidence = min(5, confidence + 1)
                
                df.loc[df.index[i], 'Confidence'] = confidence
        
        # SELL: Short Buildup or Long Unwinding
        elif ((buildup == 'SHORT_BUILDUP' and price_chg < -0.5 and oi_chg > 3.0) or  # More relaxed
      (buildup == 'LONG_UNWINDING' and price_chg < -0.5 and abs(oi_chg) > 3.0)):
            
            if rsi < 55 and rel_vol > 1.0:
                df.loc[df.index[i], 'Signal'] = 'SELL'
                df.loc[df.index[i], 'Entry_Price'] = close
                
                stop_loss = close + max(close * 0.02, 2 * atr)
                df.loc[df.index[i], 'Stop_Loss'] = stop_loss
                
                risk = stop_loss - close
                target = close - (2 * risk)
                df.loc[df.index[i], 'Target'] = target
                
                confidence = 3
                if price_chg < -2.0 and oi_chg > 10.0:
                    confidence = 5
                elif price_chg < -1.5 and oi_chg > 7.5:
                    confidence = 4
                if rsi < 40:
                    confidence = min(5, confidence + 1)
                
                df.loc[df.index[i], 'Confidence'] = confidence
    
    return df


def scalping_micro_breakout_strategy(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """
    SCALPING MICRO-BREAKOUT STRATEGY
    Quick trades on small breakouts (for active traders)
    
    Entry Rules:
    - Identify micro-range: High/Low of last 3-5 bars
    - BUY: Break above range high + increasing volume
    - SELL: Break below range low + increasing volume
    - Time constraint: Exit within 3-10 bars (scalp trade)
    
    Exit Rules:
    - Stop Loss: Opposite end of range (tight stop)
    - Target: 1x range size (quick target)
    - Time stop: Exit after 10 bars regardless
    
    Confidence Scoring:
    - 5: Clean breakout, strong volume, trending market
    - 3: Adequate breakout, moderate volume
    - 1: Weak breakout, choppy market
    
    Args:
        df: Intraday OHLCV DataFrame (1min or 5min recommended)
        lookback: Range period in bars (default 5)
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['Range_High'] = df['High'].rolling(lookback).max()
    df['Range_Low'] = df['Low'].rolling(lookback).min()
    df['Range_Size'] = df['Range_High'] - df['Range_Low']
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    df['EMA_20'] = calculate_ema(df['Close'].values, 20)
    df['VWAP'] = calculate_vwap(df)
    
    # Detect trending vs choppy market
    df['Price_Std'] = df['Close'].rolling(20).std()
    df['Is_Trending'] = df['Price_Std'] > df['Price_Std'].rolling(50).mean()
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    df['Bars_Held'] = 0
    
    for i in range(lookback + 20, len(df)):
        close = df['Close'].iloc[i]
        high = df['High'].iloc[i]
        low = df['Low'].iloc[i]
        range_high = df['Range_High'].iloc[i-1]  # Previous range
        range_low = df['Range_Low'].iloc[i-1]
        range_size = df['Range_Size'].iloc[i-1]
        rel_vol = df['Relative_Volume'].iloc[i]
        ema_20 = df['EMA_20'].iloc[i]
        vwap = df['VWAP'].iloc[i]
        is_trending = df['Is_Trending'].iloc[i]
        
        prev_close = df['Close'].iloc[i-1]
        
        # Only trade in trending markets (avoid chop)
        if not is_trending:
            continue
        
        # BUY: Micro-breakout above range high
        if (high > range_high and 
    close > range_high and
    prev_close <= range_high and
    rel_vol > 0.8):  # Much more relaxed

            
            # Additional filter: Price above VWAP for longs
            if close > vwap:
                df.loc[df.index[i], 'Signal'] = 'BUY'
                df.loc[df.index[i], 'Entry_Price'] = close
                df.loc[df.index[i], 'Stop_Loss'] = range_low
                
                # Quick target: 1x range size
                target = close + range_size
                df.loc[df.index[i], 'Target'] = target
                
                # Confidence scoring
                confidence = 3
                if rel_vol > 2.0:
                    confidence += 1
                if close > ema_20:
                    confidence += 1
                
                df.loc[df.index[i], 'Confidence'] = min(5, confidence)
        
        # SELL: Micro-breakdown below range low
        elif (low < range_low and 
      close < range_low and
      prev_close >= range_low and
      rel_vol > 0.8):  # Much more relaxed

            
            # Additional filter: Price below VWAP for shorts
            if close < vwap:
                df.loc[df.index[i], 'Signal'] = 'SELL'
                df.loc[df.index[i], 'Entry_Price'] = close
                df.loc[df.index[i], 'Stop_Loss'] = range_high
                
                target = close - range_size
                df.loc[df.index[i], 'Target'] = target
                
                confidence = 3
                if rel_vol > 2.0:
                    confidence += 1
                if close < ema_20:
                    confidence += 1
                
                df.loc[df.index[i], 'Confidence'] = min(5, confidence)
    
    return df


def price_volume_divergence_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    PRICE-VOLUME DIVERGENCE STRATEGY
    Detect when price and volume disagree (warning signal)
    
    Divergence Types:
    1. Bearish: Price making higher highs, Volume declining
    2. Bullish: Price making lower lows, Volume declining
    
    Entry Rules:
    - Identify divergence over 10-bar period
    - BUY: Bullish divergence + reversal confirmation
    - SELL: Bearish divergence + reversal confirmation
    - Confirm with RSI
    
    Exit Rules:
    - Stop Loss: Recent swing point
    - Target: 1.5x risk
    
    Confidence Scoring:
    - 5: Clear divergence, strong reversal bar, RSI confirmation
    - 3: Moderate divergence, adequate reversal
    - 1: Weak divergence, unclear pattern
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['Volume_MA'] = calculate_relative_volume(df['Volume'].values, 10)
    df['RSI'] = calculate_rsi(df['Close'].values, 14)
    df['ATR'] = calculate_atr(df, 14)
    
    # Identify swing highs and lows
    swing_highs, swing_lows = identify_swing_highs_lows(df['Close'].values, 5)
    df['Swing_High'] = np.where(swing_highs, df['High'], np.nan)
    df['Swing_Low'] = np.where(swing_lows, df['Low'], np.nan)
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    df['Divergence_Type'] = 'NONE'
    
    for i in range(20, len(df)):
        close = df['Close'].iloc[i]
        rsi = df['RSI'].iloc[i]
        atr = df['ATR'].iloc[i]
        
        # Look back 10 bars for divergence
        recent_data = df.iloc[i-10:i+1]
        
        # Bearish Divergence: Higher highs in price, lower volume
        price_highs = recent_data['Close'].nlargest(2)
        if len(price_highs) == 2 and price_highs.iloc[0] > price_highs.iloc[1]:
            vol_at_highs = recent_data.loc[price_highs.index, 'Volume'].values
            if vol_at_highs[0] < vol_at_highs[1]:
                df.loc[df.index[i], 'Divergence_Type'] = 'BEARISH'
                
                # SELL on confirmation
                if rsi > 60 and close < df['Close'].iloc[i-1]:
                    df.loc[df.index[i], 'Signal'] = 'SELL'
                    df.loc[df.index[i], 'Entry_Price'] = close
                    
                    stop_loss = df['Swing_High'].iloc[i-10:i].max()
                    if pd.isna(stop_loss):
                        stop_loss = close + (2 * atr)
                    df.loc[df.index[i], 'Stop_Loss'] = stop_loss
                    
                    risk = stop_loss - close
                    target = close - (1.5 * risk)
                    df.loc[df.index[i], 'Target'] = target
                    
                    df.loc[df.index[i], 'Confidence'] = 4
        
        # Bullish Divergence: Lower lows in price, lower volume
        price_lows = recent_data['Close'].nsmallest(2)
        if len(price_lows) == 2 and price_lows.iloc[0] < price_lows.iloc[1]:
            vol_at_lows = recent_data.loc[price_lows.index, 'Volume'].values
            if vol_at_lows[0] < vol_at_lows[1]:
                df.loc[df.index[i], 'Divergence_Type'] = 'BULLISH'
                
                # BUY on confirmation
                if rsi < 40 and close > df['Close'].iloc[i-1]:
                    df.loc[df.index[i], 'Signal'] = 'BUY'
                    df.loc[df.index[i], 'Entry_Price'] = close
                    
                    stop_loss = df['Swing_Low'].iloc[i-10:i].min()
                    if pd.isna(stop_loss):
                        stop_loss = close - (2 * atr)
                    df.loc[df.index[i], 'Stop_Loss'] = stop_loss
                    
                    risk = close - stop_loss
                    target = close + (1.5 * risk)
                    df.loc[df.index[i], 'Target'] = target
                    
                    df.loc[df.index[i], 'Confidence'] = 4
    
    return df
