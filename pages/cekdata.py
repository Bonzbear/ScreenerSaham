import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import datetime
import pytz
import re

TOKEN = "YOUR_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
MAX_SCORE = 1000


# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })


def convert_to_number(x):

    x = x.replace(",", "").strip()

    if "B" in x:
        return float(x.replace("B","")) * 1_000_000_000
    if "M" in x:
        return float(x.replace("M","")) * 1_000_000
    if "K" in x:
        return float(x.replace("K","")) * 1_000

    return float(x)


def parse_today(text):

    rows = []

    for line in text.split("\n"):

        line = line.strip()

        if not line:
            continue

        # skip header
        if "Code" in line or "NO" in line:
            continue

        parts = line.split()

        # minimal safety check
        if len(parts) < 5:
            continue

        try:
            code = parts[0]

            last = parts[1]
            change = parts[2]

            value = parts[-2]
            volume = parts[-1]

            rows.append({
                "Ticker": code + ".JK",
                "Open": float(last.replace(",", "")),
                "High": float(last.replace(",", "")),
                "Low": float(last.replace(",", "")),
                "Close": float(last.replace(",", "")),
                "Volume": convert_to_number(volume),
                "Value": convert_to_number(value)
            })

        except:
            continue

    return pd.DataFrame(rows)

# =========================
# YAHOO HISTORY
# =========================
@st.cache_data(ttl=600)
def get_history(tickers):

    raw = yf.download(
        tickers=" ".join(tickers),
        period="5y",
        group_by="ticker",
        progress=False
    )

    clean = {}

    for t in tickers:
        if t not in raw:
            continue

        df = raw[t].copy()
        df = df.dropna()

        clean[t] = df

    return clean


# =========================
# MERGE TODAY + YAHOO
# =========================
def merge_data(hist, today_df):

    combined = {}

    for _, row in today_df.iterrows():

        t = row["Ticker"]

        if t not in hist:
            continue

        df = hist[t].copy()

        today_index = pd.Timestamp.today().normalize()

        today_row = pd.DataFrame([{
            "Open": row["Open"],
            "High": row["High"],
            "Low": row["Low"],
            "Close": row["Close"],
            "Volume": row["Volume"],
            "Value": row["Value"]
        }], index=[today_index])

        df = pd.concat([df, today_row])
        df = df.sort_index()

        combined[t] = df

    return combined


# =========================
# PREPARE
# =========================
def prepare(df):

    df = df.copy()
    df = df.sort_index()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()

    df["AvgValue20"] = df["Value"].rolling(20).mean()

    return df.dropna()


# =========================
# SIGNAL RULE (SESUAI REQUEST)
# =========================
def is_signal(df):

    if len(df) < 30:
        return False

    today = df.iloc[-1]
    prev = df.iloc[-2]

    return (
        today["Volume"] > prev["Volume"] and
        prev["Close"] < today["Close"] and
        today["Close"] > today["SMA5"] and
        today["Value"] > 5_000_000_000
    )


# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for t, df in data.items():

        df = prepare(df)

        if not is_signal(df):
            continue

        results.append({
            "Ticker": t,
            "Close": df["Close"].iloc[-1],
            "Volume": df["Volume"].iloc[-1],
            "Value": df["Value"].iloc[-1]
        })

    out = pd.DataFrame(results)

    if not out.empty:
        out = out.sort_values("Value", ascending=False)

    return out


# =========================
# TELEGRAM FORMAT
# =========================
def format_msg(df):

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL 🚨</b>\n{now}\n━━━━━━━━━━\n"

    for i, r in df.head(10).iterrows():
        msg += f"<b>{r['Ticker'].replace('.JK','')}</b>\n"

    return msg


# =========================
# UI
# =========================
st.title("Screener CopyPaste + Yahoo History")

text = st.text_area("Paste data hari ini")

if st.button("Run"):

    today_df = parse_today(text)

    if today_df.empty:
        st.error("Data tidak terbaca")
        st.stop()

    tickers = today_df["Ticker"].tolist()

    hist = get_history(tickers)
    merged = merge_data(hist, today_df)

    result = run_screener(merged)

    st.dataframe(result)

    st.session_state["result"] = result


# =========================
# TELEGRAM SEND
# =========================
if "result" in st.session_state:

    if st.button("Send Telegram"):

        msg = format_msg(st.session_state["result"])
        send_telegram(msg)

        st.success("Terkirim")
