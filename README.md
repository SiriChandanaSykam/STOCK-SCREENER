# ⚡ Operation Compound — NSE Micro-Cap Momentum Screener

A zero-latency, production-ready momentum screener for NSE micro-cap stocks,
built with the **Shoonya (Finvasia) API**, **pandas-ta**, and **Streamlit**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Streamlit UI  (app.py)               │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│   │ Sidebar     │  │ KPI Metrics  │  │ Trade Cards   │  │
│   │ Stats/Rules │  │ Symbols/Hits │  │ SL / TP / R:R │  │
│   └─────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────┬───────────────────────────────┘
                           │
           ┌───────────────▼──────────────┐
           │     screener_engine.py       │
           │  RSI · EMA · AvgVol · 52WH   │
           │  6 simultaneous filters      │
           └───────────┬──────────────────┘
            ┌──────────┘            └──────────┐
┌───────────▼──────────┐   ┌───────────────────▼────────┐
│  historical_data.py  │   │     data_ingestion.py       │
│  OHLCV seed (252d)   │   │  Shoonya WebSocket ticks    │
│  via REST API        │   │  in-memory deque (no disk)  │
└──────────────────────┘   └─────────────────────────────┘
                                      │
                           ┌──────────▼──────────┐
                           │   Shoonya API        │
                           │   (NSE live feed)    │
                           └─────────────────────┘
```

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/SiriChandanaSykam/STOCK-SCREENER.git
cd STOCK-SCREENER
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install All Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Credentials
```bash
cp .env.example .env
```
Open `.env` in any text editor and fill in your Shoonya credentials:
```
SHOONYA_USER_ID=FA12345
SHOONYA_PASSWORD=YourPassword
SHOONYA_TOTP_SECRET=BASE32TOTPSECRET
SHOONYA_VENDOR_CODE=YourVendorCode
SHOONYA_API_SECRET=YourApiSecret
SHOONYA_IMEI=YourIMEI
```
> **Where to get these?**
> Log in to [Shoonya / Finvasia](https://shoonya.com) → API section → generate your API credentials.
> The TOTP secret is the Base32 key shown when you set up 2FA.

### 5. Launch the Dashboard
```bash
streamlit run app.py
```
The browser opens at `http://localhost:8501` automatically.

---

## Screener Filters (All 6 Must Pass Simultaneously)

| # | Filter | Condition |
|---|---|---|
| 1 | Price Range | ₹20 ≤ LTP ≤ ₹150 |
| 2 | Liquidity | 20-Day Avg Volume > 10 Lakh |
| 3 | Volume Surge | Live Volume > 3× Avg Volume |
| 4 | Momentum | 60 < RSI(14) < 80 |
| 5 | Trend | LTP > EMA(50) |
| 6 | Breakout Zone | LTP ≥ 98% of 52-Week High |

Stocks that meet 5/6 criteria are shown in **yellow** (watch list).  
Stocks that meet all 6 are shown in **green** (action candidates).

---

## Risk Management (Auto-Calculated)

| Metric | Formula |
|---|---|
| Stop-Loss | Entry × 0.95 (−5%) |
| Take-Profit | Entry × 1.20 (+20%) |
| Risk:Reward | Reward ÷ Risk (target ≥ 3:1) |

---

## Customising the Watchlist

Edit `config.py`:
```python
SYMBOLS = [
    "YESBANK", "SUZLON", "RVNL",   # ← add or remove symbols here
]
```
Use the NSE trading symbol (e.g., `TATAMOTORS`, `IDEA`, `NHPC`).

---

## ⚠️ Risk Disclaimer

This tool is for **educational and informational purposes only**.  
It does **not** constitute financial advice.  
Stock trading involves substantial risk of loss.  
Past screening results do not guarantee future performance.  
Always consult a SEBI-registered investment advisor before trading.
