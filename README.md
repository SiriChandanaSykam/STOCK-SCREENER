# ⚡ Operation Compound — NSE Micro-Cap Momentum Screener

A production-ready, zero-latency micro-cap momentum screener for the Indian Stock Market (NSE), powered by the [Shoonya by Finvasia](https://shoonya.com/) API with live WebSocket tick streaming.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         app.py (Streamlit UI)                   │
│   Auto-refresh every 30s │ Trade Cards │ Sidebar Session Stats  │
└────────────────┬──────────────────────────┬─────────────────────┘
                 │                          │
        ┌────────▼────────┐      ┌──────────▼──────────┐
        │  screener_engine│      │    risk_manager.py   │
        │  6-layer filter │      │  SL / TP / R:R calc  │
        └────────┬────────┘      └─────────────────────-┘
                 │
     ┌───────────┴────────────┐
     │                        │
┌────▼─────────┐   ┌──────────▼────────┐
│historical_   │   │  data_ingestion.py │
│data.py       │   │  Shoonya WebSocket │
│Seed OHLCV    │   │  Live Tick Store   │
│(daily bars)  │   │  (in-memory deque) │
└──────┬───────┘   └──────────┬─────────┘
       │                      │
       └──────────┬───────────┘
                  │
        ┌─────────▼──────────┐
        │    config.py        │
        │  Symbols / Params   │
        └────────────────────┘
                  │
        ┌─────────▼──────────┐
        │  Shoonya (Finvasia) │
        │  NorenRestApiPy     │
        │  REST + WebSocket   │
        └────────────────────┘
```

### Data flow

1. **Startup** — `load_all_seed_data()` fetches up to 262 days of daily OHLCV bars for every symbol via the Shoonya REST API.
2. **Streaming** — `start_streaming()` opens a persistent WebSocket that pushes live ticks into per-symbol in-memory `deque` objects (`tick_store`).
3. **Screener** — Every 30 s, `run_screener()` merges seed history with the latest live tick, computes RSI(14), EMA(50), 20-day average volume, and 52-week high, then applies 6 simultaneous filters.
4. **Risk** — `apply_risk_management()` appends Stop-Loss, Target, and R:R columns to any passing rows.
5. **UI** — Streamlit renders a live table, trade cards, and sidebar stats before sleeping 30 s and calling `st.rerun()`.

---

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/SiriChandanaSykam/STOCK-SCREENER.git
   cd STOCK-SCREENER
   ```

2. **Set up credentials**

   ```bash
   cp .env.example .env
   # Open .env and fill in your Shoonya credentials
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the dashboard**

   ```bash
   streamlit run app.py
   ```

---

## Screener Filters (All 6 Must Pass)

| # | Filter | Condition |
|---|--------|-----------|
| 1 | **Price Range** | ₹20 ≤ LTP ≤ ₹150 |
| 2 | **Avg Volume** | 20-day average volume > 10 Lakh (1,000,000) |
| 3 | **Volume Surge** | Live session volume > 3× 20-day average |
| 4 | **RSI(14)** | 60 < RSI < 80 (momentum zone, not overbought) |
| 5 | **EMA(50)** | LTP > 50-day EMA (bullish trend confirmation) |
| 6 | **52-Week High Proximity** | LTP ≥ 98% of 52-week high (breakout candidate) |

> Stocks meeting at least 5 of the 6 filters are shown; those meeting all 6 are highlighted in green.

---

## Risk Management

| Parameter | Value |
|-----------|-------|
| **Stop-Loss** | 5% below entry price |
| **Take-Profit** | 20% above entry price |
| **Minimum R:R** | 3 : 1 |

---

## Customization

### Edit the watchlist

Open `config.py` and modify the `SYMBOLS` list:

```python
SYMBOLS = [
    "YESBANK", "SUZLON", "IDEA",  # ... add or remove NSE symbols
]
```

### Adjust filter thresholds

All filter parameters are in `config.py`:

```python
PRICE_MIN = 20          # Minimum LTP (₹)
PRICE_MAX = 150         # Maximum LTP (₹)
AVG_VOLUME_MIN = 1_000_000   # Minimum 20-day avg volume
VOLUME_SURGE_MULTIPLIER = 3  # Volume must be X× the average
RSI_MIN = 60            # RSI lower bound
RSI_MAX = 80            # RSI upper bound
```

### Change refresh interval

```python
REFRESH_INTERVAL_SECONDS = 30   # Seconds between auto-refresh cycles
```

---

## File Structure

```
STOCK-SCREENER/
├── app.py               # Streamlit dashboard (entry point)
├── config.py            # Symbols, constants, filter parameters
├── data_ingestion.py    # Shoonya login + WebSocket live tick handler
├── historical_data.py   # Fetch historical OHLCV seed data at startup
├── screener_engine.py   # Indicator computation + 6-layer filter logic
├── risk_manager.py      # SL, TP, R:R auto-calculator
├── requirements.txt     # Python dependencies
├── .env.example         # Credential template (copy to .env)
├── .gitignore           # Excludes .env and build artifacts
└── README.md            # This file
```

---

## ⚠️ Risk Disclaimer

**This software is provided for educational and informational purposes only. It does not constitute financial advice, investment advice, trading advice, or any other type of advice.**

- Trading in equities involves substantial risk of loss and is not suitable for all investors.
- Past performance is not indicative of future results.
- The screener output identifies technical setups only — it does not guarantee profitability.
- Always conduct your own due diligence before entering any trade.
- Never risk capital you cannot afford to lose.
- The authors and contributors of this project accept no liability for any financial losses incurred through the use of this software.

**Consult a registered financial advisor before making investment decisions.**
