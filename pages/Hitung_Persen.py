import streamlit as st
import yfinance as yf
import pandas as pd
import math

st.title("Hitung Persentase Saham (Multi Ticker)")

# Input multi ticker
tickers_input = st.text_area(
    "Masukkan Ticker (pisah koma)",
    placeholder="BBCA, TLKM, BBRI"
)

# Format ticker → auto .JK
def format_ticker(t):
    t = t.strip().upper()
    if not t.endswith(".JK"):
        t += ".JK"
    return t

# Format aman untuk metric
def safe_format(x):
    try:
        return f"{float(x):.2f}%"
    except:
        return "-"

if st.button("Ambil Data"):

    if not tickers_input.strip():
        st.warning("Masukkan minimal 1 ticker")
        st.stop()

    tickers = [format_ticker(t) for t in tickers_input.split(",")]

    results = []

    for ticker in tickers:
        try:
            # Ambil 5 hari (untuk handle weekend/libur)
            df = yf.download(ticker, period="5d", interval="1d", progress=False)

            if df.empty or len(df) < 2:
                continue

            # Ambil 2 hari trading terakhir
            prev_close = df["Close"].iloc[-2]
            today = df.iloc[-1]

            high = today["High"]
            low = today["Low"]
            close = today["Close"]

            # Hitung %
            high_pct = (high - prev_close) / prev_close * 100
            low_pct = (low - prev_close) / prev_close * 100
            close_pct = (close - prev_close) / prev_close * 100

            # Skip kalau data aneh (NaN)
            if any(math.isnan(x) for x in [high_pct, low_pct, close_pct]):
                continue

            results.append({
                "Ticker": ticker.replace(".JK", ""),
                "High %": float(high_pct),
                "Low %": float(low_pct),
                "Close %": float(close_pct)
            })

        except:
            continue

    # ==========================
    # OUTPUT
    # ==========================
    if results:
        df_result = pd.DataFrame(results)

        # Tambahan: Range %
        df_result["Range %"] = df_result["High %"] - df_result["Low %"]

        # Sort biar lebih berguna
        df_result = df_result.sort_values(by="Range %", ascending=False)

        st.subheader("Hasil")
        st.dataframe(df_result)

        st.divider()

        # Detail per saham
        for _, row in df_result.iterrows():
            st.subheader(row["Ticker"])

            col1, col2, col3 = st.columns(3)
            col1.metric("High %", safe_format(row["High %"]))
            col2.metric("Low %", safe_format(row["Low %"]))
            col3.metric("Close %", safe_format(row["Close %"]))

            # Insight otomatis
            if row["High %"] > 3 and row["Close %"] < 1:
                st.warning("Rejection (potensi distribusi)")
            elif row["Low %"] < -3 and row["Close %"] > 0:
                st.success("Absorption (potensi naik)")

            st.divider()

    else:
        st.error("Tidak ada data valid (cek ticker / market libur)")
