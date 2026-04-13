import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Hitung Persentase Saham")

ticker = st.text_input("Ticker (contoh: BBCA)")

if ticker:
    ticker = ticker.upper() + ".JK"

    tk = yf.Ticker(ticker)
    df = tk.history(period="5d")

    if len(df) >= 2:
        prev_close = df["Close"].iloc[-2]
        today = df.iloc[-1]

        high = today["High"]
        low = today["Low"]
        close = today["Close"]

        high_pct = (high - prev_close) / prev_close * 100
        low_pct = (low - prev_close) / prev_close * 100
        close_pct = (close - prev_close) / prev_close * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("High %", f"{high_pct:.2f}%")
        col2.metric("Low %", f"{low_pct:.2f}%")
        col3.metric("Close %", f"{close_pct:.2f}%")

    else:
        st.error("Data tidak cukup")
