"""
node6_api_gateway.py — NODE 6: FastAPI Middleware Gateway
=========================================================
Reads from the multiprocessing.Manager().dict() updated by Node 5 and serves it
over two endpoints:

  WS  ws://localhost:8000/ws/live_feed   — broadcasts full symbol dict to all
                                           connected frontend clients every 250 ms
  POST /api/execute_trade                — receives trade payload, logs it, and
                                           returns a RISK GATE PASSED ack

CORS is fully open so the React frontend on any port can connect.

This module exposes `build_app(shared_state)` which main.py calls to create
the FastAPI app, then runs it with uvicorn.
"""

import asyncio
import json
import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("node6.api_gateway")

# How often (seconds) the WebSocket loop pushes state to clients
BROADCAST_INTERVAL = 0.25


# ---------------------------------------------------------------------------
# Pydantic model for trade payload
# ---------------------------------------------------------------------------
class TradePayload(BaseModel):
    symbol:      str
    order_type:  str
    quantity:    int
    limit_price: float
    gtt_stop_loss: float


# ---------------------------------------------------------------------------
# Connection manager — tracks all active WebSocket clients
# ---------------------------------------------------------------------------
class _ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("[NODE6] Client connected. Total: %d", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        self._active = [c for c in self._active if c is not ws]
        logger.info("[NODE6] Client disconnected. Total: %d", len(self._active))

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for ws in self._active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def build_app(shared_state: Any) -> FastAPI:
    """
    Creates and wires the FastAPI application.

    Args:
        shared_state: multiprocessing.Manager().dict() written by Node 5.
                      Keys = symbols, values = { symbol, cmp, volume, rsi, ema }
    """
    app = FastAPI(title="Quantedge V2 — API Gateway", version="2.0.0")

    # Full CORS — allow all origins so Vite dev server (any port) can connect
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    manager = _ConnectionManager()

    # ----------------------------------------------------------------
    # WebSocket — ws://localhost:8000/ws/live_feed
    # ----------------------------------------------------------------
    @app.websocket("/ws/live_feed")
    async def live_feed(ws: WebSocket):
        await manager.connect(ws)
        try:
            while True:
                # Snapshot shared state and serialise to JSON array
                snapshot = list(shared_state.values())
                if snapshot:
                    try:
                        payload = json.dumps(snapshot)
                        await manager.broadcast(payload)
                    except Exception as exc:
                        logger.warning("[NODE6] Broadcast error: %s", exc)

                await asyncio.sleep(BROADCAST_INTERVAL)

        except WebSocketDisconnect:
            manager.disconnect(ws)
        except Exception as exc:
            logger.error("[NODE6] WS error: %s", exc)
            manager.disconnect(ws)

    # ----------------------------------------------------------------
    # REST POST — /api/execute_trade
    # ----------------------------------------------------------------
    @app.post("/api/execute_trade")
    async def execute_trade(payload: TradePayload):
        logger.info(
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  ⚡ RISK GATE PASSED — ORDER RECEIVED\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  Symbol      : %s\n"
            "  Order Type  : %s\n"
            "  Quantity    : %d\n"
            "  Limit Price : ₹%.2f\n"
            "  GTT Stop    : ₹%.2f\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            payload.symbol,
            payload.order_type,
            payload.quantity,
            payload.limit_price,
            payload.gtt_stop_loss,
        )
        return {
            "status":  "RISK GATE PASSED",
            "symbol":  payload.symbol,
            "message": f"Order for {payload.quantity} × {payload.symbol} @ ₹{payload.limit_price:.2f} received.",
        }

    # ----------------------------------------------------------------
    # Health check
    # ----------------------------------------------------------------
    @app.get("/health")
    async def health():
        return {
            "status":       "ok",
            "symbols_live": len(shared_state),
        }

    return app


# ---------------------------------------------------------------------------
# Process entry-point (called by main.py)
# ---------------------------------------------------------------------------
def gateway_process(shared_state: Any, host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Target function for multiprocessing.Process.
    Creates the FastAPI app and runs uvicorn synchronously in this process.
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = build_app(shared_state)
    logger.info("[NODE6] Starting uvicorn on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
