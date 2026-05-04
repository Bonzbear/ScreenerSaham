import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz

st.set_page_config(page_title="Data Checker", layout="wide")
st.title("🔍 Data Checker (Yahoo H-1 vs CSV Hari Ini)")


# =========================
# YAHOO (H-1 ONLY)
# =========================
st.subheader("📊 Data Yahoo (H-1)")

ticker_input = st.text_input("Masukkan Ticker", "BBCA.JK")

if st.button("Ambil Data Yahoo"):

    raw = yf.download(
        tickers=ticker_input,
        period="3mo",
        progress=False
    )

    if raw.empty:
        st.error("Data tidak ditemukan")
    else:
        df = raw.copy()

        # rapikan tanggal
        df.index = pd.to_datetime(df.index).tz_localize(None)

        # ambil tanggal hari ini
        indonesia_tz = pytz.timezone("Asia/Jakarta")
        today = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

        # 🔥 FILTER H-1
        df = df[df.index < today]

        df = df.sort_index()

        st.write("### Yahoo Raw (H-1)")
        st.dataframe(df.tail(10))

        df_clean = df[["Open","High","Low","Close","Volume"]]

        st.write("### Yahoo Clean (OHLCV)")
        st.dataframe(df_clean.tail(10))

        st.write("### Info Yahoo")
        st.write({
            "Last Date (H-1)": df_clean.index.max(),
            "Last Close": df_clean["Close"].iloc[-1],
            "Last Volume": df_clean["Volume"].iloc[-1]
        })


# =========================
# CSV
# =========================
st.subheader("📂 Data CSV (Hari Ini)")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:

    file = uploaded_file

    file.seek(0)
    try:
        df = pd.read_csv(file, encoding="utf-8")
    except:
        file.seek(0)
        df = pd.read_csv(file, encoding="latin-1")

    st.write("### Raw CSV")
    st.dataframe(df.head(10))

    # =========================
    # CLEAN CSV
    # =========================
    df = df[df.iloc[:,1] != "Code"]
    df = df.iloc[:, :13]

    df.columns = [
        "NO","Code","Last","Symbol","Change","Change_pct",
        "Prev","Open","High","Low","Value_M","Volume","Freq"
    ]

    num_cols = ["Last","Prev","Open","High","Low","Value_M","Volume"]

    for col in num_cols:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "")
            .str.replace("~", "")
            .str.replace("∟", "")
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ⚠️ sesuaikan jika perlu
    df["Volume"] = df["Volume"] * 100

    df["Ticker"] = df["Code"] + ".JK"
    df["Close"] = df["Last"]
    df["Value"] = df["Value_M"] * 1_000_000

    st.write("### Clean CSV")
    st.dataframe(df[[
        "Ticker","Open","High","Low","Close","Volume","Value"
    ]].head(20))

    st.write("### Info CSV")
    st.write({
        "Jumlah Saham": len(df),
        "Sample Close": df["Close"].iloc[0],
        "Sample Volume": df["Volume"].iloc[0],
        "Sample Value": df["Value"].iloc[0]
    })


# =========================
# PERBANDINGAN
# =========================
st.subheader("⚖️ Perbandingan (Yahoo H-1 vs CSV Hari Ini)")

compare_ticker = st.text_input("Ticker untuk dibandingkan", "BBCA.JK")

if st.button("Bandingkan Data"):

    if not uploaded_file:
        st.warning("Upload CSV dulu")
    else:

        # ambil yahoo (H-1)
        raw = yf.download(
            tickers=compare_ticker,
            period="5d",
            progress=False
        )

        if raw.empty:
            st.error("Yahoo kosong")
        else:
            raw.index = pd.to_datetime(raw.index).tz_localize(None)

            indonesia_tz = pytz.timezone("Asia/Jakarta")
            today = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

            raw = raw[raw.index < today]
            raw = raw.sort_index()

            last_yahoo = raw.iloc[-1]

            row = df[df["Ticker"] == compare_ticker]

            if row.empty:
                st.error("Ticker tidak ada di CSV")
            else:
                row = row.iloc[0]

                st.write("### Yahoo (H-1)")
                st.write({
                    "Date": raw.index.max(),
                    "Close": last_yahoo["Close"],
                    "Volume": last_yahoo["Volume"]
                })

                st.write("### CSV (Hari Ini)")
                st.write({
                    "Close": row["Close"],
                    "Volume": row["Volume"],
                    "Value": row["Value"]
                })

                st.write("### Selisih")
                st.write({
                    "Close Diff": row["Close"] - last_yahoo["Close"],
                    "Volume Diff": row["Volume"] - last_yahoo["Volume"]
                })
