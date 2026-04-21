import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.title("📊 Backtest Strategy + ATR SL (Hold 1 Hari)")

# ================================
# INPUT
# ================================
tickers_input = st.text_input(
    "Ticker (pisahkan koma)",
    value="BBCA.JK,TLKM.JK"
)

start_date = st.date_input("Start Date", pd.to_datetime("2020-01-01"))
end_date = st.date_input("End Date", pd.to_datetime("today"))

atr_period = st.slider("ATR Period", 5, 50, 14)
atr_mult = st.slider("ATR Multiplier", 1.0, 4.0, 2.0, 0.1)
use_partial = st.checkbox("Partial Exit", True)

# ================================
# LOAD DATA
# ================================
@st.cache_data
def load_data(tickers, start, end):
    return yf.download(
        tickers,
        start=start,
        end=end,
        group_by='ticker',
        auto_adjust=True
    )

# ================================
# ARA LIMIT (IDX RULE)
# ================================
def get_ara_limit(price):
    if price < 200:
        return 0.35
    elif price < 5000:
        return 0.25
    else:
        return 0.20

# ================================
# SIGNAL FUNCTION (FIXED)
# ================================
def is_signal(df, i):

    if i < 20:
        return False

    today = df.iloc[i]
    prev = df.iloc[i-1]

    close = today["close"]
    volume = today["volume"]

    prev_close = prev["close"]
    prev_volume = prev["volume"]

    sma5 = today["SMA5"]
    value = today["value"]
    avg_value = today["avg_value"]
    value_ratio = today["value_ratio"]
    avg_volume = today["vol_ma"]

    change_pct = (close - prev_close) / prev_close
    ara = get_ara_limit(prev_close)

    if close > 9700 or close < 50:
        return False

    if ara == 0.25 and change_pct >= 0.24:
        return False
    if ara == 0.35 and change_pct >= 0.34:
        return False

    if not (avg_value > 10_000_000_000 and avg_volume > 1_000_000):
        return False

    if not (
        volume > prev_volume and
        prev_close < close and
        close > sma5 and
        value > 10_000_000_000 and
        value_ratio > 2
    ):
        return False

    return True

# ================================
# RUN BACKTEST
# ================================
if st.button("Run Backtest"):

    tickers = [t.strip() for t in tickers_input.split(",")]
    data = load_data(tickers, start_date, end_date)

    results = []

    for ticker in tickers:

        try:
            df = data[ticker].copy()
        except:
            continue

        df = df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        df = df.reset_index()
        df.rename(columns={'Date': 'date'}, inplace=True)

        # ================================
        # FEATURE ENGINEERING
        # ================================
        df['value'] = df['close'] * df['volume']
        df['SMA5'] = df['close'].rolling(5).mean()
        df['avg_value'] = df['value'].rolling(20).mean()
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['value_ratio'] = df['value'] / df['avg_value']

        # ATR
        df['h-l'] = df['high'] - df['low']
        df['h-c'] = abs(df['high'] - df['close'].shift(1))
        df['l-c'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['h-l', 'h-c', 'l-c']].max(axis=1)
        df['atr'] = df['tr'].rolling(atr_period).mean()

        # ================================
        # BACKTEST HOLD 1 HARI
        # ================================
        for i in range(1, len(df) - 1):

            if not is_signal(df, i):
                continue

            entry_price = df.loc[i, 'close']
            atr = df.loc[i, 'atr']

            if pd.isna(atr):
                continue

            sl = entry_price - (atr * atr_mult)

            next_row = df.loc[i + 1]

            o = next_row['open']
            l = next_row['low']
            c = next_row['close']

            # GAP
            if o <= sl:
                exit_price = o
                reason = 'gap_SL'

            elif l <= sl:
                if use_partial:
                    exit_price = (0.5 * sl) + (0.5 * c)
                    reason = 'partial_SL'
                else:
                    exit_price = sl
                    reason = 'SL'

            else:
                exit_price = c
                reason = 'close_exit'

            ret = (exit_price - entry_price) / entry_price

            results.append({
                'ticker': ticker,
                'entry_date': df.loc[i, 'date'],
                'exit_date': next_row['date'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'return': ret,
                'reason': reason
            })

    results_df = pd.DataFrame(results)

    if len(results_df) > 0:

        winrate = (results_df['return'] > 0).mean()
        avg_return = results_df['return'].mean()

        equity = results_df['return'].cumsum()
        max_dd = (equity.cummax() - equity).max()

        col1, col2, col3 = st.columns(3)
        col1.metric("Winrate", f"{winrate:.2%}")
        col2.metric("Avg Return", f"{avg_return:.2%}")
        col3.metric("Max DD", f"{max_dd:.2%}")

        st.dataframe(results_df)
        st.line_chart(equity)

    else:
        st.warning("Tidak ada trade.")
