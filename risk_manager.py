"""
risk_manager.py — Stop-loss, take-profit, and R:R calculation.

For every stock that passes the screener filter this module computes:
  * stop_loss           = current_price × (1 − STOP_LOSS_PCT)
  * take_profit         = current_price × (1 + TAKE_PROFIT_PCT)
  * risk_reward         = (take_profit − price) / (price − stop_loss)
  * volume_surge_multiple  = today's cum. volume / 20-day average volume
  * distance_from_52w_high = (current_price / 52w_high) × 100
"""

import logging
from typing import Any, Dict, List

from config import STOP_LOSS_PCT, TAKE_PROFIT_PCT

logger = logging.getLogger(__name__)


def calculate_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Augment a single screener-result dict with risk management fields.

    Parameters
    ----------
    row : dict
        A result dict produced by screener_engine._screen_symbol.
        Must contain at least: ltp, avg_vol_20, cum_vol, high52.

    Returns
    -------
    dict
        The same dict with stop_loss, take_profit, risk_reward,
        volume_surge_multiple, and distance_from_52w_high added.
    """
    price = float(row.get("ltp", 0.0))
    avg_vol_20 = float(row.get("avg_vol_20") or 0.0)
    cum_vol = float(row.get("cum_vol") or 0.0)
    high52 = float(row.get("high52") or 0.0)

    if price <= 0:
        logger.warning("Skipping risk calculation for %s — invalid price %.4f",
                       row.get("symbol", "?"), price)
        return row

    stop_loss = round(price * (1.0 - STOP_LOSS_PCT), 2)
    take_profit = round(price * (1.0 + TAKE_PROFIT_PCT), 2)

    reward = take_profit - price
    risk = price - stop_loss

    # Guard against zero risk (should never happen with a fixed pct, but be safe)
    risk_reward = round(reward / risk, 2) if risk > 0 else 0.0

    volume_surge_multiple = (
        round(cum_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0.0
    )

    distance_from_52w_high = (
        round((price / high52) * 100, 2) if high52 > 0 else 0.0
    )

    row.update({
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward": risk_reward,
        "volume_surge_multiple": volume_surge_multiple,
        "distance_from_52w_high": distance_from_52w_high,
    })

    return row


def enrich_results(screener_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply calculate_risk to every item in *screener_results* and return
    the enriched list.
    """
    enriched = []
    for row in screener_results:
        try:
            enriched.append(calculate_risk(row))
        except Exception as exc:
            logger.error("Risk calculation failed for %s: %s",
                         row.get("symbol", "?"), exc)
            enriched.append(row)
    return enriched
