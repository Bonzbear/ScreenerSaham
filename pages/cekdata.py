import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np
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


# =========================
# PARSER PASTE DATA (FIX UTAMA)
# =========================
def parse_paste_data(text):

    rows = []

    for line in text.splitlines():

        line = line.strip()

        # skip header / empty
        if not line:
            continue
        if "Code" in line and "Last" in line:
            continue
        if line.startswith("NO"):
            continue

        # normalize weird characters
        line = line.replace("¡ã", "").replace("¡è", "")

        # split by 2+ spaces OR tab
        parts = re.split(r"\s{2,}|\t+", line)

        if len(parts) < 8:
            continue

        try:
            code = parts[1].strip()
            last = parts[2].strip()
            change = parts[3].strip()
            value_m = parts[4].strip()
            volume = parts[5].strip()

            # clean numeric
            last = float(last.replace(",", ""))
            value_m = float(value_m.replace(",", "").replace(".", ""))
            volume = float(volume.replace(",", "").replace(".", ""))

            ticker = code + ".JK"

            rows.append({
                "Ticker": ticker,
                "Close": last,
                "Value": value_m * 1_000_000,
                "Volume": volume
            })

        except:
            continue

    return pd.DataFrame(rows)


# =========================
# YAHOO HISTORY
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):

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
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.sort_index()

        clean[t] = df

    return clean


# =========================
# PREPARE
# =========================
def prepare(df):

    df = df.copy()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()

    return df.dropna()


# =========================
# SIGNAL (FIXED REQUIREMENT)
# =========================
def is_signal(df):

    today = df.iloc[-1]
    prev = df.iloc[-2]

    if today["Volume"] <= prev["Volume"]:
        return False

    if prev["Close"] >= today["Close"]:
        return False

    if today["Close"] <= today["SMA5"]:
        return False

    if today["Value"] <= 5_000_000_000:
        return False

    return True


# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for ticker, df in data.items():

        df = prepare(df)

        if len(df) < 30:
            continue

        if not is_signal(df):
            continue

        results.append({
            "Ticker": ticker,
            "Price": df["Close"].iloc[-1],
            "Value": df["Value"].iloc[-1]
        })

    out = pd.DataFrame(results)

    if not out.empty:
        out.insert(0, "Rank", range(1, len(out) + 1))

    return out


# =========================
# TELEGRAM FORMAT
# =========================
def format_msg(df):

    if df.empty:
        return "Tidak ada signal"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL 🚨</b>\n{now}\n━━━━━━━━━━━━\n"

    for i, r in df.head(10).iterrows():
        msg += f"{r['Rank']}. <b>{r['Ticker'].replace('.JK','')}</b>\n"

    return msg


# =========================
# UI
# =========================
st.title("Screener Saham (Paste Data Fix)")

paste_data = st.text_area("Paste Data Hari Ini", height=300)

if st.button("RUN"):

    df_today = parse_paste_data(paste_data)

    if df_today.empty:
        st.error("Data tidak terbaca")
        st.stop()

    tickers = df_today["Ticker"].tolist()

    history = get_data(tickers)

    combined = {}

    for t in tickers:

        if t not in history:
            continue

        hist = history[t]

        today_row = df_today[df_today["Ticker"] == t].iloc[0]

        today_df = pd.DataFrame([{
            "Open": today_row["Close"],
            "High": today_row["Close"],
            "Low": today_row["Close"],
            "Close": today_row["Close"],
            "Volume": today_row["Volume"],
            "Value": today_row["Value"]
        }], index=[pd.Timestamp.today()])

        full = pd.concat([hist, today_df])
        combined[t] = full

    result = run_screener(combined)

    st.dataframe(result)

    if not result.empty:
        msg = format_msg(result)
        send_telegram(msg)
        st.success("Sent Telegram")
