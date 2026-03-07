# data_ingestion.py — Shoonya login + WebSocket live tick handler

import os
import logging
import threading
import collections
import time

import pyotp
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import of Shoonya API so the app loads even without credentials
# ---------------------------------------------------------------------------
try:
    from NorenRestApiPy.NorenApi import NorenApi

    class ShoonyaApiPy(NorenApi):
        def __init__(self):
            super().__init__(
                host="https://api.shoonya.com/NorenWClientTP/",
                websocket="wss://api.shoonya.com/NorenWSTP/"
            )

    api = ShoonyaApiPy()
    SHOONYA_AVAILABLE = True
except ImportError:
    logger.warning("NorenRestApiPy not installed. Running in DEMO mode.")
    api = None
    SHOONYA_AVAILABLE = False

from config import SYMBOLS, DEQUE_MAXLEN, EXCHANGE  # noqa: E402

# ---------------------------------------------------------------------------
# In-memory tick store  {symbol: deque(maxlen=390)}
# ---------------------------------------------------------------------------
tick_store = {sym: collections.deque(maxlen=DEQUE_MAXLEN) for sym in SYMBOLS}
websocket_status = {"connected": False}

_login_lock = threading.Lock()
_is_logged_in = False


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def login() -> bool:
    global _is_logged_in
    if not SHOONYA_AVAILABLE:
        logger.warning("Shoonya API unavailable — skipping login.")
        return False

    with _login_lock:
        if _is_logged_in:
            return True

        user_id = os.getenv("SHOONYA_USER_ID")
        password = os.getenv("SHOONYA_PASSWORD")
        totp_secret = os.getenv("SHOONYA_TOTP_SECRET")
        vendor_code = os.getenv("SHOONYA_VENDOR_CODE")
        api_secret = os.getenv("SHOONYA_API_SECRET")
        imei = os.getenv("SHOONYA_IMEI")

        if not all([user_id, password, totp_secret, vendor_code, api_secret, imei]):
            logger.error(
                "Missing Shoonya credentials. "
                "Please fill in your .env file before starting."
            )
            return False

        totp = pyotp.TOTP(totp_secret).now()
        try:
            ret = api.login(
                userid=user_id,
                password=password,
                twoFA=totp,
                vendor_code=vendor_code,
                api_secret=api_secret,
                imei=imei
            )
        except Exception as exc:
            logger.error(f"Login exception: {exc}")
            return False

        if ret and ret.get("stat") == "Ok":
            logger.info("✅ Shoonya login successful.")
            _is_logged_in = True
            return True

        logger.error(f"Shoonya login failed: {ret}")
        return False


# ---------------------------------------------------------------------------
# WebSocket callbacks
# ---------------------------------------------------------------------------
def _on_open():
    websocket_status["connected"] = True
    logger.info("WebSocket opened — subscribing to symbols.")
    token_list = [{"exch": EXCHANGE, "token": sym} for sym in SYMBOLS]
    api.subscribe(token_list)


def _on_message(tick):
    try:
        sym = tick.get("tsym") or tick.get("tk")
        ltp = float(tick.get("lp") or tick.get("ltp") or 0)
        vol = int(tick.get("v") or tick.get("vol") or 0)
        ts = tick.get("ft") or time.time()
        if sym and sym in tick_store and ltp > 0:
            tick_store[sym].append({"ltp": ltp, "vol": vol, "ts": ts})
    except Exception as exc:
        logger.warning(f"Tick parse error: {exc}")


def _on_error(err):
    websocket_status["connected"] = False
    logger.error(f"WebSocket error: {err}")


def _on_close():
    websocket_status["connected"] = False
    logger.warning("WebSocket closed — reconnecting in 5 s…")
    time.sleep(5)
    _reconnect_websocket()


# ---------------------------------------------------------------------------
# Start WebSocket
# ---------------------------------------------------------------------------
_MAX_RETRIES = 10


def _reconnect_websocket(retries: int = 0):
    """Retry WebSocket connection with a bounded retry count."""
    if retries >= _MAX_RETRIES:
        logger.error("WebSocket max retries reached. Giving up.")
        return
    try:
        api.start_websocket(
            order_update_callback=None,
            subscribe_callback=_on_message,
            socket_open_callback=_on_open,
            socket_close_callback=_on_close,
            socket_error_callback=_on_error
        )
    except Exception as exc:
        logger.error(f"WebSocket start failed: {exc}. Retrying in 10 s… (attempt {retries + 1})")
        time.sleep(10)
        _reconnect_websocket(retries + 1)


def start_websocket():
    _reconnect_websocket()


def start_streaming():
    if not login():
        logger.warning(
            "Streaming not started — credentials missing or login failed. "
            "Add credentials to .env and restart."
        )
        return
    t = threading.Thread(target=start_websocket, daemon=True)
    t.start()
    logger.info("WebSocket streaming thread started.")
