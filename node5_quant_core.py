"""
node5_quant_core.py - NODE 5: The quantitative brain.

Runs in a dedicated child process. Continuously drains the multiprocessing
Queue populated by Node 4, maintains rolling per-symbol price history, and
writes RSI/EMA state into a multiprocessing.Manager().dict() for Node 6.
"""

import logging
from collections import deque
from multiprocessing import Queue
from typing import Any

import numpy as np

logger = logging.getLogger("node5.quant_core")

TICK_HISTORY = 200
RSI_PERIOD = 14
EMA50_PERIOD = 50
EMA200_PERIOD = 200


def _compute_rsi(prices: list[float], period: int = RSI_PERIOD) -> float | None:
    """
    Standard Wilder RSI using smoothed average gains/losses.
    """
    if len(prices) < period + 1:
        return None

    arr = np.array(prices, dtype=np.float64)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _compute_ema(prices: list[float], period: int) -> float | None:
    """
    Span-based EWM calculation seeded with a simple average.
    """
    if len(prices) < period:
        return None

    alpha = 2.0 / (period + 1.0)
    ema = float(np.mean(prices[:period]))
    for price in prices[period:]:
        ema = (float(price) * alpha) + (ema * (1.0 - alpha))
    return round(ema, 2)


def quant_process(queue: Queue, shared_state: Any) -> None:
    """
    Process entry point used by main.py.

    Shared state schema per symbol:
        {
            "symbol": str,
            "cmp": float,
            "volume": int,
            "rsi": float | None,
            "ema50": float | None,
            "ema200": float | None,
        }
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    histories: dict[str, deque] = {}
    logger.info("[NODE5] Quant core started. Waiting for ticks...")

    while True:
        try:
            tick = queue.get(timeout=1.0)
        except Exception:
            continue

        symbol = tick.get("symbol")
        lp = tick.get("lp")
        vol = tick.get("v", 0)

        if not symbol or lp is None:
            continue

        if symbol not in histories:
            histories[symbol] = deque(maxlen=TICK_HISTORY)

        histories[symbol].append(float(lp))
        prices = list(histories[symbol])
        rsi = _compute_rsi(prices)
        ema50 = _compute_ema(prices, EMA50_PERIOD)
        ema200 = _compute_ema(prices, EMA200_PERIOD)

        shared_state[symbol] = {
            "symbol": symbol,
            "cmp": float(lp),
            "volume": int(vol),
            "rsi": rsi,
            "ema50": ema50,
            "ema200": ema200,
        }

        logger.debug(
            "[NODE5] %s CMP=%.2f VOL=%d RSI=%s EMA50=%s EMA200=%s",
            symbol,
            float(lp),
            int(vol),
            f"{rsi:.2f}" if rsi is not None else "N/A",
            f"{ema50:.2f}" if ema50 is not None else "N/A",
            f"{ema200:.2f}" if ema200 is not None else "N/A",
        )
