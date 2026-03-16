import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Screener Saham Indonesia")

menu = st.sidebar.selectbox(
    "Menu",
    ["Screener","Backtest","Winrate Analyzer"]
)

# =====================================
# LIST TICKER (ubah sesuai kebutuhan)
# =====================================

TICKERS = [
"BBRI.JK","BBCA.JK","BMRI.JK","TLKM.JK",
"ADRO.JK","PTBA.JK","ASII.JK","ICBP.JK",
"INDF.JK","UNTR.JK","ANTM.JK","MDKA.JK"
]

# =====================================
# FUNCTION SCREENER
# =====================================

def run_screener():

    hasil=[]

    for ticker in TICKERS:

        df=yf.download(ticker,period="60d",progress=False)

        if df.empty:
            continue

        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()

        df=df.dropna()

        today=df.iloc[-1]
        prev=df.iloc[-2]

        close=float(today["Close"])
        prev_close=float(prev["Close"])

        volume=float(today["Volume"])
        prev_volume=float(prev["Volume"])

        sma5=float(today["SMA5"])

        value=close*volume

        signal=(
            volume>prev_volume and
            prev_close<close and
            close>sma5 and
            value>5000000000
        )

        if signal:

            hasil.append({
                "Ticker":ticker,
                "Close":round(close,2),
                "Volume":int(volume),
                "Value":int(value)
            })

    return pd.DataFrame(hasil)

# =====================================
# FUNCTION BACKTEST
# =====================================

def run_backtest(ticker):

    ticker=ticker.upper()+".JK"

    df=yf.download(ticker,period="2y",progress=False)

    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    df["SMA5"]=df["Close"].rolling(5).mean()

    df=df.dropna().reset_index()

    hasil=[]

    for i in range(5,len(df)-1):

        today=df.iloc[i]
        prev=df.iloc[i-1]
        tomorrow=df.iloc[i+1]

        close=float(today["Close"])
        prev_close=float(prev["Close"])

        volume=float(today["Volume"])
        prev_volume=float(prev["Volume"])

        sma5=float(today["SMA5"])

        value=close*volume

        signal=(
            volume>prev_volume and
            prev_close<close and
            close>sma5 and
            value>5000000000
        )

        if not signal:
            continue

        gain=(tomorrow["High"]-close)/close*100

        hasil.append({
            "Date":today["Date"],
            "Next High %":round(gain,2)
        })

    return pd.DataFrame(hasil)

# =====================================
# FUNCTION WINRATE ANALYZER
# =====================================

def run_winrate_analyzer(tickers):

    results=[]

    for ticker in tickers:

        df=yf.download(ticker,period="2y",progress=False)

        if df.empty:
            continue

        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()
        df["SMA20"]=df["Close"].rolling(20).mean()
        df["VolMA20"]=df["Volume"].rolling(20).mean()

        df=df.dropna().reset_index()

        for i in range(20,len(df)-1):

            today=df.iloc[i]
            prev=df.iloc[i-1]
            tomorrow=df.iloc[i+1]

            close=today["Close"]
            prev_close=prev["Close"]

            volume=today["Volume"]
            prev_volume=prev["Volume"]

            value=close*volume

            signal=(
                volume>prev_volume and
                prev_close<close and
                close>today["SMA5"] and
                value>5000000000
            )

            if not signal:
                continue

            gain=(tomorrow["High"]-close)/close*100

            results.append({

                "ticker":ticker,
                "gain":gain,
                "trend":close>today["SMA20"],
                "breakout":close>prev["High"],
                "volume_spike":volume>today["VolMA20"],
                "range":today["High"]/today["Low"]>1.03

            })

    df=pd.DataFrame(results)

    return df

# =====================================
# MENU SCREENER
# =====================================

if menu=="Screener":

    st.header("Screener Saham")

    if st.button("Run Screener"):

        df=run_screener()

        if df.empty:
            st.write("Tidak ada saham memenuhi kriteria")
        else:
            st.dataframe(df)

# =====================================
# MENU BACKTEST
# =====================================

if menu=="Backtest":

    st.header("Backtest")

    ticker_input=st.text_input("Ticker","BBRI")

    if st.button("Run Backtest"):

        df=run_backtest(ticker_input)

        if df.empty:
            st.write("Tidak ada sinyal")
        else:

            st.dataframe(df)

            total=len(df)

            tp1=(df["Next High %"]>=1).sum()
            tp2=(df["Next High %"]>=2).sum()

            st.write("Total Signal:",total)
            st.write("TP1 Hit:",tp1)
            st.write("TP2 Hit:",tp2)

# =====================================
# MENU WINRATE ANALYZER
# =====================================

if menu=="Winrate Analyzer":

    st.header("Analisa Winrate dari Screener")

    ticker_input=st.text_input(
        "Masukkan ticker hasil screener",
        "BBRI,ADRO,PTBA"
    )

    if st.button("Analyze"):

        tickers=[x.strip().upper()+".JK" for x in ticker_input.split(",")]

        df=run_winrate_analyzer(tickers)

        if df.empty:

            st.write("Tidak ada data")

        else:

            filters=["trend","breakout","volume_spike","range"]

            hasil=[]

            for f in filters:

                subset=df[df[f]]

                if len(subset)>0:

                    win=(subset["gain"]>=1).sum()

                    winrate=win/len(subset)*100

                    hasil.append({
                        "Filter":f,
                        "Signals":len(subset),
                        "Winrate TP1 %":round(winrate,2)
                    })

            result_df=pd.DataFrame(hasil)

            st.dataframe(result_df)
