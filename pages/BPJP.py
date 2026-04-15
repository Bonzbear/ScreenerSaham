import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================
MIN_VALUE = 1_000_000_000  # diturunkan biar ada hasil
TP_PCT = 0.015
SL_PCT = 0.03

st.title("Backtest Breakout + Gap Strategy")

# =========================
# GET TICKERS (AUTO IDX)
# =========================
@st.cache_data
def get_all_idx_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Indonesia_Stock_Exchange"
    tables = pd.read_html(url)
    df = tables[0]

    tickers = df["Ticker"].tolist()
    tickers = [t + ".JK" for t in tickers]

    return tickers[:100]  # batasi dulu biar cepat

# =========================
# GET DATA
# =========================
@st.cache_data
def get_data(ticker):
    end = datetime.today()
    start = end - timedelta(days=730)

    df = yf.download(ticker, start=start, end=end, progress=False)

    if df is None or df.empty:
        return None

    # FIX MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    try:
        df = df[["Open","High","Low","Close","Volume"]].copy()
    except:
        return None

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    df["Value"] = df["Close"] * df["Volume"]

    # drop minimal
    df = df.dropna(subset=["SMA5","AvgVolume20"])

    return df

# =========================
# SCREENER
# =========================
def is_signal(df, i):
    today = df.iloc[i]
    prev = df.iloc[i-1]

    if today["Volume"] <= prev["Volume"]:
        return False

    if today["Close"] <= prev["Close"]:
        return False

    if today["Close"] <= today["SMA5"]:
        return False

    if today["Value"] <= MIN_VALUE:
        return False

    if today["Close"] < prev["Close"] * 1.08:  # diturunkan dari 10%
        return False

    return True

# =========================
# BACKTEST
# =========================
def backtest(df):
    results = []

    for i in range(21, len(df)-1):

        if not is_signal(df, i):
            continue

        today = df.iloc[i]
        next_day = df.iloc[i+1]

        # IEP proxy
        if next_day["Open"] < today["Close"] * 1.02:
            continue

        entry = next_day["Open"]
        tp = entry * (1 + TP_PCT)
        sl = entry * (1 - SL_PCT)

        if next_day["High"] >= tp:
            results.append(1)
        elif next_day["Low"] <= sl:
            results.append(0)
        else:
            results.append(0)

    total = len(results)
    winrate = sum(results) / total if total > 0 else 0

    return total, winrate

# =========================
# MAIN
# =========================
if st.button("Run Backtest"):

    tickers = get_all_idx_tickers()

    summary = []

    progress = st.progress(0)
    total_ticker = len(tickers)

    for idx, ticker in enumerate(tickers):

        progress.progress((idx + 1) / total_ticker)
        st.write(f"Processing {ticker}")

        df = get_data(ticker)

        if df is None or len(df) < 50:
            continue

        total, winrate = backtest(df)

        if total > 0:
            summary.append({
                "Ticker": ticker,
                "Trades": total,
                "Winrate (%)": round(winrate * 100, 2)
            })

    result_df = pd.DataFrame(summary)

    # =========================
    # OUTPUT
    # =========================
    st.write("## Hasil Backtest")

    if result_df.empty:
        st.warning("Tidak ada hasil. Coba longgarkan filter atau cek data.")
    else:
        result_df = result_df.sort_values(by="Winrate (%)", ascending=False)

        st.dataframe(result_df)

        total_trades = result_df["Trades"].sum()
        weighted_winrate = (
            (result_df["Trades"] * result_df["Winrate (%)"]).sum() / total_trades
        )

        st.write("### Summary")
        st.write(f"Total Trades: {total_trades}")
        st.write(f"Overall Winrate: {weighted_winrate:.2f}%")

        st.success("Selesai ✅")
