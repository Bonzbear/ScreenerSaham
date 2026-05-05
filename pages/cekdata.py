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
# PARSER PASTE DATA
# =========================
def parse_paste_data(text):

    rows = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue
        if "Code" in line and "Last" in line:
            continue
        if line.startswith("NO"):
            continue

        # remove noise
        line = line.replace("¡ã", "").replace("¡è", "")

        parts = re.split(r"\s{2,}|\t+", line)

        if len(parts) < 10:
            continue

        try:
            code = parts[1]

            last = float(parts[2].replace(",", ""))
            prev = float(parts[4].replace(",", ""))
            open_ = float(parts[5].replace(",", ""))
            high = float(parts[6].replace(",", ""))
            low = float(parts[7].replace(",", ""))

            value = float(parts[8].replace(",", "").replace(".", ""))
            volume = float(parts[9].replace(",", "").replace(".", ""))

            rows.append({
                "Ticker": code + ".JK",
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": last,
                "Prev": prev,
                "Value": value,
                "Volume": volume
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
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.sort_index()

        clean[t] = df

    return clean


# =========================
# COMBINE TODAY + HISTORY
# =========================
def merge_data(hist, today_df):

    combined = {}

    for t in today_df["Ticker"]:

        if t not in hist:
            continue

        h = hist[t]

        row = today_df[today_df["Ticker"] == t].iloc[0]

        today_row = pd.DataFrame([{
            "Open": row["Open"],
            "High": row["High"],
            "Low": row["Low"],
            "Close": row["Close"],
            "Volume": row["Volume"]
        }], index=[pd.Timestamp.today()])

        df = pd.concat([h, today_row])
        df = df.sort_index()

        combined[t] = df

    return combined


# =========================
# INDICATOR
# =========================
def prepare(df):

    df = df.copy()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()

    return df.dropna()


# =========================
# SIGNAL RULE (FIXED)
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

    if today["Close"] * today["Volume"] < 5_000_000_000:
        return False

    return True


# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for t, df in data.items():

        df = prepare(df)

        if len(df) < 30:
            continue

        if not is_signal(df):
            continue

        results.append({
            "Ticker": t,
            "Price": df["Close"].iloc[-1],
            "Volume": df["Volume"].iloc[-1]
        })

    out = pd.DataFrame(results)

    if not out.empty:
        out.insert(0, "Rank", range(1, len(out) + 1))

    return out


# =========================
# TELEGRAM FORMAT
# =========================
def format_msg(df):

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL SCREENER 🚨</b>\n{now}\n━━━━━━━━━━━━\n"

    for i, r in df.iterrows():
        msg += f"{r['Rank']}. <b>{r['Ticker'].replace('.JK','')}</b>\n"

    return msg


# =========================
# UI
# =========================
st.title("Screener Saham (Paste Data + Yahoo History)")

paste = st.text_area("Paste Data BEI", height=300)

if st.button("RUN"):

    today = parse_paste_data(paste)

    if today.empty:
        st.error("Data tidak terbaca")
        st.stop()

    tickers = today["Ticker"].tolist()

    hist = get_history(tickers)

    merged = merge_data(hist, today)

    result = run_screener(merged)

    st.dataframe(result)

    if not result.empty:
        send_telegram(format_msg(result))
        st.success("Sent Telegram")
