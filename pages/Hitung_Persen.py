import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Hitung Persentase Saham")

tickers_input = st.text_area("Ticker (pisah koma)")

if tickers_input:
    tickers = [t.strip().upper() + ".JK" for t in tickers_input.split(",")]

    results = []

    for ticker in tickers:
        tk = yf.Ticker(ticker)
        df = tk.history(period="5d")

        if len(df) < 2:
            continue

        prev_close = df["Close"].iloc[-2]
        today = df.iloc[-1]

        high = today["High"]
        low = today["Low"]
        close = today["Close"]

        high_pct = (high - prev_close) / prev_close * 100
        low_pct = (low - prev_close) / prev_close * 100
        close_pct = (close - prev_close) / prev_close * 100

        results.append({
            "Ticker": ticker.replace(".JK",""),
            "High %": high_pct,
            "Low %": low_pct,
            "Close %": close_pct
        })

    if results:
        st.dataframe(pd.DataFrame(results))
    else:
        st.error("Tidak ada data")
