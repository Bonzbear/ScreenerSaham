import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import pytz

MAX_SCORE = 1000


# =========================
# YAHOO DATA
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):

    raw = yf.download(
        tickers=" ".join(tickers),
        period="2y",
        group_by="ticker",
        progress=False
    )

    data = {}

    for t in tickers:

        if t not in raw:
            continue

        df = raw[t].copy()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        df["Ticker"] = t
        df["Value"] = df["Close"] * df["Volume"]

        data[t] = df

    return data


# =========================
# PREPARE
# =========================
def prepare(df):

    df = df.copy()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["VOLMA5"] = df["Volume"].rolling(5).mean()
    df["VWAP"] = (df["Volume"] * df["Close"]).cumsum() / df["Volume"].cumsum()

    return df.dropna()


# =========================
# SIGNAL (DIPERLEMAH SEMENTARA)
# =========================
def is_signal(df, i):

    if i < 10:
        return False

    today = df.iloc[i]
    prev = df.iloc[i-1]

    if today["Close"] < 50:
        return False

    if today["Volume"] <= 0:
        return False

    # 🔥 SIGNAL DIPERMUDAH SUPAYA ADA OUTPUT
    cond1 = today["Close"] > today["SMA5"]
    cond2 = today["Volume"] > today["VOLMA20"]
    cond3 = today["Close"] > prev["Close"]

    return cond1 and cond2 and cond3


# =========================
# SCORE
# =========================
def calculate_score(df):

    today = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0

    if today["Close"] > today["SMA5"]:
        score += 250
    if today["Volume"] > today["VOLMA20"]:
        score += 250
    if today["Close"] > prev["Close"]:
        score += 250
    if today["Close"] > today["VWAP"]:
        score += 250

    return score


# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for ticker, df in data.items():

        df = prepare(df)

        if len(df) < 30:
            continue

        if not is_signal(df, len(df)-1):
            continue

        score = calculate_score(df)

        results.append({
            "Ticker": ticker,
            "Price": df["Close"].iloc[-1],
            "Score": score
        })

    out = pd.DataFrame(results)

    if not out.empty:
        out = out.sort_values("Score", ascending=False)
        out.insert(0, "Rank", range(1, len(out)+1))

    return out


# =========================
# UI
# =========================
st.set_page_config(page_title="Screener Yahoo Only", layout="wide")
st.title("Screener Saham (Yahoo Only Debug Version)")

tickers_input = st.text_input("Masukkan ticker (pisahkan spasi)", "BBCA.JK BBRI.JK BMRI.JK TLKM.JK ASII.JK")

if st.button("Run"):

    tickers = tickers_input.split()

    data = get_data(tickers)

    result = run_screener(data)

    st.dataframe(result, use_container_width=True)

    st.success(f"Total hasil: {len(result)}")
