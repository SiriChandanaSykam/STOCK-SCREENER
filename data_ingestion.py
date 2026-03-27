"""
data_ingestion.py — Shoonya (Finvasia) login and WebSocket live tick handler.

Responsibilities:
  * Authenticate with the Shoonya API using credentials from .env
  * Open a WebSocket connection and subscribe to live tick data for all
    symbols defined in config.SYMBOLS
  * Maintain per-symbol tick deques (max 390 ticks = one full trading day)
    strictly in memory — no data is written to disk

Usage (standalone test):
  python data_ingestion.py
"""

import logging
import os
import time
from collections import deque
from threading import Lock

import pyotp
from dotenv import load_dotenv
from pathlib import Path

# ---------------------------------------------------------------------------
# Shoonya API import — optional at import time so that the module can be
# imported even when NorenRestApiPy is not installed (e.g. during linting).
# ---------------------------------------------------------------------------
try:
    from NorenRestApiPy.NorenApi import NorenApi  # type: ignore[import]
    NOREN_AVAILABLE = True
except ImportError:
    NOREN_AVAILABLE = False
    NorenApi = object  # fallback so the class definition below still parses

from config import SYMBOLS, NSE_EXCHANGE

# ---------------------------------------------------------------------------
# Dynamic symbol loader — reads target_list.txt written by premarket_filter.py
# Falls back to config.SYMBOLS when the file is absent.
# ---------------------------------------------------------------------------
_TARGET_LIST_PATH = Path(__file__).resolve().parent / "target_list.txt"


def load_target_list() -> list[str]:
    """
    Read target_list.txt (one 'NSE|SYMBOL-EQ' entry per line).
    Strip the 'NSE|' prefix and '-EQ' suffix so the raw symbol name
    (e.g. 'HAPPSTMNDS') is returned — matching the format expected by
    searchscrip() and the existing tick_data store.

    Falls back to list(SYMBOLS) from config.py if the file does not exist.
    """
    if not _TARGET_LIST_PATH.exists():
        logger.info(
            "target_list.txt not found — falling back to config.SYMBOLS (%d symbols)",
            len(SYMBOLS),
        )
        return list(SYMBOLS)

    symbols: list[str] = []
    with open(_TARGET_LIST_PATH, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            # Strip exchange prefix and equity suffix
            sym = raw.removeprefix("NSE|").removesuffix("-EQ")
            if sym:
                symbols.append(sym)

    if not symbols:
        logger.warning("target_list.txt is empty — falling back to config.SYMBOLS")
        return list(SYMBOLS)

    logger.info("Loaded %d symbols from target_list.txt", len(symbols))
    return symbols

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-memory tick store
# key  : symbol string (e.g. "YESBANK")
# value: deque of dicts {"ltp": float, "vol": int, "ts": float}
# ---------------------------------------------------------------------------
MAX_TICKS = 390  # one full trading day of 1-min bars
_tick_lock = Lock()

# Resolve symbol list once at module import time
ACTIVE_SYMBOLS: list[str] = load_target_list()

tick_data: dict = {sym: deque(maxlen=MAX_TICKS) for sym in ACTIVE_SYMBOLS}

# WebSocket connection status (True = connected)
ws_connected: bool = False


# ---------------------------------------------------------------------------
# Helper: generate TOTP from secret
# ---------------------------------------------------------------------------
def _get_totp(secret: str) -> str:
    """Return the 2FA code.
    If the secret is purely numeric (static PIN / DOB), return it as-is.
    Otherwise treat it as a base32 TOTP secret and generate a live OTP.
    """
    clean = secret.replace("-", "").replace(" ", "").strip()
    if clean.isdigit():
        # Static PIN (e.g. date of birth DDMMYYYY or a fixed OTP PIN)
        return clean
    return pyotp.TOTP(clean.upper()).now()


# ---------------------------------------------------------------------------
# Shoonya API wrapper
# ---------------------------------------------------------------------------
class ShoonyaDataIngestor(NorenApi):  # type: ignore[misc]
    """
    Subclass of NorenApi that wires WebSocket callbacks to the shared
    in-memory tick store.
    """

    def __init__(self) -> None:
        if not NOREN_AVAILABLE:
            raise RuntimeError(
                "NorenRestApiPy is not installed. "
                "Run: pip install NorenRestApiPy"
            )
        super().__init__(
            host="https://api.shoonya.com/NorenWClientTP/",
            websocket="wss://api.shoonya.com/NorenWSTP/",
        )
        self._token_map: dict = {}  # symbol -> scrip token

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def shoonya_login(self) -> bool:
        """
        Authenticate using credentials loaded from shoonya.env.
        Returns True on success, False on failure.
        """
        _env_path = Path(__file__).resolve().parent / "shoonya.env"
        load_dotenv(dotenv_path=_env_path, override=True)

        user_id = os.getenv("SHOONYA_USER_ID", "")
        password = os.getenv("SHOONYA_PASSWORD", "")
        totp_secret = os.getenv("SHOONYA_TOTP_SECRET", "")
        vendor_code = os.getenv("SHOONYA_VENDOR_CODE", "")
        api_secret = os.getenv("SHOONYA_API_SECRET", "")
        imei = os.getenv("SHOONYA_IMEI", "")

        missing = [
            name for name, val in [
                ("SHOONYA_USER_ID", user_id),
                ("SHOONYA_PASSWORD", password),
                ("SHOONYA_TOTP_SECRET", totp_secret),
                ("SHOONYA_VENDOR_CODE", vendor_code),
                ("SHOONYA_API_SECRET", api_secret),
                ("SHOONYA_IMEI", imei),
            ]
            if not val
        ]
        if missing:
            logger.error("Missing .env variables: %s", ", ".join(missing))
            return False

        twoFA = _get_totp(totp_secret)

        try:
            ret = super().login(
                userid=user_id,
                password=password,
                twoFA=twoFA,
                vendor_code=vendor_code,
                api_secret=api_secret,
                imei=imei,
            )
            if ret is None or ret.get("stat") != "Ok":
                logger.error("Shoonya login failed: %s", ret)
                return False

            logger.info("Shoonya login successful for user %s", user_id)
            return True

        except Exception as exc:
            logger.exception("Exception during Shoonya login: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------
    def resolve_tokens(self) -> None:
        """
        Fetch the scrip token for every symbol in ACTIVE_SYMBOLS.
        Token is needed to subscribe via WebSocket.
        """
        for sym in ACTIVE_SYMBOLS:
            try:
                resp = self.searchscrip(exchange=NSE_EXCHANGE, searchtext=sym)
                if resp and resp.get("stat") == "Ok":
                    values = resp.get("values", [])
                    if values:
                        # Pick the equity token (tsym matches symbol exactly)
                        for item in values:
                            if item.get("tsym") == sym:
                                self._token_map[sym] = item.get("token")
                                break
                        else:
                            # Fallback: take first result
                            self._token_map[sym] = values[0].get("token")
                        logger.debug("Resolved %s → token %s", sym, self._token_map[sym])
                else:
                    logger.warning("Could not resolve token for %s: %s", sym, resp)
            except Exception as exc:
                logger.warning("Token resolution error for %s: %s", sym, exc)

    # ------------------------------------------------------------------
    # WebSocket subscription
    # ------------------------------------------------------------------
    def start_websocket(self) -> None:
        """Open the WebSocket and subscribe to all resolved symbol tokens."""
        subscribe_list = [
            f"{NSE_EXCHANGE}|{token}"
            for token in self._token_map.values()
            if token
        ]
        if not subscribe_list:
            logger.error("No tokens available for WebSocket subscription.")
            return

        logger.info("Opening WebSocket for %d symbols…", len(subscribe_list))

        # Call the parent NorenApi.start_websocket with callback arguments
        super().start_websocket(
            subscribe_callback=self._on_tick,
            order_update_callback=self._on_order_update,
            socket_open_callback=self._on_open,
            socket_close_callback=self._on_close,
            socket_error_callback=self._on_error,
        )

        # Subscribe after connection is established — handled in _on_open
        self._subscribe_list = subscribe_list

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------
    def _on_open(self) -> None:
        global ws_connected
        ws_connected = True
        logger.info("WebSocket connected. Subscribing to %d tokens…",
                    len(getattr(self, "_subscribe_list", [])))
        sub_list = getattr(self, "_subscribe_list", [])
        if sub_list:
            self.subscribe(sub_list)

    def _on_close(self) -> None:
        global ws_connected
        ws_connected = False
        logger.warning("WebSocket disconnected. Attempting reconnect in 5 s…")
        time.sleep(5)
        self._reconnect()

    def _on_error(self, error: object) -> None:
        global ws_connected
        ws_connected = False
        logger.error("WebSocket error: %s", error)

    def _on_order_update(self, order: object) -> None:
        """Not used for read-only data ingestion."""
        pass  # intentionally empty

    def _on_tick(self, tick: dict) -> None:
        """
        Called for every incoming tick.  Stores ltp and vol in the
        symbol's deque — no file I/O occurs here.
        """
        if not isinstance(tick, dict):
            return

        token = tick.get("tk")
        ltp_str = tick.get("lp") or tick.get("ltp")
        vol_str = tick.get("v") or tick.get("vol")

        if not token or ltp_str is None:
            return

        # Reverse-lookup symbol from token
        sym = next(
            (s for s, t in self._token_map.items() if str(t) == str(token)),
            None,
        )
        if sym is None:
            return

        try:
            ltp = float(ltp_str)
            vol = int(vol_str) if vol_str is not None else 0
        except (ValueError, TypeError):
            return

        with _tick_lock:
            tick_data[sym].append({"ltp": ltp, "vol": vol, "ts": time.time()})

    # ------------------------------------------------------------------
    # Reconnect logic
    # ------------------------------------------------------------------
    def _reconnect(self) -> None:
        """Re-login and re-open the WebSocket after a disconnection."""
        logger.info("Reconnecting to Shoonya WebSocket…")
        if self.shoonya_login():
            self.start_websocket()
        else:
            logger.error("Reconnect failed: login error.")


# ---------------------------------------------------------------------------
# Convenience accessor used by the screener engine
# ---------------------------------------------------------------------------
def get_latest_tick(symbol: str) -> dict:
    """
    Return the most recent tick dict for *symbol*, or an empty dict if
    no ticks have arrived yet.
    """
    with _tick_lock:
        dq = tick_data.get(symbol)
        if dq:
            return dq[-1]
    return {}


def get_cumulative_volume(symbol: str) -> int:
    """
    Return the current cumulative traded volume for *symbol*.

    Shoonya WebSocket tick data includes a running cumulative traded quantity
    (field 'v') that increases monotonically through the trading session.
    We therefore take the most recent tick's value — which represents the
    total volume traded so far today.
    """
    with _tick_lock:
        dq = tick_data.get(symbol, deque())
        if dq:
            return int(dq[-1]["vol"])
    return 0


# ---------------------------------------------------------------------------
# Standalone entry-point for manual testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not NOREN_AVAILABLE:
        print("NorenRestApiPy is not installed. Install it first.")
    else:
        ingestor = ShoonyaDataIngestor()
        if ingestor.shoonya_login():
            ingestor.resolve_tokens()
            ingestor.start_websocket()
            # Keep the main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down.")
