import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Hitung Persentase Saham (Multi Ticker)")

# Format 2 desimal aman
def fmt(x):
    try:
        return f"{float(x):.2f}%"
    except:
        return "-"

# Input multi ticker
tickers_input = st.text_area(
    "Masukkan Ticker (pisah koma, contoh: BBCA, BBRI, TLKM)"
)

# Auto jalan saat tekan Enter / isi berubah
if tickers_input:

    tickers = [t.strip().upper() + ".JK" for t in tickers_input.split(",") if t.strip()]

    results = []

    for ticker in tickers:
        try:
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
                "Ticker": ticker.replace(".JK", ""),
                "High %": high_pct,
                "Low %": low_pct,
                "Close %": close_pct
            })

        except:
            continue

    # ======================
    # OUTPUT
    # ======================
    if results:
        df_result = pd.DataFrame(results)

        # Tambahan: Range %
        df_result["Range %"] = df_result["High %"] - df_result["Low %"]

        # Sort biar informatif
        df_result = df_result.sort_values(by="Range %", ascending=False)

        st.subheader("Hasil")
        st.dataframe(df_result.style.format({
            "High %": "{:.2f}",
            "Low %": "{:.2f}",
            "Close %": "{:.2f}",
            "Range %": "{:.2f}"
        }))

        st.divider()

        # Detail per saham
        for _, row in df_result.iterrows():
            st.subheader(row["Ticker"])

            col1, col2, col3 = st.columns(3)
            col1.metric("High %", fmt(row["High %"]))
            col2.metric("Low %", fmt(row["Low %"]))
            col3.metric("Close %", fmt(row["Close %"]))

            st.divider()

    else:
        st.error("Tidak ada data valid")
