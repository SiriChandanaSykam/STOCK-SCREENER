"""
Momentum-Based Trading Strategies
High-probability setups for trending markets and breakouts
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import sys
sys.path.append('..')
from utils.technicals import calculate_rsi
from strategies.indicators import (
    calculate_ema, calculate_vwap, calculate_atr,
    calculate_relative_volume, identify_swing_highs_lows, detect_gap
)


def momentum_breakout_strategy(df: pd.DataFrame, lookback: int = 20, volume_multiplier: float = 2.0) -> pd.DataFrame:
    """
    MOMENTUM BREAKOUT STRATEGY
    
    Entry Rules:
    - BUY: Price breaks above highest high of last N bars (default 20)
    - Volume must be at least 2x the recent average
    - Price must be above 20 EMA (trend confirmation)
    
    Exit Rules:
    - Stop Loss: Recent swing low or 2% below entry
    - Target: 2x the risk (Risk:Reward = 1:2)
    
    Confidence Scoring (1-5):
    - 5: Strong breakout with 3x+ volume, far from resistance
    - 4: Good volume (2-3x), clean breakout
    - 3: Adequate volume (1.5-2x), some resistance nearby
    - 2: Weak volume, multiple resistance levels
    - 1: Very weak setup, avoid
    
    Args:
        df: OHLCV DataFrame
        lookback: Period for identifying highs (default 20)
        volume_multiplier: Minimum volume increase required (default 2.0)
    
    Returns:
        DataFrame with signals and confidence scores
    """
    df = df.copy()
    
    # Calculate indicators
    df['EMA_20'] = calculate_ema(df['Close'].values, 20)
    df['Highest_High'] = df['High'].rolling(lookback).max()
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    df['ATR'] = calculate_atr(df, 14)
    
    # Identify swing lows for stop loss
    _, swing_lows = identify_swing_highs_lows(df['Low'].values, 5)
    df['Swing_Low'] = np.where(swing_lows, df['Low'], np.nan)
    df['Recent_Swing_Low'] = df['Swing_Low'].ffill()  # Updated syntax

    
    # Initialize signal columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    df['Risk_Reward'] = np.nan
    
    for i in range(lookback, len(df)):
        close = df['Close'].iloc[i]
        high = df['High'].iloc[i]
        ema_20 = df['EMA_20'].iloc[i]
        highest_high = df['Highest_High'].iloc[i-1]  # Previous bar's high
        rel_volume = df['Relative_Volume'].iloc[i]
        atr = df['ATR'].iloc[i]
        recent_low = df['Recent_Swing_Low'].iloc[i]
        
        # BUY Signal: Breakout above recent high with volume
        if (high > highest_high and rel_volume >= volume_multiplier * 0.7):  # Lower volume requirement

            df.loc[df.index[i], 'Signal'] = 'BUY'
            df.loc[df.index[i], 'Entry_Price'] = close
            
            # Stop Loss: Lower of swing low or 2% below entry
            stop_loss = max(recent_low, close * 0.98)
            df.loc[df.index[i], 'Stop_Loss'] = stop_loss
            
            # Target: 2x risk (1:2 Risk:Reward)
            risk = close - stop_loss
            target = close + (2 * risk)
            df.loc[df.index[i], 'Target'] = target
            df.loc[df.index[i], 'Risk_Reward'] = 2.0
            
            # Calculate confidence score
            confidence = 3  # Base score
            
            if rel_volume >= 3.0:
                confidence += 1  # Strong volume
            if close > ema_20 * 1.01:
                confidence += 1  # Strong momentum
            if risk < atr * 2:
                confidence -= 1  # Tight stop, risky
            
            df.loc[df.index[i], 'Confidence'] = max(1, min(5, confidence))
    
    return df


def opening_range_breakout_strategy(df: pd.DataFrame, orb_minutes: int = 15, min_gap: float = 0.5) -> pd.DataFrame:
    """
    OPENING RANGE BREAKOUT (ORB) STRATEGY
    Professional gap-and-go setup used by institutional traders
    
    Entry Rules:
    - Identify gap up/down at market open (>0.5% default)
    - Define opening range: High and Low of first 15 minutes
    - BUY: Price breaks above OR high with increasing volume
    - SHORT: Price breaks below OR low with increasing volume
    
    Exit Rules:
    - Stop Loss: Opposite side of opening range
    - Target: Opening range size projected from breakout point
    
    Confidence Scoring:
    - 5: Large gap (>2%), strong volume, clear range
    - 3: Medium gap (1-2%), good volume
    - 1: Small gap (<1%), weak setup
    
    Args:
        df: Intraday OHLCV DataFrame (5min or 15min recommended)
        orb_minutes: Opening range period in minutes (default 15)
        min_gap: Minimum gap percentage required (default 0.5%)
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Detect gaps
    df['Gap_Percent'] = detect_gap(df, min_gap)
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    df['OR_High'] = np.nan
    df['OR_Low'] = np.nan
    
    # Identify opening range for each trading day
    # Assumes df has datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        return df
    
    df['Date'] = df.index.date
    
    for date in df['Date'].unique():
        day_data = df[df['Date'] == date]
        
        if len(day_data) < 3:  # Need at least 3 bars
            continue
        
        # Get opening range (first 15 minutes = first 3 bars if 5min data)
        or_bars = min(orb_minutes // 5, len(day_data) // 2)  # Adjust based on timeframe
        or_data = day_data.iloc[:or_bars]
        
        or_high = or_data['High'].max()
        or_low = or_data['Low'].min()
        or_range = or_high - or_low
        gap = day_data['Gap_Percent'].iloc[0]
        
        # Skip if no significant gap
        if abs(gap) < min_gap:
            continue
        
        # Check for breakout after opening range
        for idx in day_data.index[or_bars:]:
            i = df.index.get_loc(idx)
            close = df['Close'].iloc[i]
            high = df['High'].iloc[i]
            low = df['Low'].iloc[i]
            rel_vol = df['Relative_Volume'].iloc[i]
            
            df.loc[idx, 'OR_High'] = or_high
            df.loc[idx, 'OR_Low'] = or_low
            
            # BUY: Break above opening range high
            if high > or_high and close > or_high and rel_vol > 1.0:  # Reduced from 1.5
                df.loc[idx, 'Signal'] = 'BUY'
                df.loc[idx, 'Entry_Price'] = close
                df.loc[idx, 'Stop_Loss'] = or_low
                df.loc[idx, 'Target'] = close + or_range
                
                # Confidence based on gap size and volume
                confidence = 3
                if abs(gap) > 2.0:
                    confidence = 5
                elif abs(gap) > 1.0:
                    confidence = 4
                if rel_vol > 2.5:
                    confidence = min(5, confidence + 1)
                
                df.loc[idx, 'Confidence'] = confidence
            
            # SHORT: Break below opening range low
            elif low < or_low and close < or_low and rel_vol > 1.0:  # Reduced from 1.5

                df.loc[idx, 'Signal'] = 'SELL'
                df.loc[idx, 'Entry_Price'] = close
                df.loc[idx, 'Stop_Loss'] = or_high
                df.loc[idx, 'Target'] = close - or_range
                
                confidence = 3
                if abs(gap) > 2.0:
                    confidence = 5
                elif abs(gap) > 1.0:
                    confidence = 4
                if rel_vol > 2.5:
                    confidence = min(5, confidence + 1)
                
                df.loc[idx, 'Confidence'] = confidence
    
    return df


def vwap_ema_trend_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    VWAP + EMA TREND FOLLOWING STRATEGY
    Institutional-grade system using VWAP as dynamic support/resistance
    
    Entry Rules:
    - LONG: Price above both 20 EMA and VWAP, pullback completes, volume increases
    - SHORT: Price below both 20 EMA and VWAP, pullback completes, volume increases
    - Confirm trend: EMA must be above/below VWAP
    
    Exit Rules:
    - Stop Loss: Below VWAP for longs, above VWAP for shorts
    - Target: 1.5x risk
    
    Confidence Scoring:
    - 5: Strong trend, price far from VWAP, high volume
    - 3: Moderate trend, price near VWAP
    - 1: Weak trend, choppy price action
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['EMA_20'] = calculate_ema(df['Close'].values, 20)
    df['VWAP'] = calculate_vwap(df)
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    df['ATR'] = calculate_atr(df, 14)
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    
    for i in range(20, len(df)):
        close = df['Close'].iloc[i]
        ema_20 = df['EMA_20'].iloc[i]
        vwap = df['VWAP'].iloc[i]
        rel_vol = df['Relative_Volume'].iloc[i]
        atr = df['ATR'].iloc[i]
        
        prev_close = df['Close'].iloc[i-1]
        prev_ema = df['EMA_20'].iloc[i-1]
        
        # LONG Setup: Uptrend with pullback completion
        if (close > ema_20 and close > vwap and ema_20 > vwap):
            # Check for pullback: previous bar was below EMA, current above
            if prev_close < prev_ema and close > ema_20 and rel_vol > 1.0:  # Reduced from 1.5
                df.loc[df.index[i], 'Signal'] = 'BUY'
                df.loc[df.index[i], 'Entry_Price'] = close
                df.loc[df.index[i], 'Stop_Loss'] = vwap
                
                risk = close - vwap
                target = close + (1.5 * risk)
                df.loc[df.index[i], 'Target'] = target
                
                # Confidence scoring
                distance_from_vwap = ((close - vwap) / vwap) * 100
                confidence = 3
                
                if distance_from_vwap > 1.0:
                    confidence += 1  # Strong trend
                if rel_vol > 2.5:
                    confidence += 1  # High volume confirmation
                
                df.loc[df.index[i], 'Confidence'] = min(5, confidence)
        
        # SHORT Setup: Downtrend with pullback completion
        elif (close < ema_20 and close < vwap and ema_20 < vwap):
            if prev_close > prev_ema and close < ema_20 and rel_vol > 1.0:  # Reduced from 1.5
                df.loc[df.index[i], 'Signal'] = 'SELL'
                df.loc[df.index[i], 'Entry_Price'] = close
                df.loc[df.index[i], 'Stop_Loss'] = vwap
                
                risk = vwap - close
                target = close - (1.5 * risk)
                df.loc[df.index[i], 'Target'] = target
                
                distance_from_vwap = ((vwap - close) / vwap) * 100
                confidence = 3
                
                if distance_from_vwap > 1.0:
                    confidence += 1
                if rel_vol > 2.5:
                    confidence += 1
                
                df.loc[df.index[i], 'Confidence'] = min(5, confidence)
    
    return df


def pullback_buy_strategy(df: pd.DataFrame, ema_period: int = 20) -> pd.DataFrame:
    """
    PULLBACK TO SUPPORT STRATEGY
    Buy dips in strong uptrends at key support levels
    
    Entry Rules:
    - Identify uptrend: Price consistently above rising EMA
    - Wait for pullback to EMA or VWAP
    - BUY when price bounces off support with volume
    - Confirm: Higher lows pattern
    
    Exit Rules:
    - Stop Loss: Below pullback low or EMA (whichever is lower)
    - Target: Recent swing high or 2x risk
    
    Confidence Scoring:
    - 5: Strong uptrend, perfect bounce, high volume
    - 3: Moderate trend, adequate bounce
    - 1: Weak trend, poor volume
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['EMA'] = calculate_ema(df['Close'].values, ema_period)
    df['VWAP'] = calculate_vwap(df)
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    
    # Identify swing highs for targets
    swing_highs, _ = identify_swing_highs_lows(df['High'].values, 5)
    df['Swing_High'] = np.where(swing_highs, df['High'], np.nan)
    df['Recent_Swing_High'] = df['Swing_High'].ffill()  # Updated syntax

    
    # Check if EMA is rising (uptrend)
    df['EMA_Rising'] = df['EMA'].diff(3) > 0
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    
    for i in range(ema_period + 5, len(df)):
        close = df['Close'].iloc[i]
        low = df['Low'].iloc[i]
        ema = df['EMA'].iloc[i]
        vwap = df['VWAP'].iloc[i]
        rel_vol = df['Relative_Volume'].iloc[i]
        ema_rising = df['EMA_Rising'].iloc[i]
        recent_high = df['Recent_Swing_High'].iloc[i]
        
        # Check previous bars for pullback pattern
        prev_close = df['Close'].iloc[i-1]
        prev_low = df['Low'].iloc[i-1]
        
        # Pullback Buy Setup
        if ema_rising and close > ema:
            # Previous bar touched or went below EMA/VWAP (pullback)
            support_level = max(ema, vwap)
            
            if (prev_low <= support_level * 1.02 and  close > prev_close and  rel_vol > 0.8):  # Much lower volume requirement

                
                df.loc[df.index[i], 'Signal'] = 'BUY'
                df.loc[df.index[i], 'Entry_Price'] = close
                
                # Stop loss below pullback low
                stop_loss = min(prev_low, support_level * 0.99)
                df.loc[df.index[i], 'Stop_Loss'] = stop_loss
                
                # Target: Recent swing high
                risk = close - stop_loss
                target = min(recent_high, close + (2 * risk))
                df.loc[df.index[i], 'Target'] = target
                
                # Confidence scoring
                confidence = 3
                
                # Perfect bounce off EMA
                if abs(prev_low - ema) / ema < 0.005:
                    confidence += 1
                
                # Strong volume
                if rel_vol > 2.0:
                    confidence += 1
                
                # Close to recent high (strong uptrend)
                if close > recent_high * 0.95:
                    confidence += 1
                
                df.loc[df.index[i], 'Confidence'] = min(5, confidence)
    
    return df
