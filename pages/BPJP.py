import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================
TICKERS = [
    "BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK","ASII.JK",
    "ADRO.JK","MDKA.JK","GOTO.JK","ESSA.JK","ANTM.JK"
]

MIN_VALUE = 5_000_000_000
TP_PCT = 0.015
SL_PCT = 0.03

# =========================
# GET DATA (SUDAH FIX)
# =========================
def get_data(ticker):
    end = datetime.today()
    start = end - timedelta(days=730)

    df = yf.download(ticker, start=start, end=end, progress=False)

    if df is None or df.empty:
        return None

    # 🔥 FIX MULTIINDEX (WAJIB)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # ambil kolom penting saja
    df = df[["Open","High","Low","Close","Volume"]].copy()

    # indikator
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    df["Value"] = df["Close"] * df["Volume"]

    df.dropna(inplace=True)

    return df

# =========================
# SCREENER
# =========================
def is_screening_signal(df, i):
    today = df.iloc[i].squeeze()
    prev = df.iloc[i-1].squeeze()

    if today["Volume"] <= prev["Volume"]:
        return False

    if prev["Close"] >= today["Close"]:
        return False

    if today["Close"] <= today["SMA5"]:
        return False

    if today["Value"] <= MIN_VALUE:
        return False

    if today["High"] / prev["Close"] < 1.10:
        return False

    # filter tambahan ≥10%
    if today["Close"] < prev["Close"] * 1.10:
        return False

    return True

# =========================
# BACKTEST
# =========================
def backtest_ticker(df):
    results = []

    for i in range(21, len(df)-1):

        if not is_screening_signal(df, i):
            continue

        today = df.iloc[i]
        next_day = df.iloc[i+1]

        # IEP proxy
        if next_day["Open"] < today["Close"] * 1.02:
            continue

        entry = next_day["Open"]
        tp = entry * (1 + TP_PCT)
        sl = entry * (1 - SL_PCT)

        high = next_day["High"]
        low = next_day["Low"]

        if high >= tp:
            results.append(1)
        elif low <= sl:
            results.append(0)
        else:
            results.append(0)

    total = len(results)
    winrate = sum(results) / total if total > 0 else 0

    return total, winrate

# =========================
# MAIN
# =========================
summary = []

for ticker in TICKERS:
    print(f"Processing {ticker}...")

    df = get_data(ticker)
    if df is None:
        continue

    total, winrate = backtest_ticker(df)

    summary.append({
        "Ticker": ticker,
        "Trades": total,
        "Winrate (%)": round(winrate * 100, 2)
    })

# =========================
# RESULT
# =========================
result_df = pd.DataFrame(summary)

if not result_df.empty:
    result_df = result_df.sort_values(by="Winrate (%)", ascending=False)

print("\n=== RESULT ===")
print(result_df)

# overall
if not result_df.empty:
    total_trades = result_df["Trades"].sum()
    weighted_winrate = (
        (result_df["Trades"] * result_df["Winrate (%)"]).sum() / total_trades
    )

    print(f"\nTotal Trades: {total_trades}")
    print(f"Overall Winrate: {weighted_winrate:.2f}%")
