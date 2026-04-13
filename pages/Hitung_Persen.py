import yfinance as yf
import streamlit as st

tk = yf.Ticker("BBCA.JK")
df = tk.history(period="5d")

st.write(df)
