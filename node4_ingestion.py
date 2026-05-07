"""
node4_ingestion.py — NODE 4: The Firehose
==========================================
Runs in a dedicated child process. Opens the Shoonya WebSocket using headless
pyotp login. On every incoming tick, extracts (ts, lp, v) and places a minimal
dict into the shared multiprocessing.Queue with zero computation.

Intended to be spawned by main.py:
    p = Process(target=ingestion_process, args=(queue,))
"""

import logging
import os
import time
from multiprocessing import Queue
from pathlib import Path

import pyotp
from dotenv import load_dotenv

logger = logging.getLogger("node4.ingestion")

# ---------------------------------------------------------------------------
# Shoonya API — optional import guard
# ---------------------------------------------------------------------------
try:
    from NorenRestApiPy.NorenApi import NorenApi  # type: ignore
    NOREN_AVAILABLE = True
except ImportError:
    NOREN_AVAILABLE = False
    NorenApi = object  # allow class definition to parse

_ENV_PATH = Path(__file__).resolve().parent / "shoonya.env"


# ---------------------------------------------------------------------------
# Helper: TOTP / static PIN
# ---------------------------------------------------------------------------
def _get_totp(secret: str) -> str:
    clean = secret.replace("-", "").replace(" ", "").strip()
    return clean if clean.isdigit() else pyotp.TOTP(clean.upper()).now()


# ---------------------------------------------------------------------------
# Ingestion worker class
# ---------------------------------------------------------------------------
class _IngestionWorker(NorenApi):  # type: ignore[misc]
    """
    Subclasses NorenApi so we can override the WebSocket callback to push
    raw ticks straight into the Queue with no processing.
    """

    def __init__(self, queue: Queue) -> None:
        if not NOREN_AVAILABLE:
            raise RuntimeError("NorenRestApiPy is not installed.")
        super().__init__(
            host="https://api.shoonya.com/NorenWClientTP/",
            websocket="wss://api.shoonya.com/NorenWSTP/",
        )
        self._queue = queue
        self._token_map: dict = {}   # symbol -> scrip token
        self._sub_list: list = []

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login_headless(self) -> bool:
        load_dotenv(dotenv_path=_ENV_PATH, override=True)

        user_id      = os.getenv("SHOONYA_USER_ID", "")
        password     = os.getenv("SHOONYA_PASSWORD", "")
        totp_secret  = os.getenv("SHOONYA_TOTP_SECRET", "")
        vendor_code  = os.getenv("SHOONYA_VENDOR_CODE", "")
        api_secret   = os.getenv("SHOONYA_API_SECRET", "")
        imei         = os.getenv("SHOONYA_IMEI", "")

        missing = [k for k, v in [
            ("SHOONYA_USER_ID", user_id), ("SHOONYA_PASSWORD", password),
            ("SHOONYA_TOTP_SECRET", totp_secret), ("SHOONYA_VENDOR_CODE", vendor_code),
            ("SHOONYA_API_SECRET", api_secret), ("SHOONYA_IMEI", imei),
        ] if not v]

        if missing:
            logger.error("[NODE4] Missing env vars: %s", ", ".join(missing))
            return False

        try:
            ret = super().login(
                userid=user_id,
                password=password,
                twoFA=_get_totp(totp_secret),
                vendor_code=vendor_code,
                api_secret=api_secret,
                imei=imei,
            )
            if ret is None or ret.get("stat") != "Ok":
                logger.error("[NODE4] Login failed: %s", ret)
                return False
            logger.info("[NODE4] Login OK — user %s", user_id)
            return True
        except Exception as exc:
            logger.exception("[NODE4] Login exception: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------
    def resolve_tokens(self, symbols: list[str], exchange: str = "NSE") -> None:
        for sym in symbols:
            try:
                resp = self.searchscrip(exchange=exchange, searchtext=sym)
                if resp and resp.get("stat") == "Ok":
                    values = resp.get("values", [])
                    token = next(
                        (v.get("token") for v in values if v.get("tsym") == sym),
                        values[0].get("token") if values else None,
                    )
                    if token:
                        self._token_map[sym] = token
                        logger.debug("[NODE4] %s → token %s", sym, token)
                    else:
                        logger.warning("[NODE4] No token for %s", sym)
                else:
                    logger.warning("[NODE4] searchscrip failed for %s: %s", sym, resp)
            except Exception as exc:
                logger.warning("[NODE4] Token resolution error %s: %s", sym, exc)

    # ------------------------------------------------------------------
    # WebSocket open
    # ------------------------------------------------------------------
    def start_feed(self) -> None:
        self._sub_list = [
            f"NSE|{token}"
            for token in self._token_map.values()
            if token
        ]
        if not self._sub_list:
            logger.error("[NODE4] No tokens to subscribe.")
            return

        logger.info("[NODE4] Opening WebSocket for %d symbols…", len(self._sub_list))
        super().start_websocket(
            subscribe_callback=self._on_feed,
            order_update_callback=lambda _: None,
            socket_open_callback=self._on_open,
            socket_close_callback=self._on_close,
            socket_error_callback=self._on_error,
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _on_open(self) -> None:
        logger.info("[NODE4] WebSocket connected. Subscribing…")
        if self._sub_list:
            self.subscribe(self._sub_list)

    def _on_close(self) -> None:
        logger.warning("[NODE4] WebSocket closed. Retrying in 5 s…")
        time.sleep(5)
        self._reconnect()

    def _on_error(self, err: object) -> None:
        logger.error("[NODE4] WebSocket error: %s", err)

    def _on_feed(self, tick: dict) -> None:
        """
        HOT PATH — zero computation.
        Extract (ts, lp, v) and push straight into the Queue.
        """
        if not isinstance(tick, dict):
            return

        ts = tick.get("ts") or tick.get("tk")   # trading symbol or token
        lp = tick.get("lp")                      # last traded price
        v  = tick.get("v")                       # volume

        if ts is None or lp is None:
            return

        # Reverse-lookup symbol name from token when ts is a token id
        sym = self._token_map_reverse().get(str(ts), str(ts))

        self._queue.put_nowait({
            "symbol": sym,
            "lp": float(lp),
            "v":  int(v) if v is not None else 0,
        })

    def _token_map_reverse(self) -> dict:
        """Lazy-built reverse map  token-str → symbol."""
        if not hasattr(self, "_rev_map") or len(self._rev_map) != len(self._token_map):
            self._rev_map = {str(v): k for k, v in self._token_map.items()}
        return self._rev_map

    def _reconnect(self) -> None:
        logger.info("[NODE4] Reconnecting…")
        if self.login_headless():
            self.start_feed()
        else:
            logger.error("[NODE4] Reconnect login failed.")


# ---------------------------------------------------------------------------
# Process entry-point (called by main.py)
# ---------------------------------------------------------------------------
def ingestion_process(queue: Queue, symbols: list[str]) -> None:
    """
    Target function for multiprocessing.Process.
    Blocks indefinitely keeping the WebSocket feed alive.
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not NOREN_AVAILABLE:
        logger.error("[NODE4] NorenRestApiPy not installed. Ingestion process exiting.")
        return

    worker = _IngestionWorker(queue)

    if not worker.login_headless():
        logger.error("[NODE4] Headless login failed. Exiting.")
        return

    worker.resolve_tokens(symbols)
    worker.start_feed()

    # Keep process alive — the WebSocket runs on a background thread inside NorenApi
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("[NODE4] Shutting down.")
