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


def format_telegram(df):
    if df.empty:
        return "Tidak ada sinyal hari ini"

    indonesia_tz = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(indonesia_tz).strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n"
    msg += "━━━━━━━━━━━━━━\n"

    for i, (_, row) in enumerate(df.head(5).iterrows(), 1):
        warning = row["Warning"] if "Warning" in df.columns else ""
        ticker = row["Ticker"].replace(".JK", "")
        msg += f"<b>{i}. {ticker} {warning}</b>\n"

    msg += (
        "\n<b>⚠️ Risiko tinggi / volatilitas tinggi</b>\n"
        "<b>📌 Entry:</b> Pre-closing\n"
        "<b>🎯 TP:</b> fleksibel (>1%)\n"
        "<b>🛑 CL:</b> bawah support\n"
    )

    return msg


# =========================
# PARSE COPY PASTE DATA
# =========================
def load_pasted_data(text):

    rows = []
    lines = text.strip().split("\n")

    for line in lines[1:]:  # skip header
        parts = re.split(r"\t+", line.strip())

        if len(parts) < 5:
            continue

        code = parts[0]
        last = parts[1]
        change_pct = parts[2]
        value = parts[3]
        volume = parts[4]

        def parse_num(x):
            x = x.replace(",", "").strip()

            if "B" in x:
                return float(x.replace("B", "")) * 1e9
            elif "M" in x:
                return float(x.replace("M", "")) * 1e6
            elif "K" in x:
                return float(x.replace("K", "")) * 1e3
            return float(x)

        rows.append({
            "Ticker": code + ".JK",
            "Close": float(last.replace(",", "")),
            "Change_pct": float(change_pct.replace("%", "").replace(",", ".")),
            "Value": parse_num(value),
            "Volume": parse_num(volume),
            "Open": np.nan,
            "High": np.nan,
            "Low": np.nan
        })

    return pd.DataFrame(rows)


# =========================
# YAHOO HISTORY (H-1)
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):

    raw = yf.download(
        tickers=" ".join(tickers),
        period="5y",
        group_by="ticker",
        progress=False
    )

    indonesia_tz = pytz.timezone("Asia/Jakarta")
    today = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

    clean = {}

    for t in tickers:

        if t not in raw:
            continue

        df = raw[t].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()

        df = df[df.index < today]
        df = df.sort_index()

        clean[t] = df

    return clean


# =========================
# MERGE TODAY + HISTORY
# =========================
def merge_today(hist, df_today):

    indonesia_tz = pytz.timezone("Asia/Jakarta")
    today = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

    merged = {}

    for ticker, h in hist.items():

        row = df_today[df_today["Ticker"] == ticker]
        if row.empty:
            continue

        row = row.iloc[0]

        today_df = pd.DataFrame([{
            "Open": row["Close"],
            "High": row["Close"],
            "Low": row["Close"],
            "Close": row["Close"],
            "Volume": row["Volume"],
            "Value": row["Value"]
        }], index=[today])

        df = pd.concat([h, today_df]).sort_index()
        merged[ticker] = df

    return merged


# =========================
# PREPARE DATA
# =========================
def prepare_data(df):

    df = df.copy().sort_index()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["VOLMA5"] = df["Volume"].rolling(5).mean()

    df["AvgValue20"] = df["Value"].rolling(20).mean()
    df["ValueRatio"] = df["Value"] / df["AvgValue20"]

    df["VWAP"] = (
        df["Volume"] * (df["High"] + df["Low"] + df["Close"]) / 3
    ).cumsum() / df["Volume"].cumsum()

    return df.dropna()


# =========================
# SIGNAL
# =========================
def is_signal(df, i):

    if i < 2:
        return False

    today = df.iloc[i]
    prev = df.iloc[i-1]

    change_pct = (today["Close"] - prev["Close"]) / prev["Close"]

    if today["Close"] > 6500 or today["Close"] < 100:
        return False

    if not (
        today["Volume"] > prev["Volume"] and
        today["Close"] > today["SMA5"] and
        today["Value"] > 1e10 and
        today["ValueRatio"] > 2
    ):
        return False

    if change_pct > 0.25:
        return False

    return True


# =========================
# SCORE
# =========================
def calculate_score(df):

    today = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0
    warning = ""

    if prev["Close"] < prev["SMA5"]: score += 125
    if today["Volume"] > today["VOLMA20"]: score += 125
    if today["Volume"] > today["VOLMA5"]: score += 125
    if today["Close"] > today["VWAP"]: score += 125
    if today["Low"] > prev["Low"]: score += 125
    if today["High"] > prev["High"]: score += 125

    if today["Close"] > today["Open"]:
        score += 100

    return score, warning


# =========================
# BACKTEST
# =========================
def backtest_ev(df):

    returns = []

    for i in range(20, len(df)-1):

        if not is_signal(df, i):
            continue

        today = df.iloc[i]
        next_day = df.iloc[i+1]

        ret = (next_day["High"] - today["Close"]) / today["Close"]
        returns.append(ret)

    if not returns:
        return 0, 0

    winrate = sum(r >= 0.015 for r in returns) / len(returns)
    ev = sum(returns) / len(returns)

    return round(winrate * 100, 2), round(ev * 100, 2)


# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for ticker, df in data.items():

        df = prepare_data(df)

        if len(df) < 30:
            continue

        if not is_signal(df, len(df)-1):
            continue

        score, warning = calculate_score(df)

        winrate, ev = backtest_ev(df)

        probability = (score * 0.3) + (winrate * 0.7)

        results.append({
            "Ticker": ticker,
            "Price": df["Close"].iloc[-1],
            "Warning": warning,
            "Score": score,
            "Winrate (%)": winrate,
            "Probability (%)": round(probability, 2),
            "EV (%)": ev
        })

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values("Probability (%)", ascending=False)
        df.insert(0, "Rank", range(1, len(df)+1))

    return df


# =========================
# UI
# =========================
st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia (Paste Input Mode)")

text_input = st.text_area("Paste data market hari ini di sini")

if st.button("▶️ Run Screener"):

    if not text_input:
        st.error("Data kosong")
        st.stop()

    df_today = load_pasted_data(text_input)
    tickers = df_today["Ticker"].tolist()

    hist = get_data(tickers)
    merged = merge_today(hist, df_today)

    st.session_state["df"] = run_screener(merged)

    st.success("Selesai")


# =========================
# DISPLAY
# =========================
if "df" in st.session_state:

    df_show = st.session_state["df"].copy()
    df_show["Kirim"] = False

    edited = st.data_editor(df_show, use_container_width=True)

    st.session_state["edited"] = edited


# =========================
# TELEGRAM
# =========================
if "edited" in st.session_state:

    if st.button("📤 Telegram"):

        selected = st.session_state["edited"]
        selected = selected[selected["Kirim"] == True]

        if selected.empty:
            st.warning("Pilih saham dulu")
        else:
            msg = format_telegram(selected)
            send_telegram(msg)
            st.success("Terkirim")
