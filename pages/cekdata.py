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
# COPY PASTE PARSER (HARI INI)
# =========================
def parse_today(text):

    lines = text.strip().split("\n")
    data = []

    for line in lines[1:]:
        parts = line.split("\t")

        if len(parts) < 5:
            continue

        code = parts[0]
        last = float(parts[1].replace(",", ""))
        change = float(parts[2].replace("%", "").replace(",", "."))
        value = parts[3]
        volume = parts[4]

        # value convert
        if "B" in value:
            value = float(value.replace(" B", "")) * 1e9
        elif "M" in value:
            value = float(value.replace(" M", "")) * 1e6
        else:
            value = float(value)

        # volume convert
        if "M" in volume:
            volume = float(volume.replace(" M", "")) * 1e6
        elif "K" in volume:
            volume = float(volume.replace(" K", "")) * 1e3
        else:
            volume = float(volume)

        data.append({
            "Ticker": code + ".JK",
            "Close": last,
            "ChangePct": change,
            "Value": value,
            "Volume": volume
        })

    return pd.DataFrame(data)


# =========================
# YAHOO HISTORICAL
# =========================
@st.cache_data(ttl=600)
def get_history(tickers):

    raw = yf.download(
        tickers=" ".join(tickers),
        period="6mo",
        group_by="ticker",
        progress=False
    )

    out = {}

    for t in tickers:
        if t not in raw:
            continue
        df = raw[t].dropna()
        out[t] = df

    return out


# =========================
# TECHNICAL
# =========================
def prepare(df):

    df = df.copy()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["VWAP"] = (df["Volume"] * df["Close"]).cumsum() / df["Volume"].cumsum()

    return df.dropna()


# =========================
# SIGNAL (INI YANG KAMU MAU TETAP ADA)
# =========================
def is_signal(df, today_row, hist):

    hist = prepare(hist)

    if len(hist) < 20:
        return False

    last = hist.iloc[-1]
    prev = hist.iloc[-2]

    # trend confirmation
    cond1 = last["Close"] > last["SMA5"]
    cond2 = last["SMA5"] > last["SMA20"]

    # volume breakout
    cond3 = last["Volume"] > last["VOLMA20"]

    # price momentum
    cond4 = last["Close"] > prev["Close"]

    # confirmation dari hari ini (copy paste)
    cond5 = today_row["ChangePct"] > 3
    cond6 = today_row["Volume"] > last["VOLMA20"]

    return cond1 and cond2 and cond3 and cond4 and cond5 and cond6


# =========================
# SCORE SYSTEM
# =========================
def score(df_today, hist):

    hist = prepare(hist)

    last = hist.iloc[-1]
    prev = hist.iloc[-2]

    score = 0
    warning = ""

    if last["Close"] > last["SMA5"]:
        score += 20
    if last["SMA5"] > last["SMA20"]:
        score += 20
    if last["Volume"] > last["VOLMA20"]:
        score += 20
    if last["Close"] > prev["Close"]:
        score += 20
    if df_today["ChangePct"] > 10:
        score += 10
    if df_today["Volume"] > last["VOLMA20"]:
        score += 10

    if df_today["ChangePct"] > 25:
        warning = "⚠️"

    return score, warning


# =========================
# BACKTEST (INI JUGA BALIK)
# =========================
def backtest(hist):

    hist = prepare(hist)

    returns = []

    for i in range(20, len(hist)-1):

        today = hist.iloc[i]
        nxt = hist.iloc[i+1]

        ret = (nxt["High"] - today["Close"]) / today["Close"]
        returns.append(ret)

    if len(returns) == 0:
        return 0, 0

    winrate = sum(1 for r in returns if r > 0.015) / len(returns)
    ev = np.mean(returns)

    return winrate * 100, ev * 100


# =========================
# SCREENER ENGINE (FULL LOGIC)
# =========================
def run_screener(df_today, hist_data):

    results = []

    for _, row in df_today.iterrows():

        ticker = row["Ticker"]

        if ticker not in hist_data:
            continue

        hist = hist_data[ticker]

        # SIGNAL
        if not is_signal(df_today, row, hist):
            continue

        # SCORE
        sc, warn = score(row, hist)

        # BACKTEST
        wr, ev = backtest(hist)

        probability = (sc * 0.4) + (wr * 0.6)

        results.append({
            "Ticker": ticker,
            "Price": row["Close"],
            "Score": sc,
            "Winrate": round(wr, 2),
            "EV": round(ev, 2),
            "Probability": round(probability, 2),
            "Warning": warn
        })

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values("Probability", ascending=False)
        df.insert(0, "Rank", range(1, len(df)+1))

    return df


# =========================
# UI
# =========================
st.title("Hybrid Screener FIXED (Copy Paste + Yahoo + Signal + Backtest)")

text = st.text_area("Paste data hari ini")

if st.button("RUN"):

    df_today = parse_today(text)

    tickers = df_today["Ticker"].tolist()

    hist = get_history(tickers)

    result = run_screener(df_today, hist)

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

        msg = "<b>🚨 SIGNAL LIST 🚨</b>\n\n"

        for i, r in enumerate(df.iterrows(), 1):
            row = r[1]
            msg += f"{i}. {row['Ticker']} {row['Warning']} | P:{row['Price']} | S:{row['Score']}\n"

        send_telegram(msg)
        st.success("sent")
