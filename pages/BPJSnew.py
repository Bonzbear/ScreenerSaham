import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np

TOKEN = 
CHAT_ID = 
TICKERS = 

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
        "TP fleksibel (bisa >1.5% / ARA)\n\n"
        "<b>🛑 Risiko</b>\n"
        "CL jika bertahan di bawah support hingga penutupan\n\n"
        "<b>ℹ️ Disclaimer</b>\n"
        "Bukan rekomendasi investasi. Lakukan analisa mandiri.\n"
    )

    return msg

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
# DATA
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
# SCORE
# =========================
def calculate_score(df):

    today = df.iloc[-1]
    prev = df.iloc[-2]

    open_ = float(today["Open"])
    high = float(today["High"])
    low = float(today["Low"])
    close = float(today["Close"])
    warning = ""
    score = 0

    if float(prev["Close"]) < float(prev["SMA5"]): score += 125
    if float(today["Volume"]) > float(today["VOLMA20"]): score += 125
    if float(today["Volume"]) > float(today["VOLMA5"]): score += 125
    if float(today["Low"]) > float(prev["Low"]): score += 125
    if float(today["High"]) > float(prev["High"]): score += 125
    if (open_ - low) > (high - close): score += 125
    if float(today["Close"]) > float(today["VWAP"]): score += 125
    if float(prev["Close"]) < float(prev["VWAP"]): score += 125

    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    if body > 0 and upper_wick > body * 1.5:
        score -= 100
        warning = "⚠️"
 
    return score, warning


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
    
    if close > 9700 or close < 50:
        return False

    if ara == 0.25 and change_pct >= 0.24:
        return False
    if ara == 0.35 and change_pct >= 0.34:
        return False

    if not (avg_value > 5_000_000_000 and avg_volume > 1_000_000):
        return False

    if not (
        volume > prev_volume and
        prev_close < close and
        close > sma5 and
        value > 5_000_000_000 and
        value_ratio > 2
    ):
        return False

    return True

# =========================
# BACKTEST (INSTITUTIONAL)
# =========================
def backtest_window(df):
    returns = []

    for i in range(20, len(df)-1):
        if not is_signal(df.iloc[:i+1], i):
            continue

        close_today = df.iloc[i]["Close"]
        high_next = df.iloc[i+1]["High"]

        ret = (high_next - close_today) / close_today
        returns.append(ret)

    return returns


def compute_metrics(returns):
    if len(returns) == 0:
        return None

    returns = np.array(returns)

    winrate = np.mean(returns >= 0.015)
    ev = np.mean(returns)

    sharpe = np.mean(returns) / (np.std(returns) + 1e-9)

    equity = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min()

    return {
        "trades": len(returns),
        "winrate": winrate * 100,
        "ev": ev * 100,
        "sharpe": sharpe,
        "max_dd": max_dd * 100
    }


def walk_forward_backtest(df, train_size=504, test_size=252):

    all_results = []
    start = 0

    while True:
        train_end = start + train_size
        test_end = train_end + test_size

        if test_end > len(df):
            break

        test_df = df.iloc[train_end:test_end]

        returns = backtest_window(test_df)
        metrics = compute_metrics(returns)

        if metrics and metrics["trades"] >= 30:
            all_results.append(metrics)

        start += test_size

    return all_results


def aggregate_results(results):
    if not results:
        return None

    return {
        "winrate": np.mean([r["winrate"] for r in results]),
        "ev": np.mean([r["ev"] for r in results]),
        "sharpe": np.mean([r["sharpe"] for r in results]),
        "drawdown": np.min([r["max_dd"] for r in results])
    }

# =========================
# SCREENER
# =========================
MAX_SCORE = 1000

def run_screener(data):

    results = []

    for ticker in TICKERS:

        try:
            df = data[ticker].copy()
        except:
            continue

        if df.empty:
            continue

        df = prepare_data(df)

        if len(df) < 300:
            continue

        if not is_signal(df, len(df)-1):
            continue

        score, warning = calculate_score(df)
        score_pct = (score / MAX_SCORE) * 100

        wf = walk_forward_backtest(df)
        agg = aggregate_results(wf)

        if not agg:
            continue

        winrate = agg["winrate"]
        ev = agg["ev"]
        sharpe = agg["sharpe"]

        probability = (
            score_pct * 0.25 +
            winrate * 0.5 +
            max(0, sharpe) * 10
        )

        results.append({
            "Ticker": ticker,
            "Warning": warning,
            "Score (%)": round(score_pct,2),
            "Winrate (%)": round(winrate,2),
            "Sharpe": round(sharpe,2),
            "Probability (%)": round(probability,2),
            "EV (%)": round(ev,2)
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

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("▶️ Run Screener"):

        with st.spinner("Scanning + Backtesting..."):
            data = get_data(TICKERS)
            df = run_screener(data)

        if df.empty:
            st.warning("Tidak ada saham")
        else:
            st.session_state["df"] = df
            st.success(f"{len(df)} saham ditemukan")

with col2:
    if st.button("🔄 Clear Cache"):
        st.cache_data.clear()
        st.success("Cache dihapus")

with col3:
    key = st.text_input("Key", type="password")

    if key == "rahasia123":
        if st.button("📤 Telegram"):
            if "df" not in st.session_state:
                st.error("Run dulu")
            else:
                msg = format_telegram(st.session_state["df"])
                send_telegram(msg)
                st.success("Terkirim")
    else:
        st.caption("Akses terbatas")

if "df" in st.session_state:
    st.dataframe(st.session_state["df"], use_container_width=True)
