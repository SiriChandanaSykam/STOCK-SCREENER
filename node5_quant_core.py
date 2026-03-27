"""
node5_quant_core.py — NODE 5: The Quantitative Brain
=====================================================
Runs in a dedicated child process. Continuously drains the multiprocessing.Queue
populated by Node 4. Maintains a per-symbol deque of the last 50 price ticks.
Computes a 14-period RSI using numpy and writes results into a
multiprocessing.Manager().dict() that Node 6 reads from.

Intended to be spawned by main.py:
    p = Process(target=quant_process, args=(queue, shared_state))
"""

import logging
import time
from collections import deque
from multiprocessing import Queue
from typing import Any

import numpy as np

logger = logging.getLogger("node5.quant_core")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TICK_HISTORY   = 50    # deque max capacity per symbol
RSI_PERIOD     = 14    # standard Wilder RSI


# ---------------------------------------------------------------------------
# RSI calculation (numpy, no pandas dependency)
# ---------------------------------------------------------------------------
def _compute_rsi(prices: list[float], period: int = RSI_PERIOD) -> float | None:
    """
    Standard Wilder RSI using Exponential Moving Average of gains/losses.
    Returns None when not enough data.
    """
    if len(prices) < period + 1:
        return None

    arr    = np.array(prices, dtype=np.float64)
    deltas = np.diff(arr)

    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Seed: simple mean of first `period` bars
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()

    # Wilder smoothing for remaining bars
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0

    rs  = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)


# ---------------------------------------------------------------------------
# Process entry-point (called by main.py)
# ---------------------------------------------------------------------------
def quant_process(queue: Queue, shared_state: Any) -> None:
    """
    Target function for multiprocessing.Process.

    Args:
        queue:        multiprocessing.Queue filled by Node 4.
        shared_state: multiprocessing.Manager().dict() shared with Node 6.
                      Schema per symbol:
                        {
                          "symbol": str,
                          "cmp":    float,
                          "volume": int,
                          "rsi":    float | None,
                          "ema":    float | None,   # placeholder for future
                        }
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # In-memory per-symbol price history  symbol -> deque[float]
    histories: dict[str, deque] = {}

    logger.info("[NODE5] Quant core started. Waiting for ticks…")

    while True:
        try:
            # Block with 1 s timeout so the process stays responsive to signals
            tick = queue.get(timeout=1.0)
        except Exception:
            # Timeout or Empty — loop back
            continue

        symbol = tick.get("symbol")
        lp     = tick.get("lp")
        vol    = tick.get("v", 0)

        if not symbol or lp is None:
            continue

        # Maintain rolling price history
        if symbol not in histories:
            histories[symbol] = deque(maxlen=TICK_HISTORY)

        histories[symbol].append(float(lp))

        # Compute RSI
        prices = list(histories[symbol])
        rsi    = _compute_rsi(prices)

        # Write to shared state (atomic replace of the symbol's entry)
        shared_state[symbol] = {
            "symbol": symbol,
            "cmp":    float(lp),
            "volume": int(vol),
            "rsi":    rsi,
            "ema":    None,   # reserved for future EMA node
        }

        logger.debug(
            "[NODE5] %s  CMP=%.2f  VOL=%d  RSI=%s",
            symbol, lp, vol,
            f"{rsi:.2f}" if rsi is not None else "N/A (building…)",
        )
