# NSE Micro-Cap Momentum Screener — "Operation Compound"

> **Zero-latency momentum screener for the Indian Stock Market (NSE)**  
> Powered by the **Shoonya by Finvasia API** (NorenRestApiPy) with a live **Streamlit** dashboard.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         app.py (Streamlit UI)                        │
│   ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│   │ Sidebar:         │   │ Master Table:    │   │ HOLD CASH      │  │
│   │ session stats,   │   │ Ticker · LTP ·   │   │ banner when    │  │
│   │ WS status,       │   │ RSI · EMA · Vol  │   │ 0 stocks pass  │  │
│   │ market regime    │   │ Surge · SL · TP  │   │                │  │
│   └──────────────────┘   └──────────────────┘   └────────────────┘  │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ calls every 30 s
               ┌───────────────────┼───────────────────┐
               ▼                   ▼                   ▼
     screener_engine.py     risk_manager.py      config.py
     (6-criteria filter)    (SL / TP / R:R)   (watchlist & params)
               │
       ┌───────┴───────┐
       ▼               ▼
 historical_data.py  data_ingestion.py
 (seed OHLCV via     (Shoonya WebSocket
  REST API)           live ticks → deque)
       │               │
       └───────┬───────┘
               ▼
     Shoonya (Finvasia) API
     NorenRestApiPy
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/SiriChandanaSykam/STOCK-SCREENER.git
cd STOCK-SCREENER
```

### 2. Create a virtual environment

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create and populate the `.env` file

Copy the example template and fill in your Shoonya credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```
SHOONYA_USER_ID=your_user_id_here
SHOONYA_PASSWORD=your_password_here
SHOONYA_TOTP_SECRET=your_totp_secret_key_here
SHOONYA_VENDOR_CODE=your_vendor_code_here
SHOONYA_API_SECRET=your_api_secret_here
SHOONYA_IMEI=your_imei_here
```

| Variable | Where to find it |
|---|---|
| `SHOONYA_USER_ID` | Your Shoonya / Finvasia login ID |
| `SHOONYA_PASSWORD` | Your Shoonya login password |
| `SHOONYA_TOTP_SECRET` | TOTP secret from your authenticator app (base-32 key) |
| `SHOONYA_VENDOR_CODE` | Provided by Finvasia when you register as a vendor |
| `SHOONYA_API_SECRET` | API secret from the Finvasia developer portal |
| `SHOONYA_IMEI` | Device IMEI or any unique string (e.g. `abc1234`) |

> ⚠️ **Never commit the `.env` file.** It is already listed in `.gitignore`.

### 5. Run the dashboard

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501` and auto-refresh every **30 seconds**.

---

## How It Works

| Module | Responsibility |
|---|---|
| `config.py` | Watchlist, price/volume/RSI thresholds, risk percentages |
| `data_ingestion.py` | Shoonya login + WebSocket; stores live ticks in memory |
| `historical_data.py` | Bootstraps seed OHLCV data via Shoonya REST API on startup |
| `screener_engine.py` | Calculates RSI(14), EMA(50), 20-day avg vol, 52-week high; applies 6-criteria filter |
| `risk_manager.py` | Computes stop-loss (−5 %), take-profit (+20 %), R:R, volume-surge multiple |
| `app.py` | Streamlit dashboard with auto-refresh, colour-coded table, HOLD CASH banner |

### 6-Criteria Filter

A stock must satisfy **all six** conditions simultaneously:

| # | Criterion |
|---|---|
| 1 | `₹20 ≤ price ≤ ₹150` |
| 2 | 20-day average daily volume > 1,000,000 shares |
| 3 | Today's live cumulative volume > 3 × 20-day average |
| 4 | `60 < RSI(14) < 80` |
| 5 | Current price > EMA(50) |
| 6 | Current price ≥ 98 % of 52-week high |

Stocks meeting 5/6 criteria are highlighted in **yellow** as watchlist candidates.

---

## Customising the Watchlist

Open `config.py` and edit the `SYMBOLS` list:

```python
SYMBOLS = [
    "YESBANK", "SUZLON", "IDEA",
    # add or remove NSE ticker symbols here
]
```

All screener thresholds can also be adjusted in `config.py`:

```python
PRICE_MIN = 20          # minimum price (₹)
PRICE_MAX = 150         # maximum price (₹)
AVG_VOLUME_MIN = 1_000_000
VOLUME_SURGE_MULTIPLIER = 3
RSI_MIN = 60
RSI_MAX = 80
STOP_LOSS_PCT = 0.05    # 5 %
TAKE_PROFIT_PCT = 0.20  # 20 %
REFRESH_INTERVAL_SECONDS = 30
```

---

## Risk Disclaimer

> **This software is provided for educational and informational purposes only.**  
> It does **not** constitute financial advice, a recommendation to buy or sell any security,
> or a solicitation of any investment.  
> Trading in equities and derivatives carries significant risk of loss.  
> Past performance is not indicative of future results.  
> Always conduct your own due diligence and consult a SEBI-registered investment adviser
> before making any investment decisions.  
> The authors and contributors of this project accept no liability for any financial losses
> incurred through the use of this software.
