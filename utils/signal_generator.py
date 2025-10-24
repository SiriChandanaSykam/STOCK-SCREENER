"""
Multi-Strategy Signal Generator
Aggregates signals from all strategies with consensus scoring
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import sys
sys.path.append('..')

# Import all strategies
from strategies.momentum_strategies import (
    momentum_breakout_strategy,
    opening_range_breakout_strategy,
    vwap_ema_trend_strategy,
    pullback_buy_strategy
)
from strategies.reversal_strategies import (
    rsi_reversal_strategy,
    capitulation_reversal_strategy,
    bollinger_squeeze_reversal,
    supertrend_reversal_strategy
)
from strategies.volume_strategies import (
    unusual_volume_spike_strategy,
    fo_buildup_strategy,
    scalping_micro_breakout_strategy,
    price_volume_divergence_strategy
)


class MultiStrategySignalGenerator:
    """
    Aggregate signals from multiple strategies and generate consensus
    """
    
    def __init__(self):
        self.strategies = {
            'Momentum Breakout': momentum_breakout_strategy,
            'Opening Range Breakout': opening_range_breakout_strategy,
            'VWAP-EMA Trend': vwap_ema_trend_strategy,
            'Pullback Buy': pullback_buy_strategy,
            'RSI Reversal': rsi_reversal_strategy,
            'Capitulation Reversal': capitulation_reversal_strategy,
            'Bollinger Squeeze': bollinger_squeeze_reversal,
            'Supertrend Reversal': supertrend_reversal_strategy,
            'Volume Spike': unusual_volume_spike_strategy,
            'F&O Buildup': fo_buildup_strategy,
            'Micro Breakout': scalping_micro_breakout_strategy,
            'Price-Volume Divergence': price_volume_divergence_strategy
        }
    
    def generate_signals(self, df: pd.DataFrame, selected_strategies: List[str] = None) -> pd.DataFrame:
        """
        Generate signals from selected strategies
        
        Args:
            df: OHLCV DataFrame
            selected_strategies: List of strategy names to use (None = all)
        
        Returns:
            DataFrame with signals from all strategies
        """
        if selected_strategies is None:
            selected_strategies = list(self.strategies.keys())
        
        results = {}
        
        for strategy_name in selected_strategies:
            if strategy_name in self.strategies:
                try:
                    strategy_func = self.strategies[strategy_name]
                    result = strategy_func(df.copy())
                    results[strategy_name] = result[['Signal', 'Confidence', 'Entry_Price', 'Stop_Loss', 'Target']]
                except Exception as e:
                    print(f"Error in {strategy_name}: {str(e)}")
                    continue
        
        return results
    
    def create_consensus_signal(self, df: pd.DataFrame, selected_strategies: List[str] = None) -> pd.DataFrame:
        """
        Create consensus signal by aggregating all strategy signals
        
        Consensus Rules:
        - Overall Signal: Majority vote (BUY/SELL/HOLD)
        - Consensus Score: Average confidence of agreeing strategies
        - Signal Strength: % of strategies agreeing
        
        Args:
            df: OHLCV DataFrame
            selected_strategies: List of strategy names
        
        Returns:
            DataFrame with consensus signals and individual strategy columns
        """
        results = self.generate_signals(df, selected_strategies)
        
        if not results:
            return df
        
        # Initialize consensus columns
        consensus_df = df.copy()
        consensus_df['Consensus_Signal'] = 'HOLD'
        consensus_df['Consensus_Confidence'] = 0.0
        consensus_df['Signal_Strength'] = 0.0
        consensus_df['Buy_Votes'] = 0
        consensus_df['Sell_Votes'] = 0
        consensus_df['Hold_Votes'] = 0
        
        # Add individual strategy columns
        for strategy_name, strategy_result in results.items():
            safe_name = strategy_name.replace(' ', '_').replace('-', '_')
            consensus_df[f'{safe_name}_Signal'] = strategy_result['Signal']
            consensus_df[f'{safe_name}_Confidence'] = strategy_result['Confidence']
        
        # Calculate consensus for each row
        for i in range(len(consensus_df)):
            buy_votes = 0
            sell_votes = 0
            hold_votes = 0
            buy_confidences = []
            sell_confidences = []
            
            for strategy_name, strategy_result in results.items():
                signal = strategy_result['Signal'].iloc[i]
                confidence = strategy_result['Confidence'].iloc[i]
                
                if signal == 'BUY':
                    buy_votes += 1
                    buy_confidences.append(confidence)
                elif signal == 'SELL':
                    sell_votes += 1
                    sell_confidences.append(confidence)
                else:
                    hold_votes += 1
            
            total_strategies = len(results)
            consensus_df.loc[consensus_df.index[i], 'Buy_Votes'] = buy_votes
            consensus_df.loc[consensus_df.index[i], 'Sell_Votes'] = sell_votes
            consensus_df.loc[consensus_df.index[i], 'Hold_Votes'] = hold_votes
            
            # Determine consensus signal
            if buy_votes > sell_votes and buy_votes > hold_votes:
                consensus_df.loc[consensus_df.index[i], 'Consensus_Signal'] = 'BUY'
                consensus_df.loc[consensus_df.index[i], 'Consensus_Confidence'] = np.mean(buy_confidences) if buy_confidences else 0
                consensus_df.loc[consensus_df.index[i], 'Signal_Strength'] = (buy_votes / total_strategies) * 100
            elif sell_votes > buy_votes and sell_votes > hold_votes:
                consensus_df.loc[consensus_df.index[i], 'Consensus_Signal'] = 'SELL'
                consensus_df.loc[consensus_df.index[i], 'Consensus_Confidence'] = np.mean(sell_confidences) if sell_confidences else 0
                consensus_df.loc[consensus_df.index[i], 'Signal_Strength'] = (sell_votes / total_strategies) * 100
            else:
                consensus_df.loc[consensus_df.index[i], 'Consensus_Signal'] = 'HOLD'
                consensus_df.loc[consensus_df.index[i], 'Signal_Strength'] = (hold_votes / total_strategies) * 100
        
        return consensus_df
    
    def get_latest_signals(self, df: pd.DataFrame, selected_strategies: List[str] = None, min_confidence: int = 3) -> pd.DataFrame:
        """
        Get only the latest actionable signals
        
        Args:
            df: OHLCV DataFrame with consensus signals
            selected_strategies: List of strategies to use
            min_confidence: Minimum confidence score (1-5)
        
        Returns:
            DataFrame with latest signals filtered by confidence
        """
        consensus_df = self.create_consensus_signal(df, selected_strategies)
        
        # Filter for actionable signals
        latest = consensus_df.iloc[-1]
        
        if (latest['Consensus_Signal'] in ['BUY', 'SELL'] and 
            latest['Consensus_Confidence'] >= min_confidence):
            
            signal_data = {
                'Timestamp': latest.name if hasattr(latest.name, 'strftime') else str(latest.name),
                'Signal': latest['Consensus_Signal'],
                'Confidence': f"{latest['Consensus_Confidence']:.1f}/5.0",
                'Signal_Strength': f"{latest['Signal_Strength']:.0f}%",
                'Buy_Votes': int(latest['Buy_Votes']),
                'Sell_Votes': int(latest['Sell_Votes']),
                'Close_Price': latest['Close']
            }
            
            return pd.DataFrame([signal_data])
        
        return pd.DataFrame()
    
    def backtest_strategy(self, df: pd.DataFrame, strategy_name: str) -> Dict:
        """
        Simple backtest for a single strategy
        
        Returns:
            Dictionary with performance metrics
        """
        if strategy_name not in self.strategies:
            return {}
        
        strategy_func = self.strategies[strategy_name]
        result = strategy_func(df.copy())
        
        # Calculate basic metrics
        buy_signals = result[result['Signal'] == 'BUY']
        sell_signals = result[result['Signal'] == 'SELL']
        
        total_signals = len(buy_signals) + len(sell_signals)
        avg_confidence = result[result['Signal'].isin(['BUY', 'SELL'])]['Confidence'].mean()
        
        metrics = {
            'Total_Signals': total_signals,
            'Buy_Signals': len(buy_signals),
            'Sell_Signals': len(sell_signals),
            'Avg_Confidence': round(avg_confidence, 2) if not np.isnan(avg_confidence) else 0,
            'High_Confidence_Signals': len(result[result['Confidence'] >= 4])
        }
        
        return metrics
