import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np
import os

# =========================
# CONFIG (AMAN)
# =========================
TOKEN = "8639573881:AAHQfo4YEqjFVMMurZD4-gS416UrMbukGsE"
CHAT_ID = "-1003724967633"

MAX_SCORE = 1000

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def format_telegram(df):
    if df.empty:
        return "Tidak ada sinyal hari ini"

    indonesia_tz = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(indonesia_tz).strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n"
    msg += "━━━━━━━━━━━━━━\n"

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        warning = row["Warning"] if "Warning" in df.columns else ""
        ticker = row["Ticker"].replace(".JK", "")

        if warning:
            ticker = f"{ticker} {warning}"

        msg += f"<b>{i}. {ticker}</b>\n"

    msg += (
        "\n<b>⚠️ Risiko tinggi / volatilitas tinggi</b>\n"
        "\n<b>📌 Entry</b>\nPre-closing\n"
        "\n<b>🎯 Target</b>\nTP fleksibel\n"
        "\n<b>🛑 Risiko</b>\nCutloss jika breakdown\n"
        "\n<b>ℹ️ Disclaimer</b>\nBukan rekomendasi investasi\n"
    )

    return msg

# =========================
# LOAD CSV
# =========================
def load_csv_today(file):
    file.seek(0)

    try:
        df = pd.read_csv(file, encoding="utf-8")
    except:
        file.seek(0)
        df = pd.read_csv(file, encoding="latin-1")

    df = df[df.iloc[:,1] != "Code"]
    df = df.iloc[:, :13]

    df.columns = [
        "NO","Code","Last","Symbol","Change","Change_pct",
        "Prev","Open","High","Low","Value_M","Volume","Freq"
    ]

    num_cols = ["Last","Prev","Open","High","Low","Value_M","Volume"]

    for col in num_cols:
        df[col] = (
            df[col].astype(str)
            .str.replace(",", "")
            .str.replace("~", "")
            .str.replace("∟", "")
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Volume"] = df["Volume"] * 100
    df["Ticker"] = df["Code"] + ".JK"
    df["Close"] = df["Last"]

    return df[["Ticker","Open","High","Low","Close","Volume"]]

# =========================
# DATA
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):
    return yf.download(" ".join(tickers), period="5y", group_by="ticker", progress=False)

def merge_today(data, df_today):
    combined = {}
    today = pd.Timestamp(datetime.datetime.now(pytz.timezone("Asia/Jakarta")).date())

    for ticker in df_today["Ticker"].unique():
        if ticker not in data:
            continue

        hist = data[ticker].copy()
        if hist.empty:
            continue

        hist.index = pd.to_datetime(hist.index)
        row = df_today[df_today["Ticker"] == ticker].iloc[0]

        new_row = pd.DataFrame([{
            "Open": row["Open"],
            "High": row["High"],
            "Low": row["Low"],
            "Close": row["Close"],
            "Volume": row["Volume"]
        }], index=[today])

        if hist.index.max() == today:
            hist.loc[today] = new_row.iloc[0]
        else:
            hist = pd.concat([hist, new_row])

        combined[ticker] = hist

    return combined

# =========================
# PREPARE
# =========================
def prepare_data(df):
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["VOLMA5"] = df["Volume"].rolling(5).mean()

    df["Value"] = df["Close"] * df["Volume"]
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
    today = df.iloc[i]
    prev = df.iloc[i-1]

    change_pct = (today["Close"] - prev["Close"]) / prev["Close"]

    if not (
        today["Volume"] > prev["Volume"] and
        today["Close"] > today["SMA5"] and
        today["Value"] > 10_000_000_000 and
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

    if today["Volume"] > today["VOLMA20"]: score += 200
    if today["Close"] > today["VWAP"]: score += 200
    if today["High"] > prev["High"]: score += 200
    if today["Low"] > prev["Low"]: score += 200
    if prev["Close"] < prev["SMA5"]: score += 200

    body = abs(today["Close"] - today["Open"])
    upper = today["High"] - max(today["Close"], today["Open"])

    if upper > body * 1.5:
        warning = "⚠️"
        score -= 100

    return score, warning

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

        results.append({
            "Ticker": ticker,
            "Price": df["Close"].iloc[-1],
            "Warning": warning,
            "Score (%)": round(score / MAX_SCORE * 100, 2)
        })

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values(by="Score (%)", ascending=False)

    return df

# =========================
# UI
# =========================
st.set_page_config(layout="wide")
st.title("📈 Screener Saham Indonesia")

file = st.file_uploader("Upload CSV", type=["csv"])

if st.button("▶️ Run Screener"):

    if file is None:
        st.warning("Upload file dulu")
        st.stop()

    df_today = load_csv_today(file)
    data = get_data(df_today["Ticker"].tolist())
    data = merge_today(data, df_today)

    df = run_screener(data)

    if df.empty:
        st.warning("Tidak ada saham")
    else:
        st.session_state["df"] = df

# =========================
# DISPLAY + CHECKLIST
# =========================
if "df" in st.session_state:

    df = st.session_state["df"].copy()
    df["Kirim"] = False

    edited = st.data_editor(df, use_container_width=True, hide_index=True)

    st.session_state["edited_df"] = edited

# =========================
# TELEGRAM
# =========================
if "edited_df" in st.session_state:

    if st.button("📤 Kirim ke Telegram"):

        selected = st.session_state["edited_df"]
        selected = selected[selected["Kirim"] == True]

        if selected.empty:
            st.warning("Pilih saham dulu")
        else:
            msg = format_telegram(selected)
            send_telegram(msg)
            st.success("Berhasil dikirim 🚀")
