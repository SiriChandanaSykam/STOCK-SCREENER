"""
main.py — Quantedge V2 Backend Entry Point
==========================================
Wires Nodes 4, 5, and 6 into a multi-process architecture that bypasses the GIL:

  Process A  (Node 4): Shoonya WebSocket ingestion  → pushes ticks to Queue
  Process B  (Node 5): Quantitative core             → drains Queue, computes RSI,
                                                       writes to Manager().dict()
  Process C  (Node 6): FastAPI / uvicorn gateway     → reads Manager().dict(),
                                                       serves WS + REST

Usage:
    python main.py

Requirements (install once):
    pip install fastapi uvicorn[standard] numpy pyotp python-dotenv NorenRestApiPy
"""

import logging
import multiprocessing
import sys
import time
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import SYMBOLS  # NSE symbols list from existing config.py

from node4_ingestion import ingestion_process
from node5_quant_core import quant_process
from node6_api_gateway import gateway_process

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def main() -> None:
    # Required for Windows multiprocessing with 'spawn' start method
    multiprocessing.freeze_support()

    # ----------------------------------------------------------------
    # Shared IPC primitives
    # ----------------------------------------------------------------
    tick_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=10_000)

    # Manager dict is shared across processes via a proxy
    mp_manager = multiprocessing.Manager()
    shared_state: dict = mp_manager.dict()

    # ----------------------------------------------------------------
    # Spawn the three worker processes
    # ----------------------------------------------------------------
    processes = [
        multiprocessing.Process(
            target=ingestion_process,
            args=(tick_queue, list(SYMBOLS)),
            name="Node4-Ingestion",
            daemon=True,
        ),
        multiprocessing.Process(
            target=quant_process,
            args=(tick_queue, shared_state),
            name="Node5-QuantCore",
            daemon=True,
        ),
        multiprocessing.Process(
            target=gateway_process,
            args=(shared_state,),
            name="Node6-APIGateway",
            daemon=False,   # keep alive as the main server process
        ),
    ]

    logger.info("═" * 55)
    logger.info("  QUANTEDGE V2 — Starting %d nodes", len(processes))
    logger.info("═" * 55)

    for p in processes:
        p.start()
        logger.info("  ✓ Started %-20s  PID %d", p.name, p.pid)

    logger.info("  WebSocket  : ws://localhost:8000/ws/live_feed")
    logger.info("  REST POST  : http://localhost:8000/api/execute_trade")
    logger.info("  Health     : http://localhost:8000/health")
    logger.info("═" * 55)

    # ----------------------------------------------------------------
    # Supervisor loop — restart crashed daemon processes
    # ----------------------------------------------------------------
    try:
        while True:
            for p in processes:
                if not p.is_alive() and p.daemon:
                    logger.warning(
                        "  ⚠ Process %s (PID %d) died — restarting…",
                        p.name, p.pid,
                    )
                    # Restart the dead process
                    new_p = multiprocessing.Process(
                        target=p._target,
                        args=p._args,
                        name=p.name,
                        daemon=p.daemon,
                    )
                    new_p.start()
                    processes[processes.index(p)] = new_p
                    logger.info("  ✓ Restarted %s  PID %d", new_p.name, new_p.pid)

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("\n  Shutdown signal received. Terminating all nodes…")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=3)
        mp_manager.shutdown()
        logger.info("  All nodes stopped. Goodbye.")


if __name__ == "__main__":
    main()
