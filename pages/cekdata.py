import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# =========================
# CONFIG
# =========================
TOKEN = "ISI_TOKEN"
CHAT_ID = "ISI_CHAT_ID"

TICKERS = ['AALI.JK','BBRI.JK','BBCA.JK','TLKM.JK','BMRI.JK']  # bisa full list kamu

# =========================
# SAFE SCALAR
# =========================
def scalar(x):
    if isinstance(x, pd.Series):
        return float(x.iloc[0])
    if isinstance(x, np.ndarray):
        return float(x[0])
    return float(x)

# =========================
# DOWNLOAD DATA
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):
    return yf.download(
        tickers=" ".join(tickers),
        period="6mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True
    )

# =========================
# PREP (HANYA SMA5 SESUAI KODE KAMU)
# =========================
def prepare(df):
    df = df.copy()
    df["SMA5"] = df["Close"].rolling(5).mean()
    return df.dropna()

# =========================
# RULE KAMU (TIDAK DIUBAH)
# =========================
def is_signal(df):

    today = df.iloc[-1]
    prev = df.iloc[-2]

    close = scalar(today["Close"])
    volume = scalar(today["Volume"])
    prev_close = scalar(prev["Close"])
    sma5 = scalar(today["SMA5"])

    # RULE ORIGINAL KAMU
    if close < 50 or close > 9700:
        return False

    if volume < 1_000_000:
        return False

    if close <= sma5:
        return False

    if volume <= scalar(prev["Volume"]):
        return False

    return True

# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for ticker in TICKERS:

        try:
            df = data[ticker].dropna()
        except:
            continue

        if df.empty or len(df) < 10:
            continue

        df = prepare(df)

        if len(df) < 10:
            continue

        if not is_signal(df):
            continue

        today = df.iloc[-1]

        close = scalar(today["Close"])
        volume = scalar(today["Volume"])

        results.append({
            "Ticker": ticker,
            "Close": close,
            "Volume": volume
        })

    return pd.DataFrame(results)

# =========================
# UI
# =========================
st.title("Screener Saham (Rule Original)")

if st.button("Run Screener"):

    data = get_data(TICKERS)
    df = run_screener(data)

    if df.empty:
        st.warning("Tidak ada saham lolos")
    else:
        st.success(f"{len(df)} saham ditemukan")
        st.dataframe(df, use_container_width=True)
