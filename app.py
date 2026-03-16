import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia")

# ===============================
# LIST TICKER
# ===============================

TICKERS = [
"AALI.JK","ABBA.JK","ABDA.JK","ABMM.JK","ACES.JK",
"ADRO.JK","AKRA.JK","AMRT.JK","ANTM.JK",
"ASII.JK","BBCA.JK","BBNI.JK","BBRI.JK","BMRI.JK",
"ICBP.JK","INDF.JK","MDKA.JK","PTBA.JK","TLKM.JK"
]

# ===============================
# WINRATE PER TICKER
# ===============================

def calculate_winrate(ticker):

    try:
        df = yf.download(ticker, period="2y", progress=False)
    except:
        return None

    if df is None or df.empty:
        return None

    df["SMA5"] = df["Close"].rolling(5).mean()
    df = df.dropna()

    total = 0
    win = 0

    for i in range(5, len(df)-1):

        close = float(df["Close"].iloc[i])
        prev_close = float(df["Close"].iloc[i-1])

        volume = float(df["Volume"].iloc[i])
        prev_volume = float(df["Volume"].iloc[i-1])

        sma5 = float(df["SMA5"].iloc[i])

        next_high = float(df["High"].iloc[i+1])

        value = close * volume

        signal = (
            volume > prev_volume and
            prev_close < close and
            close > sma5 and
            value > 5000000000
        )

        if not signal:
            continue

        total += 1

        gain = (next_high - close) / close * 100

        if gain >= 1.5:
            win += 1

    if total == 0:
        return None

    return round((win/total)*100,2)

# ===============================
# SCREENER
# ===============================

def run_screener():

    hasil = []

    progress = st.progress(0)
    status = st.empty()

    data = yf.download(
        TICKERS,
        period="250d",
        group_by="ticker",
        threads=True,
        progress=False
    )

    total = len(TICKERS)

    for i,ticker in enumerate(TICKERS):

        status.text(f"Scanning {ticker} ({i+1}/{total})")

        try:
            df = data[ticker].copy()
        except:
            continue

        if df is None or df.empty:
            continue

        # =========================
        # INDICATOR
        # =========================

        df["SMA5"] = df["Close"].rolling(5).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()

        df["EMA10"] = df["Close"].ewm(span=10).mean()
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()

        df["BB_MID"] = df["Close"].rolling(20).mean()
        df["BB_STD"] = df["Close"].rolling(20).std()

        df["BB_UP"] = df["BB_MID"] + df["BB_STD"]*2
        df["BB_LOW"] = df["BB_MID"] - df["BB_STD"]*2

        df["BBW"] = (df["BB_UP"] - df["BB_LOW"]) / df["BB_MID"]

        df = df.dropna()

        if len(df) < 10:
            continue

        today = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(today["Close"])
        prev_close = float(prev["Close"])

        volume = float(today["Volume"])
        prev_volume = float(prev["Volume"])

        high = float(today["High"])
        low = float(today["Low"])
        open_price = float(today["Open"])

        prev_high = float(prev["High"])
        prev_low = float(prev["Low"])

        sma5 = float(today["SMA5"])
        sma50 = float(today["SMA50"])
        sma200 = float(today["SMA200"])

        ema10 = float(today["EMA10"])
        ema20 = float(today["EMA20"])
        ema50 = float(today["EMA50"])

        bb_mid = float(today["BB_MID"])
        bb_low = float(today["BB_LOW"])
        prev_bb_low = float(prev["BB_LOW"])

        bbw = float(today["BBW"])

        value = close * volume

        llv5 = df["Low"].iloc[-6:-1].min()

        # =========================
        # SCREENER V1
        # =========================

        V1 = (
            volume > prev_volume and
            prev_close < close and
            close > sma5 and
            value > 5000000000
        )

        # =========================
        # SCREENER V2
        # =========================

        V2 = (
            volume > prev_volume and
            prev_close < close and
            close > sma5 and
            value > 5000000000 and
            (high/prev_close) >= 1.10
        )

        # =========================
        # MA50
        # =========================

        MA50 = (
            llv5 > sma50 and
            close >= sma50*0.99 and
            close <= sma50*1.02 and
            value > 1000000000
        )

        # =========================
        # MA200
        # =========================

        MA200 = (
            llv5 > sma200 and
            close >= sma200*0.99 and
            close <= sma200*1.02 and
            value > 1000000000
        )

        # =========================
        # BBMid
        # =========================

        BBMid = (
            close >= bb_mid*0.98 and
            close <= bb_mid*1.02 and
            value > 1000000000 and
            ema10 > ema20 and
            ema20 > ema50 and
            bbw >= 0.1 and
            close > bb_mid
        )

        # =========================
        # BBRev
        # =========================

        BBRev = (
            prev_low < prev_bb_low and
            prev_close < prev_bb_low and
            close > bb_low and
            value > 1000000000 and
            volume > prev_volume and
            prev_high < high and
            close > prev_close
        )

        if V1 or V2 or MA50 or MA200 or BBMid or BBRev:

            winrate = calculate_winrate(ticker)

            hasil.append({
                "Ticker":ticker,
                "V1":V1,
                "V2":V2,
                "MA50":MA50,
                "MA200":MA200,
                "BBMid":BBMid,
                "BBRev":BBRev,
                "Close":round(close,2),
                "Value":int(value),
                "Winrate_TP1_1.5%":winrate
            })

        progress.progress((i+1)/total)

    status.text("Scan selesai")

    return pd.DataFrame(hasil)

# ===============================
# RUN
# ===============================

if st.button("Run Screener"):

    df = run_screener()

    if df.empty:
        st.warning("Tidak ada saham memenuhi kriteria")

    else:
        st.dataframe(df, use_container_width=True)
