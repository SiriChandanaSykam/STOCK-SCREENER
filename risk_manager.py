"""
risk_manager.py - Stop-loss, take-profit, and R:R calculations.
"""

import logging
from typing import Any, Dict, List

from config import STOP_LOSS_PCT, TAKE_PROFIT_PCT

logger = logging.getLogger(__name__)

ENGINE_RISK_PARAMETERS = {
    "MACRO_FLOOR": (0.04, 0.15),
    "KINETIC_SQUEEZE": (0.03, 0.12),
    "STEALTH_ACCUMULATION": (0.05, 0.20),
    "BTST": (0.02, 0.06),
    "VCP_SETUP": (0.05, 0.25),
    "VCP_BREAKOUT": (0.03, 0.15),
    "ORIGINAL": (STOP_LOSS_PCT, TAKE_PROFIT_PCT),
}


def _risk_params_for_engine(engine: str) -> tuple[float, float]:
    first_engine = (engine or "ORIGINAL").split(",")[0].strip().upper()
    return ENGINE_RISK_PARAMETERS.get(first_engine, ENGINE_RISK_PARAMETERS["ORIGINAL"])


def calculate_risk(row: Dict[str, Any], engine: str = "ORIGINAL") -> Dict[str, Any]:
    """
    Augment a screener-result dict with risk management fields.
    """
    selected_engine = str(row.get("engine") or engine or "ORIGINAL")
    stop_loss_pct, take_profit_pct = _risk_params_for_engine(selected_engine)

    price = float(row.get("ltp", 0.0))
    avg_vol_20 = float(row.get("avg_vol_20") or 0.0)
    cum_vol = float(row.get("cum_vol") or 0.0)
    high52 = float(row.get("high52") or 0.0)

    if price <= 0:
        logger.warning("Skipping risk calculation for %s - invalid price %.4f", row.get("symbol", "?"), price)
        return row

    stop_loss = round(price * (1.0 - stop_loss_pct), 2)
    take_profit = round(price * (1.0 + take_profit_pct), 2)
    reward = take_profit - price
    risk = price - stop_loss

    row.update({
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward": round(reward / risk, 2) if risk > 0 else 0.0,
        "volume_surge_multiple": round(cum_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0.0,
        "distance_from_52w_high": round((price / high52) * 100, 2) if high52 > 0 else 0.0,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
    })
    return row


def enrich_results(screener_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply calculate_risk to every item in screener_results.
    """
    enriched = []
    for row in screener_results:
        try:
            enriched.append(calculate_risk(row, engine=str(row.get("engine") or "ORIGINAL")))
        except Exception as exc:
            logger.error("Risk calculation failed for %s: %s", row.get("symbol", "?"), exc)
            enriched.append(row)
    return enriched
