import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Screener Saham Indonesia")

menu = st.sidebar.selectbox(
    "Menu",
    ["Screener", "Backtest"]
)

# =========================
# LIST TICKER (contoh dulu)
# =========================

TICKERS = [
"BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK",
"ADRO.JK","PTBA.JK","ASII.JK","ICBP.JK"
]

# =========================
# SCREENER
# =========================

if menu == "Screener":

    st.header("Screener Saham")

    if st.button("Jalankan Screener"):

        hasil = []

        for ticker in TICKERS:

            df = yf.download(ticker, period="60d", progress=False)

            if df.empty:
                continue

            df.columns = df.columns.get_level_values(0)

            df["SMA5"] = df["Close"].rolling(5).mean()

            df = df.dropna()

            today = df.iloc[-1]
            prev = df.iloc[-2]

            volume = today["Volume"]
            prev_volume = prev["Volume"]

            close = today["Close"]
            prev_close = prev["Close"]

            sma5 = today["SMA5"]

            value = close * volume

            signal = (
                volume > prev_volume and
                prev_close < close and
                close > sma5 and
                value > 5000000000
            )

            if signal:

                change = (close - prev_close) / prev_close * 100

                hasil.append({
                    "Ticker": ticker,
                    "Close": round(close,2),
                    "Volume": int(volume),
                    "Value": int(value),
                    "Change %": round(change,2)
                })

        df = pd.DataFrame(hasil)

        if df.empty:
            st.write("Tidak ada saham yang memenuhi kriteria")
        else:

            df = df.sort_values("Change %", ascending=False)

            st.dataframe(df)

# =========================
# BACKTEST
# =========================

if menu == "Backtest":

    st.header("Backtest Strategi")

    ticker_input = st.text_input(
        "Masukkan ticker",
        "BBRI,ADRO,PTBA"
    )

    if st.button("Run Backtest"):

        tickers = [x.strip().upper()+".JK" for x in ticker_input.split(",")]

        hasil = []

        for ticker in tickers:

            df = yf.download(ticker, period="1y", progress=False)

            if df.empty:
                continue

            df.columns = df.columns.get_level_values(0)

            df["SMA5"] = df["Close"].rolling(5).mean()

            df = df.reset_index()

            for i in range(5,len(df)-1):

                today = df.iloc[i]
                prev = df.iloc[i-1]
                tomorrow = df.iloc[i+1]

                close = today["Close"]
                prev_close = prev["Close"]

                volume = today["Volume"]
                prev_volume = prev["Volume"]

                value = close * volume

                signal = (
                    volume > prev_volume and
                    prev_close < close and
                    close > today["SMA5"] and
                    value > 5000000000
                )

                if not signal:
                    continue

                gain = (tomorrow["High"] - close) / close * 100

                hasil.append({
                    "Ticker": ticker,
                    "Date": today["Date"],
                    "Next High %": round(gain,2)
                })

        df = pd.DataFrame(hasil)

        if df.empty:
            st.write("Tidak ada sinyal")
        else:

            st.dataframe(df)

            total = len(df)

            tp1 = (df["Next High %"] >= 1).sum()
            tp2 = (df["Next High %"] >= 2).sum()

            st.write("Total Signal:", total)
            st.write("TP 1%:", tp1)
            st.write("TP 2%:", tp2)
