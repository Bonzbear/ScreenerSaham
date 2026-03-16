import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia")

TICKERS = [
"BBRI.JK","BBCA.JK","BMRI.JK","BBNI.JK",
"ADRO.JK","ANTM.JK","PTBA.JK","TLKM.JK",
"ASII.JK","MDKA.JK","INDF.JK","ICBP.JK"
]

# =========================
# BACKTEST FUNCTION
# =========================

def backtest_setup(df, setup):

    total = 0
    win = 0

    for i in range(200, len(df)-1):

        today = df.iloc[i]
        prev = df.iloc[i-1]
        nextd = df.iloc[i+1]

        close = float(today["Close"])
        volume = float(today["Volume"])
        prev_volume = float(prev["Volume"])

        prev_close = float(prev["Close"])
        value = close * volume

        sma5 = float(today["SMA5"])
        sma50 = float(today["SMA50"])
        sma200 = float(today["SMA200"])

        ema10 = float(today["EMA10"])
        ema20 = float(today["EMA20"])
        ema50 = float(today["EMA50"])

        bbmid = float(today["BB_MID"])
        bblow = float(today["BB_LOW"])
        bbw = float(today["BBW"])

        prev_low = float(prev["Low"])
        prev_high = float(prev["High"])
        today_high = float(today["High"])

        signal = False

        if setup == "V1":

            if (
                volume > prev_volume and
                prev_close < close and
                close > sma5 and
                value > 5000000000
            ):
                signal = True


        if setup == "MA50":

            llv5 = float(df["Low"].iloc[i-5:i].min())

            if (
                llv5 > sma50 and
                close >= sma50*0.99 and
                close <= sma50*1.02 and
                value > 1000000000
            ):
                signal = True


        if setup == "MA200":

            llv5 = float(df["Low"].iloc[i-5:i].min())

            if (
                llv5 > sma200 and
                close >= sma200*0.99 and
                close <= sma200*1.02 and
                value > 1000000000
            ):
                signal = True


        if setup == "BBMid":

            if (
                close >= bbmid*0.98 and
                close <= bbmid*1.02 and
                value > 1000000000 and
                ema10 > ema20 and
                ema20 > ema50 and
                bbw >= 0.1 and
                close > bbmid
            ):
                signal = True


        if setup == "BBRev":

            prev_bblow = float(prev["BB_LOW"])

            if (
                prev_low < prev_bblow and
                prev_close < prev_bblow and
                close > bblow and
                value > 1000000000 and
                volume > prev_volume and
                prev_high < today_high and
                close > prev_close
            ):
                signal = True


        if not signal:
            continue

        total += 1

        gain = (float(nextd["High"]) - close) / close * 100

        if gain >= 1.5:
            win += 1


    if total == 0:
        return None

    return round((win/total)*100,2)


# =========================
# SCREENER
# =========================

def run_screener():

    results = []

    progress = st.progress(0)
    status = st.empty()

    total = len(TICKERS)

    for i,ticker in enumerate(TICKERS):

        status.text(f"Scanning {ticker} ({i+1}/{total})")

        try:
            df = yf.download(ticker, period="2y", progress=False)
        except:
            continue

        if df.empty:
            continue


        df["SMA5"] = df["Close"].rolling(5).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()

        df["EMA10"] = df["Close"].ewm(span=10).mean()
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()

        df["BB_MID"] = df["Close"].rolling(20).mean()
        df["BB_STD"] = df["Close"].rolling(20).std()

        df["BB_UP"] = df["BB_MID"] + df["BB_STD"]*2
        df["BB_LOW"] = df["BB_MID"] - df["BB_STD"]*2

        df["BBW"] = (df["BB_UP"] - df["BB_LOW"]) / df["BB_MID"]

        df = df.dropna()

        if len(df) < 210:
            continue


        today = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(today["Close"])
        volume = float(today["Volume"])
        prev_volume = float(prev["Volume"])
        prev_close = float(prev["Close"])

        value = close * volume

        sma5 = float(today["SMA5"])
        sma50 = float(today["SMA50"])
        sma200 = float(today["SMA200"])

        ema10 = float(today["EMA10"])
        ema20 = float(today["EMA20"])
        ema50 = float(today["EMA50"])

        bbmid = float(today["BB_MID"])
        bblow = float(today["BB_LOW"])
        bbw = float(today["BBW"])

        prev_low = float(prev["Low"])
        prev_high = float(prev["High"])
        today_high = float(today["High"])

        signals = []

        # V1
        if (
            volume > prev_volume and
            prev_close < close and
            close > sma5 and
            value > 5000000000
        ):
            signals.append("V1")


        llv5 = float(df["Low"].iloc[-6:-1].min())


        # MA50
        if (
            llv5 > sma50 and
            close >= sma50*0.99 and
            close <= sma50*1.02 and
            value > 1000000000
        ):
            signals.append("MA50")


        # MA200
        if (
            llv5 > sma200 and
            close >= sma200*0.99 and
            close <= sma200*1.02 and
            value > 1000000000
        ):
            signals.append("MA200")


        # BBMid
        if (
            close >= bbmid*0.98 and
            close <= bbmid*1.02 and
            value > 1000000000 and
            ema10 > ema20 and
            ema20 > ema50 and
            bbw >= 0.1 and
            close > bbmid
        ):
            signals.append("BBMid")


        # BBRev
        prev_bblow = float(prev["BB_LOW"])

        if (
            prev_low < prev_bblow and
            prev_close < prev_bblow and
            close > bblow and
            value > 1000000000 and
            volume > prev_volume and
            prev_high < today_high and
            close > prev_close
        ):
            signals.append("BBRev")


        if len(signals) == 0:
            progress.progress((i+1)/total)
            continue


        winrates = []

        for s in signals:

            w = backtest_setup(df, s)

            if w is not None:
                winrates.append(w)

        if len(winrates) == 0:
            winrate = None
        else:
            winrate = round(sum(winrates)/len(winrates),2)


        results.append({

            "Ticker":ticker,
            "Signal":", ".join(signals),
            "Close":round(close,2),
            "Winrate":winrate

        })

        progress.progress((i+1)/total)


    status.text("Scan selesai")

    df = pd.DataFrame(results)

    if not df.empty:

        df["Winrate"] = df["Winrate"].fillna(0)

        df["Probability_%"] = df["Winrate"] * 0.7

        df = df.sort_values(
            by=["Probability_%","Winrate"],
            ascending=False
        )

        df.insert(0,"Rank",range(1,len(df)+1))

    return df


# =========================
# BUTTON
# =========================

if st.button("Run Screener"):

    df = run_screener()

    if df.empty:
        st.warning("Tidak ada saham memenuhi kriteria")
    else:
        st.dataframe(df,use_container_width=True)
