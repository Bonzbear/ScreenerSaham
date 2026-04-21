import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz

TOKEN = ""
CHAT_ID = ""

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg,"parse_mode": "HTML"})

def format_telegram(df):
    no = 0

    if df.empty:
        return "Tidak ada sinyal hari ini"

    indonesia_tz = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(indonesia_tz).strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n"
    msg += "━━━━━━━━━━━━━━\n"

    for _, row in df.head(5).iterrows():
        warning = row["Warning"] if "Warning" in df.columns else ""

        ticker = row["Ticker"].replace(".JK", "")
        if warning:
            ticker += f" {warning}"

        no += 1
        msg += f"<b>{no}. {ticker}</b>\n"

    msg += "\n<b>⚠️ High Risk</b>\n"
    return msg

# =========================
# LOAD CSV (DATA HARI INI)
# =========================
def load_csv_today(file):
    try:
        df = pd.read_csv(file, encoding="utf-8")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(file, encoding="utf-16")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="latin-1")

    df = df[df["Code"] != "Code"]

    df.columns = [
        "NO","Code","Last","Symbol","Change","Change_pct",
        "Prev","Open","High","Low","Value_M","Volume","Freq"
    ]

    num_cols = ["Last","Prev","Open","High","Low","Value_M","Volume"]

    for col in num_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "")
            .str.replace("~", "")
            .str.replace("∟", "")
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Ticker"] = df["Code"] + ".JK"
    df["Close"] = df["Last"]

    return df[["Ticker","Open","High","Low","Close","Volume"]]

# =========================
# YAHOO DATA
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):
    return yf.download(
        tickers=" ".join(tickers),
        period="1y",
        group_by="ticker",
        progress=False
    )

# =========================
# MERGE CSV + YAHOO
# =========================
def merge_today(data, df_today):

    combined = {}
    today_date = pd.Timestamp.today().normalize()

    for ticker in df_today["Ticker"].unique():

        if ticker not in data:
            continue

        hist = data[ticker].copy()
        hist.reset_index(inplace=True)

        hist = hist[hist["Date"] < today_date]

        row = df_today[df_today["Ticker"] == ticker].iloc[0]

        new_row = {
            "Date": today_date,
            "Open": row["Open"],
            "High": row["High"],
            "Low": row["Low"],
            "Close": row["Close"],
            "Volume": row["Volume"]
        }

        hist = pd.concat([hist, pd.DataFrame([new_row])], ignore_index=True)
        hist.set_index("Date", inplace=True)

        combined[ticker] = hist

    return combined

# =========================
# PREPARE DATA
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
# SCORE
# =========================
def calculate_score(df):

    today = df.iloc[-1]
    prev = df.iloc[-2]

    open_ = today["Open"]
    high = today["High"]
    low = today["Low"]
    close = today["Close"]

    score = 0
    warning = ""

    if prev["Close"] < prev["SMA5"]: score += 125
    if today["Volume"] > today["VOLMA20"]: score += 125
    if today["Volume"] > today["VOLMA5"]: score += 125
    if today["Low"] > prev["Low"]: score += 125
    if today["High"] > prev["High"]: score += 125
    if (open_ - low) > (high - close): score += 125
    if today["Close"] > today["VWAP"]: score += 125
    if prev["Close"] < prev["VWAP"]: score += 125

    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    if body > 0 and upper_wick > body * 1.5:
        score -= 100
        warning = "⚠️"

    return score, warning

# =========================
# SIGNAL
# =========================
def is_signal(df):
    today = df.iloc[-1]
    prev = df.iloc[-2]

    if not (
        today["Volume"] > prev["Volume"] and
        prev["Close"] < today["Close"] and
        today["Close"] > today["SMA5"] and
        today["Value"] > 10_000_000_000 and
        today["ValueRatio"] > 2
    ):
        return False

    return True

# =========================
# SCREENER
# =========================
def run_screener(data):

    results = []

    for ticker, df in data.items():

        df = prepare_data(df)

        if len(df) < 30:
            continue

        if not is_signal(df):
            continue

        score, warning = calculate_score(df)

        results.append({
            "Ticker": ticker,
            "Price": df["Close"].iloc[-1],
            "Score": score,
            "Warning": warning
        })

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values(by="Score", ascending=False)

    return df

# =========================
# UI
# =========================
st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia")

uploaded_file = st.file_uploader("Upload CSV Hari Ini", type=["csv"])

if st.button("▶️ Run Screener"):

    if uploaded_file is None:
        st.error("Upload CSV dulu")
        st.stop()

    with st.spinner("Processing..."):

        df_today = load_csv_today(uploaded_file)

        tickers = df_today["Ticker"].unique().tolist()

        data = get_data(tickers)

        data = merge_today(data, df_today)

        df = run_screener(data)

    if df.empty:
        st.warning("Tidak ada saham")
    else:
        st.success(f"{len(df)} saham ditemukan")
        st.dataframe(df, use_container_width=True)
