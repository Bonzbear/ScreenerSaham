import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np


TOKEN = "8639573881:AAHQfo4YEqjFVMMurZD4-gS416UrMbukGsE" 
CHAT_ID = "-1003724967633" 
MAX_SCORE = 1000

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

        if warning:
            ticker = f"{row['Ticker'].replace('.JK','')} {warning}"
        else:
            ticker = row["Ticker"].replace(".JK", "")

        no += 1
        msg += f"<b>{no}. {ticker}</b>\n"

    msg += (
        "\n<b>⚠️ Menandakan saham dengan risiko tinggi / volatilitas tinggi</b>\n"
        "\n<b>📌 Entry</b>\n"
        "Pre-closing (bid 3-5 tick di atas IEP)\n\n"
        "<b>🎯 Target</b>\n"
        "TP fleksibel (bisa >1%)\nSaya pribadi ambil TP 1 di +1%\n\n"
        "<b>🛑 Risiko</b>\n"
        "CL jika bertahan di bawah support hingga penutupan\n\n"
        "<b>ℹ️ Disclaimer</b>\n"
        "Bukan rekomendasi investasi. Lakukan analisa mandiri.\n"
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
            df[col]
            .astype(str)
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
# YAHOO
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):
    return yf.download(
        tickers=" ".join(tickers),
        period="5y",
        group_by="ticker",
        progress=False
    )


# =========================
# MERGE
# =========================
def merge_today(data, df_today):

    combined = {}
    indonesia_tz = pytz.timezone("Asia/Jakarta")

    # ✅ tanggal hari ini (sudah dinormalisasi & tanpa timezone)
    today_date = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

    for ticker in df_today["Ticker"].unique():

        if ticker not in data:
            continue

        hist = data[ticker].copy()

        if hist.empty:
            continue

        # ✅ FIX utama: samakan format index (WAJIB)
        hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()

        row = df_today[df_today["Ticker"] == ticker].iloc[0]

        new_values = {
            "Open": row["Open"],
            "High": row["High"],
            "Low": row["Low"],
            "Close": row["Close"],
            "Volume": row["Volume"]
        }

        last_date = hist.index.max()

        # ✅ overwrite jika sudah ada tanggal hari ini
        if last_date == today_date:
            hist.loc[last_date, ["Open", "High", "Low", "Close", "Volume"]] = list(new_values.values())
        else:
            # ✅ tambah baris baru jika belum ada
            new_row = pd.DataFrame([new_values], index=[today_date])
            hist = pd.concat([hist, new_row])

        # ✅ pastikan urutan rapi
        hist = hist.sort_index()

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
# ARA
# =========================
def get_ara_limit(price):

    if price < 200:
        return 0.35
    elif price <= 5000:
        return 0.25
    else:
        return 0.20


# =========================
# SIGNAL
# =========================
def is_signal(df, i):

    today = df.iloc[i]
    prev = df.iloc[i-1]

    close = today["Close"]
    volume = today["Volume"]

    prev_close = prev["Close"]
    prev_volume = prev["Volume"]

    sma5 = today["SMA5"]
    value = today["Value"]
    avg_value = today["AvgValue20"]
    value_ratio = today["ValueRatio"]
    avg_volume = today["VOLMA20"]

    change_pct = (close - prev_close) / prev_close
    ara = get_ara_limit(prev_close)

    if close > 6500 or close < 100:
        return False

    if ara == 0.25 and change_pct >= 0.24:
        return False
    if ara == 0.35 and change_pct >= 0.33:
        return False

    if not (avg_value > 10_000_000_000 and avg_volume > 1_000_000):
        return False

    if not (
        volume > prev_volume and
        prev_close < close and
        close > sma5 and
        value > 10_000_000_000 and
        value_ratio > 2
    ):
        return False

    return True


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
# BACKTEST + EV
# =========================
def backtest_ev(df):

    returns = []

    for i in range(20, len(df)-1):

        if not is_signal(df, i):
            continue

        today = df.iloc[i]
        next_day = df.iloc[i+1]

        close_today = today["Close"]
        high_next = next_day["High"]

        ret = (high_next - close_today) / close_today

        returns.append(ret)

    if len(returns) == 0:
        return 0, 0

    winrate = sum(1 for r in returns if r >= 0.015) / len(returns)
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
        score_pct = (score / MAX_SCORE) * 100

        winrate, ev = backtest_ev(df)

        probability = (score_pct * 0.3) + (winrate * 0.7)

        results.append({
            "Ticker": ticker,
            "Price": df["Close"].iloc[-1],
            "Warning": warning,
            "Score (%)": round(score_pct,2),
            "Winrate (%)": winrate,
            "Probability (%)": round(probability,2),
            "EV (%)": ev
        })

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values(by="Probability (%)", ascending=False)
        df.insert(0,"Rank",range(1,len(df)+1))

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
        st.session_state["data"] = data
        df = run_screener(data)

    if df.empty:
        st.warning("Tidak ada saham")
    else:
        st.session_state["df"] = df
        st.success(f"{len(df)} saham ditemukan")

# =========================
# DISPLAY + CHECKLIST
# =========================
if "df" in st.session_state:

    df_display = st.session_state["df"].copy()
    df_display["Kirim"] = False

    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True
    )

    st.session_state["edited_df"] = edited_df

# =========================
# TELEGRAM
# =========================
if "edited_df" in st.session_state:

    if st.button("📤 Telegram"):

        selected = st.session_state["edited_df"]
        selected = selected[selected["Kirim"] == True]

        if selected.empty:
            st.warning("Pilih saham dulu")
        else:
            msg = format_telegram(selected)
            send_telegram(msg)
            st.success("Terkirim")
