import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Screener Saham", layout="wide")

st.title("Screener Saham Indonesia")

menu = st.sidebar.selectbox(
    "Menu",
    ["Screener + Winrate", "Backtest"]
)

# =================================
# LIST TICKER (isi dengan 900 ticker Anda)
# =================================

TICKERS = [
"AALI.JK","ABBA.JK","ABDA.JK","ABMM.JK","ACES.JK",
"ADRO.JK","AGII.JK","AKRA.JK","AMRT.JK","ANTM.JK",
"ASII.JK","BBCA.JK","BBNI.JK","BBRI.JK","BMRI.JK",
"BRIS.JK","ICBP.JK","INDF.JK","MDKA.JK","PTBA.JK",
"TLKM.JK","UNTR.JK"
]

# =================================
# SCREENER
# =================================

def run_screener():

    hasil=[]

    progress_bar = st.progress(0)
    status = st.empty()

    total=len(TICKERS)

    for i,ticker in enumerate(TICKERS):

        status.text(f"Scanning {ticker} ({i+1}/{total})")

        try:
            df = yf.download(ticker, period="90d", progress=False)
        except:
            continue

        if df is None or df.empty:
            continue

        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()
        df["SMA20"]=df["Close"].rolling(20).mean()

        df["VolMA20"]=df["Volume"].rolling(20).mean()
        df["VolMA5"]=df["Volume"].rolling(5).mean()

        tp=(df["High"]+df["Low"]+df["Close"])/3
        df["VWAP"]=(tp*df["Volume"]).cumsum()/df["Volume"].cumsum()

        df=df.dropna()

        if len(df)<2:
            continue

        today=df.iloc[-1]
        prev=df.iloc[-2]

        close=float(today["Close"])
        prev_close=float(prev["Close"])

        volume=float(today["Volume"])
        prev_volume=float(prev["Volume"])

        high=float(today["High"])
        low=float(today["Low"])
        open_price=float(today["Open"])

        prev_high=float(prev["High"])
        prev_low=float(prev["Low"])

        vwap=float(today["VWAP"])
        prev_vwap=float(prev["VWAP"])

        vol_ma20=float(today["VolMA20"])
        vol_ma5=float(today["VolMA5"])

        sma5=float(today["SMA5"])

        value=close*volume

        # =====================
        # SCORING
        # =====================

        score=0

        if prev_close < prev["SMA5"]:
            score+=125

        if volume > vol_ma20:
            score+=125

        if volume > vol_ma5:
            score+=125

        if low > prev_low:
            score+=125

        if high > prev_high:
            score+=125

        if (open_price-low) > (high-close):
            score+=125

        if close > vwap:
            score+=125

        if prev_close < prev_vwap:
            score+=125

        # =====================
        # SCREENER V1
        # =====================

        V1=(
            volume > prev_volume and
            prev_close < close and
            close > sma5 and
            value > 5000000000
        )

        # =====================
        # SCREENER V2
        # =====================

        V2=(
            volume > prev_volume and
            prev_close < close and
            close > sma5 and
            value > 5000000000 and
            (high/prev_close) >= 1.10
        )

        if V1 or V2:

            hasil.append({

                "Ticker":ticker,
                "Signal_V1":V1,
                "Signal_V2":V2,
                "Score":score,
                "Close":round(close,2),
                "Value":int(value)

            })

        progress_bar.progress((i+1)/total)

    status.text("Scan selesai")

    df=pd.DataFrame(hasil)

    if not df.empty:
        df=df.sort_values("Score",ascending=False)

    return df

# =================================
# WINRATE ANALYZER
# =================================

def analyze_winrate(tickers):

    results=[]

    for ticker in tickers:

        try:
            df=yf.download(ticker,period="2y",progress=False)
        except:
            continue

        if df.empty:
            continue

        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()

        df=df.dropna().reset_index()

        for i in range(5,len(df)-1):

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

            results.append(gain)

    if len(results)==0:
        return None

    df=pd.DataFrame(results,columns=["gain"])

    total=len(df)

    tp1=(df["gain"]>=1).sum()
    tp2=(df["gain"]>=2).sum()

    winrate1=tp1/total*100
    winrate2=tp2/total*100

    return total,winrate1,winrate2

# =================================
# BACKTEST MANUAL
# =================================

def run_backtest(ticker):

    ticker=ticker.upper()+".JK"

    try:
        df=yf.download(ticker,period="2y",progress=False)
    except:
        return None

    if df.empty:
        return None

    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)

    df["SMA5"]=df["Close"].rolling(5).mean()

    df=df.dropna().reset_index()

    hasil=[]

    for i in range(5,len(df)-1):

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

        hasil.append({
            "Date":today["Date"],
            "Next High %":round(gain,2)
        })

    return pd.DataFrame(hasil)

# =================================
# MENU SCREENER
# =================================

if menu=="Screener + Winrate":

    st.header("Screener Saham")

    if st.button("Run Screener"):

        df=run_screener()

        if df.empty:

            st.warning("Tidak ada saham memenuhi kriteria")

        else:

            st.subheader("Hasil Screener")

            st.dataframe(df,use_container_width=True)

            tickers=df["Ticker"].tolist()

            result=analyze_winrate(tickers)

            if result:

                total,win1,win2=result

                st.subheader("Winrate Historis")

                st.write("Total Signal:",total)
                st.write("TP 1% Winrate:",round(win1,2),"%")
                st.write("TP 2% Winrate:",round(win2,2),"%")


# =================================
# MENU BACKTEST
# =================================

if menu=="Backtest":

    st.header("Backtest Ticker")

    ticker_input=st.text_input("Masukkan ticker","BBRI")

    if st.button("Run Backtest"):

        df=run_backtest(ticker_input)

        if df is None or df.empty:

            st.warning("Tidak ada sinyal ditemukan")

        else:

            st.dataframe(df,use_container_width=True)
