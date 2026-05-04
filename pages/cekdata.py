import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz

st.set_page_config(page_title="Data Checker", layout="wide")
st.title("🔍 Data Checker (Yahoo vs CSV)")


# =========================
# YAHOO DATA
# =========================
st.subheader("📊 Data dari Yahoo")

ticker_input = st.text_input("Masukkan Ticker (contoh: BBCA.JK)", "BBCA.JK")

if st.button("Ambil Data Yahoo"):

    data = yf.download(
        tickers=ticker_input,
        period="3mo",
        progress=False
    )

    if data.empty:
        st.error("Data tidak ditemukan")
    else:
        df = data.copy()

        # rapikan index
        df.index = pd.to_datetime(df.index).tz_localize(None)

        st.write("### Raw Yahoo")
        st.dataframe(df.tail(10))

        # versi clean
        df_clean = df[["Open","High","Low","Close","Volume"]].copy()

        st.write("### Clean Yahoo (OHLCV)")
        st.dataframe(df_clean.tail(10))

        st.write("### Info")
        st.write({
            "Last Date": df_clean.index.max(),
            "Last Close": df_clean["Close"].iloc[-1],
            "Last Volume": df_clean["Volume"].iloc[-1]
        })


# =========================
# CSV DATA
# =========================
st.subheader("📂 Data dari CSV")

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

    # ⚠️ SESUAIKAN JIKA PERLU
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
        "Contoh Close": df["Close"].iloc[0],
        "Contoh Volume": df["Volume"].iloc[0],
        "Contoh Value": df["Value"].iloc[0]
    })


# =========================
# PERBANDINGAN
# =========================
st.subheader("⚖️ Perbandingan (1 Ticker)")

compare_ticker = st.text_input("Ticker untuk dibandingkan (contoh: BBCA.JK)")

if st.button("Bandingkan"):

    if not uploaded_file:
        st.warning("Upload CSV dulu")
    else:

        # ambil dari yahoo
        yahoo = yf.download(
            tickers=compare_ticker,
            period="5d",
            progress=False
        )

        if yahoo.empty:
            st.error("Yahoo kosong")
        else:
            yahoo.index = pd.to_datetime(yahoo.index).tz_localize(None)

            last_yahoo = yahoo.iloc[-1]

            # ambil dari csv
            row = df[df["Ticker"] == compare_ticker]

            if row.empty:
                st.error("Ticker tidak ada di CSV")
            else:
                row = row.iloc[0]

                st.write("### Yahoo (Terakhir)")
                st.write({
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
