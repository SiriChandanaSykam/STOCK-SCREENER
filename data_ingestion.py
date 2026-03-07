# data_ingestion.py — Shoonya login + WebSocket live tick handler

import os
import logging
import threading
import collections
import time
import pyotp
from dotenv import load_dotenv
from NorenRestApiPy.NorenApi import NorenApi

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from config import SYMBOLS, DEQUE_MAXLEN, EXCHANGE  # noqa: E402


# Shoonya API subclass
class ShoonyaApiPy(NorenApi):
    def __init__(self):
        super().__init__(
            host="https://api.shoonya.com/NorenWClientTP/",
            websocket="wss://api.shoonya.com/NorenWSTP/"
        )


api = ShoonyaApiPy()
_login_lock = threading.Lock()
_is_logged_in = False

# In-memory tick store: {symbol: deque(maxlen=390)}
tick_store = {sym: collections.deque(maxlen=DEQUE_MAXLEN) for sym in SYMBOLS}
websocket_status = {"connected": False}


def login():
    global _is_logged_in
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
            raise EnvironmentError("Missing Shoonya credentials in .env file.")

        totp = pyotp.TOTP(totp_secret).now()
        ret = api.login(
            userid=user_id,
            password=password,
            twoFA=totp,
            vendor_code=vendor_code,
            api_secret=api_secret,
            imei=imei
        )
        if ret and ret.get("stat") == "Ok":
            logger.info("Shoonya login successful.")
            _is_logged_in = True
            return True
        else:
            logger.error(f"Shoonya login failed: {ret}")
            return False


def _on_open():
    websocket_status["connected"] = True
    logger.info("WebSocket opened.")
    # Subscribe to all symbols
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
    except Exception as e:
        logger.warning(f"Tick parse error: {e}")


def _on_error(err):
    websocket_status["connected"] = False
    logger.error(f"WebSocket error: {err}")


def _on_close():
    websocket_status["connected"] = False
    logger.warning("WebSocket closed. Reconnecting in 5s...")
    time.sleep(5)
    t = threading.Thread(target=start_websocket, daemon=True)
    t.start()


def start_websocket(max_retries: int = 10):
    retries = 0
    while retries < max_retries:
        try:
            api.start_websocket(
                order_update_callback=None,
                subscribe_callback=_on_message,
                socket_open_callback=_on_open,
                socket_close_callback=_on_close,
                socket_error_callback=_on_error
            )
            return  # Exits cleanly if the WebSocket completes without error
        except Exception as e:
            retries += 1
            logger.error(f"WebSocket start failed (attempt {retries}/{max_retries}): {e}. Retrying in 10s...")
            time.sleep(10)
    logger.error("Max WebSocket retries reached. Giving up.")


def start_streaming():
    if not login():
        raise RuntimeError("Cannot start streaming: login failed.")
    t = threading.Thread(target=start_websocket, daemon=True)
    t.start()
    logger.info("WebSocket streaming thread started.")
