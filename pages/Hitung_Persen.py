import streamlit as st

st.title("Hitung Persentase Saham")

ticker = st.text_input("Ticker")

prev_close = st.number_input("Prev Close", min_value=0.0)
high = st.number_input("High", min_value=0.0)
low = st.number_input("Low", min_value=0.0)
close = st.number_input("Close", min_value=0.0)

if st.button("Hitung"):
    if prev_close == 0:
        st.error("Prev Close tidak boleh 0")
    else:
        high_pct = (high - prev_close) / prev_close * 100
        low_pct = (low - prev_close) / prev_close * 100
        close_pct = (close - prev_close) / prev_close * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("High %", f"{high_pct:.2f}%")
        col2.metric("Low %", f"{low_pct:.2f}%")
        col3.metric("Close %", f"{close_pct:.2f}%")
