"""
Reversal Trading Strategies
Catching trend changes and capitulation moves
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import sys
sys.path.append('..')
from utils.technicals import calculate_rsi
from strategies.indicators import (
    calculate_ema, calculate_vwap, calculate_atr,
    calculate_bollinger_bands, calculate_rsi_divergence,
    calculate_supertrend, calculate_relative_volume
)


def rsi_reversal_strategy(df: pd.DataFrame, rsi_oversold: int = 30, rsi_overbought: int = 70) -> pd.DataFrame:
    """
    RSI REVERSAL STRATEGY
    Identify extreme oversold/overbought conditions with reversal confirmation
    
    Entry Rules:
    - BUY: RSI < 30 (extreme oversold) + bullish reversal bar (close > open) + volume spike
    - SELL: RSI > 70 (extreme overbought) + bearish reversal bar (close < open) + volume spike
    - Optional: RSI divergence for higher confidence
    
    Exit Rules:
    - Stop Loss: Below/above reversal bar low/high
    - Target: Middle Bollinger Band or 1.5x risk
    
    Confidence Scoring:
    - 5: RSI < 20 or > 80, divergence present, strong reversal bar
    - 3: RSI in oversold/overbought, good reversal candle
    - 1: Weak RSI reading, poor volume
    
    Args:
        df: OHLCV DataFrame
        rsi_oversold: Oversold threshold (default 30)
        rsi_overbought: Overbought threshold (default 70)
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['RSI'] = calculate_rsi(df['Close'].values, 14)
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(df['Close'].values, 20, 2.0)
    df['BB_Upper'] = upper_bb
    df['BB_Middle'] = middle_bb
    df['BB_Lower'] = lower_bb
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    
    # RSI Divergence detection
    bullish_div, bearish_div = calculate_rsi_divergence(df['Close'].values, df['RSI'].values, 14)
    df['Bullish_Divergence'] = bullish_div
    df['Bearish_Divergence'] = bearish_div
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    
    for i in range(14, len(df)):
        rsi = df['RSI'].iloc[i]
        close = df['Close'].iloc[i]
        open_price = df['Open'].iloc[i]
        low = df['Low'].iloc[i]
        high = df['High'].iloc[i]
        rel_vol = df['Relative_Volume'].iloc[i]
        bull_div = df['Bullish_Divergence'].iloc[i]
        bear_div = df['Bearish_Divergence'].iloc[i]
        bb_middle = df['BB_Middle'].iloc[i]
        
        # Bullish reversal bar
        is_bullish_bar = close > open_price and (close - open_price) / (high - low + 1e-10) > 0.5
        # Bearish reversal bar
        is_bearish_bar = close < open_price and (open_price - close) / (high - low + 1e-10) > 0.5
        
        # BUY Signal: Oversold reversal
        if rsi < rsi_oversold and is_bullish_bar and rel_vol > 1.0:  # Reduced from 1.5

            df.loc[df.index[i], 'Signal'] = 'BUY'
            df.loc[df.index[i], 'Entry_Price'] = close
            df.loc[df.index[i], 'Stop_Loss'] = low * 0.99
            
            # Target: Middle BB or 1.5x risk
            risk = close - low
            target = min(bb_middle, close + (1.5 * risk))
            df.loc[df.index[i], 'Target'] = target
            
            # Confidence scoring
            confidence = 3
            if rsi < 20:
                confidence = 5  # Extreme oversold
            elif rsi < 25:
                confidence = 4
            if bull_div:
                confidence = min(5, confidence + 1)  # Divergence adds confidence
            if rel_vol > 2.5:
                confidence = min(5, confidence + 1)
            
            df.loc[df.index[i], 'Confidence'] = confidence
        
        # SELL Signal: Overbought reversal
        elif rsi > rsi_overbought and is_bearish_bar and rel_vol > 1.0:  # Reduced from 1.5

            df.loc[df.index[i], 'Signal'] = 'SELL'
            df.loc[df.index[i], 'Entry_Price'] = close
            df.loc[df.index[i], 'Stop_Loss'] = high * 1.01
            
            risk = high - close
            target = max(bb_middle, close - (1.5 * risk))
            df.loc[df.index[i], 'Target'] = target
            
            confidence = 3
            if rsi > 80:
                confidence = 5
            elif rsi > 75:
                confidence = 4
            if bear_div:
                confidence = min(5, confidence + 1)
            if rel_vol > 2.5:
                confidence = min(5, confidence + 1)
            
            df.loc[df.index[i], 'Confidence'] = confidence
    
    return df


def capitulation_reversal_strategy(df: pd.DataFrame, volume_threshold: float = 5.0, drop_threshold: float = 3.0) -> pd.DataFrame:
    """
    CAPITULATION REVERSAL STRATEGY
    Catch panic selling bottoms and explosive reversals
    
    Entry Rules:
    - Identify capitulation: Sharp price drop (>3% in single bar) with parabolic volume (5x+)
    - Wait for reversal bar: Price recovers >50% of drop with strong close
    - BUY on confirmation bar after reversal
    
    Exit Rules:
    - Stop Loss: Below capitulation bar low
    - Target: Pre-capitulation price level or 2x risk
    
    Confidence Scoring:
    - 5: Massive volume (10x+), full recovery bar, clear capitulation
    - 3: Good volume (5x+), partial recovery
    - 1: Weak volume, unclear pattern
    
    Args:
        df: OHLCV DataFrame
        volume_threshold: Minimum volume multiplier (default 5.0x)
        drop_threshold: Minimum price drop percentage (default 3.0%)
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    df['Price_Change_Pct'] = df['Close'].pct_change() * 100
    df['EMA_20'] = calculate_ema(df['Close'].values, 20)
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    df['Capitulation_Bar'] = False
    
    for i in range(20, len(df) - 1):  # -1 to check next bar
        rel_vol = df['Relative_Volume'].iloc[i]
        price_change = df['Price_Change_Pct'].iloc[i]
        low = df['Low'].iloc[i]
        high = df['High'].iloc[i]
        close = df['Close'].iloc[i]
        open_price = df['Open'].iloc[i]
        
        # Next bar (reversal bar)
        next_close = df['Close'].iloc[i+1]
        next_open = df['Open'].iloc[i+1]
        next_low = df['Low'].iloc[i+1]
        next_high = df['High'].iloc[i+1]
        
        # Identify capitulation bar (panic selling)
        if (price_change < -drop_threshold * 0.7 and  # 2.1% instead of 3%
    rel_vol >= volume_threshold * 0.6):  # Fixed: rel_vol not rel_volume
  # 3x instead of 5x

            
            df.loc[df.index[i], 'Capitulation_Bar'] = True
            
            # Check for reversal in next bar
            drop_amount = high - low
            recovery = next_close - low
            recovery_pct = recovery / drop_amount if drop_amount > 0 else 0
            
            # Reversal bar: Recovers >50% of drop with strong close
            is_reversal = (recovery_pct > 0.5 and 
                          next_close > next_open and
                          (next_close - next_open) / (next_high - next_low + 1e-10) > 0.6)
            
            if is_reversal:
                df.loc[df.index[i+1], 'Signal'] = 'BUY'
                df.loc[df.index[i+1], 'Entry_Price'] = next_close
                df.loc[df.index[i+1], 'Stop_Loss'] = low * 0.98
                
                # Target: Pre-drop level or 2x risk
                pre_drop_price = df['Close'].iloc[i-1]
                risk = next_close - low
                target = min(pre_drop_price, next_close + (2 * risk))
                df.loc[df.index[i+1], 'Target'] = target
                
                # Confidence scoring
                confidence = 3
                if rel_vol > 10.0:
                    confidence = 5  # Extreme panic volume
                elif rel_vol > 7.0:
                    confidence = 4
                if recovery_pct > 0.8:
                    confidence = min(5, confidence + 1)  # Strong recovery
                
                df.loc[df.index[i+1], 'Confidence'] = confidence
    
    return df


def bollinger_squeeze_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """
    BOLLINGER BAND SQUEEZE REVERSAL
    Catch breakouts from low volatility compression
    
    Entry Rules:
    - Identify squeeze: Bollinger Bands narrowing (low volatility)
    - BUY: Price breaks above upper band with volume
    - SELL: Price breaks below lower band with volume
    - Confirm with RSI momentum
    
    Exit Rules:
    - Stop Loss: Middle band or opposite Bollinger Band
    - Target: 2x the band width
    
    Confidence Scoring:
    - 5: Tight squeeze, strong breakout, high volume
    - 3: Moderate squeeze, good volume
    - 1: Wide bands, weak breakout
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(df['Close'].values, 20, 2.0)
    df['BB_Upper'] = upper_bb
    df['BB_Middle'] = middle_bb
    df['BB_Lower'] = lower_bb
    df['BB_Width'] = (upper_bb - lower_bb) / middle_bb * 100  # Percentage width
    df['RSI'] = calculate_rsi(df['Close'].values, 14)
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    
    # Identify squeeze: BB width in lowest 20% of recent values
    df['BB_Width_Percentile'] = df['BB_Width'].rolling(50).apply(
        lambda x: (x.iloc[-1] <= x.quantile(0.2)), raw=False
    )
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    
    for i in range(50, len(df)):
        close = df['Close'].iloc[i]
        bb_upper = df['BB_Upper'].iloc[i]
        bb_lower = df['BB_Lower'].iloc[i]
        bb_middle = df['BB_Middle'].iloc[i]
        bb_width = df['BB_Width'].iloc[i]
        is_squeeze = df['BB_Width_Percentile'].iloc[i]
        rsi = df['RSI'].iloc[i]
        rel_vol = df['Relative_Volume'].iloc[i]
        
        prev_close = df['Close'].iloc[i-1]
        
        # BUY: Breakout above upper band during squeeze
        if (is_squeeze and 
    close > bb_upper and 
    prev_close <= bb_upper and
    rsi > 45 and  # More relaxed
    rel_vol > 1.0):  # Reduced from 1.5

            
            df.loc[df.index[i], 'Signal'] = 'BUY'
            df.loc[df.index[i], 'Entry_Price'] = close
            df.loc[df.index[i], 'Stop_Loss'] = bb_middle
            
            # Target: 2x band width
            band_width = bb_upper - bb_middle
            target = close + (2 * band_width)
            df.loc[df.index[i], 'Target'] = target
            
            # Confidence scoring
            confidence = 3
            if bb_width < 2.0:
                confidence = 5  # Very tight squeeze
            elif bb_width < 3.0:
                confidence = 4
            if rel_vol > 2.5:
                confidence = min(5, confidence + 1)
            
            df.loc[df.index[i], 'Confidence'] = confidence
        
        # SELL: Breakdown below lower band during squeeze
        elif (is_squeeze and 
      close < bb_lower and 
      prev_close >= bb_lower and
      rsi < 55 and  # More relaxed
      rel_vol > 1.0):  # Reduced from 1.5

            
            df.loc[df.index[i], 'Signal'] = 'SELL'
            df.loc[df.index[i], 'Entry_Price'] = close
            df.loc[df.index[i], 'Stop_Loss'] = bb_middle
            
            band_width = bb_middle - bb_lower
            target = close - (2 * band_width)
            df.loc[df.index[i], 'Target'] = target
            
            confidence = 3
            if bb_width < 2.0:
                confidence = 5
            elif bb_width < 3.0:
                confidence = 4
            if rel_vol > 2.5:
                confidence = min(5, confidence + 1)
            
            df.loc[df.index[i], 'Confidence'] = confidence
    
    return df


def supertrend_reversal_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    SUPERTREND REVERSAL STRATEGY
    Trade trend changes with Supertrend indicator
    
    Entry Rules:
    - BUY: Supertrend flips from bearish to bullish (red to green)
    - SELL: Supertrend flips from bullish to bearish (green to red)
    - Confirm with volume and price action
    
    Exit Rules:
    - Stop Loss: Supertrend line (dynamic trailing stop)
    - Target: 2x ATR or opposite Supertrend flip
    
    Confidence Scoring:
    - 5: Clear trend flip, strong candle, high volume
    - 3: Moderate flip, adequate volume
    - 1: Weak flip, low volume
    
    Returns:
        DataFrame with signals
    """
    df = df.copy()
    
    # Calculate indicators
    supertrend, trend = calculate_supertrend(df, 10, 3.0)
    df['Supertrend'] = supertrend
    df['Trend'] = trend  # 1 = uptrend, -1 = downtrend
    df['ATR'] = calculate_atr(df, 14)
    df['Relative_Volume'] = calculate_relative_volume(df['Volume'].values, 20)
    
    # Initialize columns
    df['Signal'] = 'HOLD'
    df['Confidence'] = 0
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Target'] = np.nan
    
    for i in range(14, len(df)):
        trend_current = df['Trend'].iloc[i]
        trend_prev = df['Trend'].iloc[i-1]
        close = df['Close'].iloc[i]
        open_price = df['Open'].iloc[i]
        supertrend_val = df['Supertrend'].iloc[i]
        atr = df['ATR'].iloc[i]
        rel_vol = df['Relative_Volume'].iloc[i]
        
        # Detect trend flip
        trend_flip_bullish = trend_prev == -1 and trend_current == 1
        trend_flip_bearish = trend_prev == 1 and trend_current == -1
        
        # Strong candle confirmation
        candle_strength = abs(close - open_price) / (df['High'].iloc[i] - df['Low'].iloc[i] + 1e-10)
        is_strong_candle = candle_strength > 0.6
        
        # BUY: Bearish to Bullish flip
        if trend_flip_bullish and rel_vol > 0.9:  # Reduced from 1.3
            df.loc[df.index[i], 'Signal'] = 'BUY'
            df.loc[df.index[i], 'Entry_Price'] = close
            df.loc[df.index[i], 'Stop_Loss'] = supertrend_val
            
            # Target: 2x ATR
            target = close + (2 * atr)
            df.loc[df.index[i], 'Target'] = target
            
            # Confidence
            confidence = 3
            if is_strong_candle:
                confidence += 1
            if rel_vol > 2.0:
                confidence += 1
            
            df.loc[df.index[i], 'Confidence'] = min(5, confidence)
        
        # SELL: Bullish to Bearish flip
        elif trend_flip_bearish and rel_vol > 0.9:  # Reduced from 1.3
            df.loc[df.index[i], 'Signal'] = 'SELL'
            df.loc[df.index[i], 'Entry_Price'] = close
            df.loc[df.index[i], 'Stop_Loss'] = supertrend_val
            
            target = close - (2 * atr)
            df.loc[df.index[i], 'Target'] = target
            
            confidence = 3
            if is_strong_candle:
                confidence += 1
            if rel_vol > 2.0:
                confidence += 1
            
            df.loc[df.index[i], 'Confidence'] = min(5, confidence)
    
    return df
