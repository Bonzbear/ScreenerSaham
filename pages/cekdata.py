import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import pytz

st.set_page_config(layout="wide")
st.title("DEBUG SAHAM - INDS")

TICKER = "INDS.JK"


# =========================
# LOAD CSV
# =========================
def load_csv_today(file):

    file.seek(0)

    try:
        df = pd.read_csv(file, encoding="utf-8")
    except:
        file.seek(0)
        df = pd.read_csv(file, encoding="latin-1")

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

    df["Volume"] = df["Volume"] * 100
    df["Ticker"] = df["Code"] + ".JK"
    df["Close"] = df["Last"]
    df["Value"] = df["Value_M"] * 1_000_000

    return df[df["Ticker"] == TICKER]


# =========================
# YAHOO (H-1)
# =========================
def get_yahoo():

    raw = yf.download(
        tickers=TICKER,
        period="6mo",
        progress=False
    )

    df = raw.copy()

    # rapikan index
    df.index = pd.to_datetime(df.index).tz_localize(None)

    indonesia_tz = pytz.timezone("Asia/Jakarta")
    today = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

    # ambil H-1
    df = df[df.index < today]

    # ambil kolom penting
    df = df[["Open","High","Low","Close","Volume"]].copy()

    # tambahkan Value
    df["Value"] = df["Close"] * df["Volume"]

    # normalize index
    df.index = df.index.normalize()

    return df


# =========================
# PREPARE
# =========================
def prepare(df):

    df = df.copy()
    df = df.sort_index()

    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["AvgValue20"] = df["Value"].rolling(20).mean()
    df["ValueRatio"] = df["Value"] / df["AvgValue20"]

    return df


# =========================
# UI
# =========================
uploaded_file = st.file_uploader("Upload CSV")

if uploaded_file:

    # =========================
    # CSV
    # =========================
    df_today = load_csv_today(uploaded_file)

    if df_today.empty:
        st.error("INDS tidak ada di CSV")
        st.stop()

    row = df_today.iloc[0]

    st.subheader("CSV (Hari Ini)")
    st.write(row)

    # =========================
    # YAHOO
    # =========================
    df_hist = get_yahoo()

    st.subheader("Yahoo (H-1)")
    st.dataframe(df_hist.tail(5))

    # =========================
    # MERGE (FIX FINAL)
    # =========================
    indonesia_tz = pytz.timezone("Asia/Jakarta")
    today = pd.Timestamp.now(tz=indonesia_tz).tz_localize(None).normalize()

    today_row = pd.DataFrame([{
        "Open": row["Open"],
        "High": row["High"],
        "Low": row["Low"],
        "Close": row["Close"],
        "Volume": row["Volume"],
        "Value": row["Value"]
    }], index=[today])

    # samakan struktur
    df_hist = df_hist[["Open","High","Low","Close","Volume","Value"]]

    # CONCAT AMAN
    df = pd.concat([df_hist, today_row], axis=0)

    # rapikan
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    st.subheader("SETELAH MERGE")
    st.dataframe(df.tail(5))

    # =========================
    # PREPARE
    # =========================
    df = prepare(df)

    st.subheader("SETELAH PREPARE")
    st.dataframe(df.tail(5))

    # =========================
    # DEBUG KONDISI
    # =========================
    st.subheader("DEBUG KONDISI SIGNAL")

    today = df.iloc[-1]
    prev = df.iloc[-2]

    debug = {
        "close>prev": bool(today["Close"] > prev["Close"]),
        "volume>prev": bool(today["Volume"] > prev["Volume"]),
        "close>sma5": bool(today["Close"] > today["SMA5"]),
        "value>10B": bool(today["Value"] > 10_000_000_000),
        "avg_value>10B": bool(today["AvgValue20"] > 10_000_000_000),
        "avg_vol>1jt": bool(today["VOLMA20"] > 1_000_000)
    }

    st.write(debug)
