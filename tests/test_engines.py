import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from screener_engine import (  # noqa: E402
    _screen_btst,
    _screen_kinetic_squeeze,
    _screen_macro_floor,
    _screen_stealth_accumulation,
    _screen_vcp_breakout,
    _screen_vcp_setup,
)


def make_df(ltp=100.0, open_price=98.0, high=101.0, low=97.0):
    rows = 260
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=rows, freq="D"),
        "open": [open_price] * rows,
        "high": [high] * rows,
        "low": [low] * rows,
        "close": [ltp] * rows,
        "volume": [1_000_000] * rows,
    })


def make_indicators(**overrides):
    data = {
        "rsi": 62.0,
        "ema50": 90.0,
        "ema200": 98.0,
        "sma20": 90.0,
        "sma50": 90.0,
        "avg_vol_20": 1_000_000.0,
        "high52": 110.0,
        "high10": 100.0,
        "low10": 95.0,
        "high5": 100.0,
        "low5": 96.0,
        "open_price": 98.0,
        "candle_high": 101.0,
        "candle_low": 97.0,
    }
    data.update(overrides)
    return data


def assert_pass(result, engine):
    assert result is not None
    assert result["engine"] == engine
    assert result["all_pass"] is True
    assert result["rupee_turnover"] > 0
    assert "candle_body_pct" in result
    assert "volume_surge_x" in result


def test_macro_floor_pass_and_fail():
    df = make_df(ltp=105.0, open_price=100.0, high=107.0, low=99.0)
    indicators = make_indicators(
        rsi=65.0,
        ema50=90.0,
        ema200=100.0,
        open_price=100.0,
        candle_high=107.0,
        candle_low=99.0,
    )
    assert_pass(_screen_macro_floor("TEST", df, 2_500_000, indicators), "MACRO_FLOOR")
    assert _screen_macro_floor("TEST", df, 100_000, indicators) is None


def test_kinetic_squeeze_pass_and_fail():
    df = make_df(ltp=105.0, open_price=102.0, high=105.0, low=100.0)
    indicators = make_indicators(
        rsi=70.0,
        ema50=90.0,
        sma20=92.0,
        high10=105.0,
        open_price=102.0,
        candle_high=105.0,
        candle_low=100.0,
    )
    assert_pass(_screen_kinetic_squeeze("TEST", df, 3_000_000, indicators), "KINETIC_SQUEEZE")
    fail = {**indicators, "rsi": 82.0}
    assert _screen_kinetic_squeeze("TEST", df, 3_000_000, fail) is None


def test_stealth_accumulation_pass_and_fail():
    df = make_df(ltp=102.0, open_price=100.0, high=103.0, low=99.0)
    indicators = make_indicators(
        rsi=55.0,
        sma50=90.0,
        high10=105.0,
        low10=96.0,
        open_price=100.0,
        candle_high=103.0,
        candle_low=99.0,
    )
    assert_pass(_screen_stealth_accumulation("TEST", df, 1_600_000, indicators), "STEALTH_ACCUMULATION")
    fail = {**indicators, "high10": 112.0}
    assert _screen_stealth_accumulation("TEST", df, 1_600_000, fail) is None


def test_btst_pass_and_fail():
    df = make_df(ltp=106.0, open_price=100.0, high=106.2, low=99.0)
    indicators = make_indicators(
        rsi=65.0,
        sma20=90.0,
        high52=120.0,
        open_price=100.0,
        candle_high=106.2,
        candle_low=99.0,
    )
    assert_pass(_screen_btst("TEST", df, 3_000_000, indicators), "BTST")
    fail = {**indicators, "rsi": 54.0}
    assert _screen_btst("TEST", df, 3_000_000, fail) is None


def test_vcp_setup_pass_and_fail():
    df = make_df(ltp=100.0, open_price=99.0, high=101.0, low=98.0)
    indicators = make_indicators(
        rsi=58.0,
        avg_vol_20=1_000_000.0,
        high52=104.0,
        high5=100.0,
        low5=96.0,
        open_price=99.0,
        candle_high=101.0,
        candle_low=98.0,
    )
    assert_pass(_screen_vcp_setup("TEST", df, 600_000, indicators), "VCP_SETUP")
    assert _screen_vcp_setup("TEST", df, 900_000, indicators) is None


def test_vcp_breakout_pass_and_fail():
    df = make_df(ltp=100.0, open_price=98.0, high=100.5, low=97.0)
    indicators = make_indicators(
        rsi=66.0,
        avg_vol_20=1_000_000.0,
        high52=104.0,
        high10=101.0,
        open_price=98.0,
        candle_high=100.5,
        candle_low=97.0,
    )
    assert_pass(_screen_vcp_breakout("TEST", df, 2_500_000, indicators), "VCP_BREAKOUT")
    fail = {**indicators, "rsi": 59.0}
    assert _screen_vcp_breakout("TEST", df, 2_500_000, fail) is None
