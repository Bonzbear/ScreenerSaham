import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Hitung Persentase Saham (Multi Ticker)")

# Input multiple ticker (pisah koma / enter)
tickers_input = st.text_area(
    "Masukkan Ticker (contoh: BBCA, TLKM, ASII)",
    placeholder="BBCA, TLKM, BBRI"
)

def format_ticker(t):
    t = t.strip().upper()
    if not t.endswith(".JK"):
        t += ".JK"
    return t

if st.button("Ambil Data"):
    if not tickers_input.strip():
        st.warning("Masukkan minimal 1 ticker")
    else:
        tickers = [format_ticker(t) for t in tickers_input.split(",")]

        results = []

        for ticker in tickers:
            try:
                # Ambil 5 hari untuk jaga-jaga weekend/libur
                df = yf.download(ticker, period="5d", interval="1d")

                if len(df) < 2:
                    continue

                # Ambil 2 hari trading terakhir
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
                    "High %": round(high_pct, 2),
                    "Low %": round(low_pct, 2),
                    "Close %": round(close_pct, 2)
                })

            except:
                continue

        if results:
            df_result = pd.DataFrame(results)

            st.dataframe(df_result)

            # Highlight per baris
            for _, row in df_result.iterrows():
                st.subheader(row["Ticker"])

                col1, col2, col3 = st.columns(3)
                col1.metric("High %", f"{row['High %']:.2f}%")
                col2.metric("Low %", f"{row['Low %']:.2f}%")
                col3.metric("Close %", f"{row['Close %']:.2f}%")

        else:
            st.error("Tidak ada data valid")
