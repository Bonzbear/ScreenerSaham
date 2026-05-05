import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import datetime
import pytz

TOKEN = "YOUR_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
MAX_SCORE = 1000


# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})


# =========================
# PARSE COPY PASTE INPUT
# =========================
def parse_input(text):

    lines = text.strip().split("\n")

    data = []

    for line in lines[1:]:  # skip header

        parts = line.split("\t")

        if len(parts) < 5:
            continue

        code = parts[0].strip()
        last = float(parts[1].replace(",", ""))
        change_pct = float(parts[2].replace("%", "").replace(",", "."))
        value = parts[3].replace(" B", "").replace(" M", "").strip()
        volume = parts[4].strip()

        # convert value
        if "B" in parts[3]:
            value = float(value) * 1_000_000_000
        elif "M" in parts[3]:
            value = float(value) * 1_000_000
        else:
            value = float(value)

        # convert volume
        if "M" in volume:
            volume = float(volume.replace("M", "")) * 1_000_000
        elif "K" in volume:
            volume = float(volume.replace("K", "")) * 1_000
        else:
            volume = float(volume)

        data.append({
            "Ticker": code + ".JK",
            "Close": last,
            "ChangePct": change_pct,
            "Value": value,
            "Volume": volume
        })

    return pd.DataFrame(data)


# =========================
# YAHOO DATA (H-1)
# =========================
@st.cache_data(ttl=600)
def get_history(tickers):

    raw = yf.download(
        tickers=" ".join(tickers),
        period="6mo",
        group_by="ticker",
        progress=False
    )

    result = {}

    for t in tickers:

        if t not in raw:
            continue

        df = raw[t].copy()
        df = df.dropna()
        result[t] = df

    return result


# =========================
# PREPARE TECHNICAL
# =========================
def prepare(df):

    df = df.copy()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()

    df["VWAP"] = (df["Volume"] * df["Close"]).cumsum() / df["Volume"].cumsum()

    return df.dropna()


# =========================
# SCORING
# =========================
def score(df_today, hist):

    hist = prepare(hist)

    if len(hist) < 20:
        return 0, False

    prev = hist.iloc[-2]
    last = hist.iloc[-1]

    score = 0
    warning = False

    # trend
    if last["Close"] > last["SMA5"]:
        score += 20

    if last["SMA5"] > last["SMA20"]:
        score += 20

    # volume spike
    if last["Volume"] > last["VOLMA20"]:
        score += 20

    # breakout
    if last["Close"] > prev["Close"]:
        score += 20

    # confirm dari hari ini (copy paste)
    if df_today["ChangePct"] > 5:
        score += 10

    if df_today["Volume"] > last["VOLMA20"]:
        score += 10

    # risk warning
    if df_today["ChangePct"] > 25:
        warning = True

    return score, warning


# =========================
# SCREENER
# =========================
def run_screener(df_today, hist_data):

    results = []

    for _, row in df_today.iterrows():

        ticker = row["Ticker"]

        if ticker not in hist_data:
            continue

        hist = hist_data[ticker]

        s, warn = score(row, hist)

        results.append({
            "Ticker": ticker,
            "Price": row["Close"],
            "Score": s,
            "Warning": "⚠️" if warn else ""
        })

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values("Score", ascending=False)

    return df


# =========================
# UI
# =========================
st.title("Hybrid Screener (Copy Paste + Yahoo)")

text = st.text_area("Paste data di sini")

if st.button("RUN"):

    df_today = parse_input(text)

    tickers = df_today["Ticker"].tolist()

    hist_data = get_history(tickers)

    result = run_screener(df_today, hist_data)

    st.session_state["result"] = result


# =========================
# DISPLAY
# =========================
if "result" in st.session_state:

    st.dataframe(st.session_state["result"], use_container_width=True)


# =========================
# TELEGRAM
# =========================
if "result" in st.session_state:

    if st.button("SEND TELEGRAM"):

        df = st.session_state["result"].head(10)

        msg = "<b>🚨 SIGNAL 🚨</b>\n\n"

        for i, r in enumerate(df.iterrows(), 1):
            row = r[1]
            msg += f"{i}. {row['Ticker']} {row['Warning']} (Score {row['Score']})\n"

        send_telegram(msg)
        st.success("sent")
