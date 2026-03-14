import streamlit as st
import yfinance as yf
import pandas as pd

st.title("Screener Saham Indonesia")

ticker_input = st.text_input(
"Masukkan ticker (contoh: BBRI,ADRO,PTBA)"
)

if st.button("Jalankan Backtest"):

    tickers=[x.strip().upper()+".JK" for x in ticker_input.split(",")]

    hasil=[]

    for ticker in tickers:

        df=yf.download(ticker,period="1y",progress=False)

        if df.empty:
            continue

        df.columns=df.columns.get_level_values(0)

        df["SMA5"]=df["Close"].rolling(5).mean()

        df=df.reset_index()

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
                "Ticker":ticker,
                "Date":today["Date"],
                "Next High %":round(gain,2)
            })

    df=pd.DataFrame(hasil)

    if df.empty:
        st.write("Tidak ada sinyal")
    else:

        st.dataframe(df)

        total=len(df)

        tp1=(df["Next High %"]>=1).sum()
        tp2=(df["Next High %"]>=2).sum()

        st.write("Total Signal:",total)
        st.write("TP 1%:",tp1)
        st.write("TP 2%:",tp2)
