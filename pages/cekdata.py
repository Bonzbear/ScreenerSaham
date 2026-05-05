import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Screener Fix", layout="wide")
st.title("Screener Saham (Rule Custom)")

# =========================
# INPUT
# =========================
tickers_input = st.text_input(
    "Ticker (pisah spasi)",
    "BBCA.JK BBRI.JK BMRI.JK TLKM.JK ASII.JK"
)


# =========================
# DATA YAHOO
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):

    raw = yf.download(
        tickers=" ".join(tickers),
        period="1y",
        group_by="ticker",
        progress=False
    )

    data = {}

    for t in tickers:

        if t not in raw:
            continue

        df = raw[t].copy()
        df.index = pd.to_datetime(df.index)
        df = df.dropna()

        # value = close * volume
        df["Value"] = df["Close"] * df["Volume"]

        data[t] = df

    return data


# =========================
# INDICATOR
# =========================
def prepare(df):

    df = df.copy()

    df["SMA5"] = df["Close"].rolling(5).mean()

    return df.dropna()


# =========================
# RULE SCREENER (SESUAI PERMINTAAN KAMU)
# =========================
def signal(df):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # RULE 1: volume > prev volume
    cond1 = last["Volume"] > prev["Volume"]

    # RULE 2: prev close < current price
    cond2 = prev["Close"] < last["Close"]

    # RULE 3: current price > SMA5
    cond3 = last["Close"] > last["SMA5"]

    # RULE 4: value > 5B
    cond4 = last["Value"] > 5_000_000_000

    return cond1 and cond2 and cond3 and cond4


# =========================
# SCREENER
# =========================
def run(data):

    results = []

    for t, df in data.items():

        if len(df) < 20:
            continue

        df = prepare(df)

        if not signal(df):
            continue

        results.append({
            "Ticker": t,
            "Price": df["Close"].iloc[-1],
            "Volume": df["Volume"].iloc[-1],
            "Value": df["Value"].iloc[-1],
        })

    out = pd.DataFrame(results)

    if not out.empty:
        out = out.sort_values("Value", ascending=False)
        out.insert(0, "Rank", range(1, len(out)+1))

    return out


# =========================
# RUN
# =========================
if st.button("RUN SCREENER"):

    tickers = tickers_input.split()

    data = get_data(tickers)

    result = run(data)

    if result.empty:
        st.warning("Tidak ada signal")
    else:
        st.success(f"Signal ditemukan: {len(result)}")
        st.dataframe(result, use_container_width=True)
