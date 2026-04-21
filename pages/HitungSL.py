import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.title("📊 Backtest ATR SL (Hold 1 Hari)")

# ================================
# 📥 Input
# ================================
tickers_input = st.text_input(
    "Masukkan ticker (pisahkan koma)",
    value="BBCA.JK,TLKM.JK"
)

start_date = st.date_input("Start Date", pd.to_datetime("2020-01-01"))
end_date = st.date_input("End Date", pd.to_datetime("today"))

# ================================
# ⚙️ Parameter
# ================================
atr_period = st.slider("ATR Period", 5, 50, 14)
atr_mult = st.slider("ATR Multiplier", 1.0, 4.0, 2.0, 0.1)
use_partial = st.checkbox("Partial Exit (50% SL, 50% Close)", True)

# ================================
# 📊 Load Data
# ================================
@st.cache_data
def load_data(tickers, start, end):
    return yf.download(
        tickers,
        start=start,
        end=end,
        group_by='ticker',
        auto_adjust=True   # penting → hindari split issue
    )

if st.button("Run Backtest"):

    tickers = [t.strip() for t in tickers_input.split(",")]
    data = load_data(tickers, start_date, end_date)

    all_results = []

    for ticker in tickers:

        try:
            df = data[ticker].copy()
        except:
            st.warning(f"Gagal load {ticker}")
            continue

        df = df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        df = df.reset_index()
        df = df.sort_values('Date')
        df.rename(columns={'Date': 'date'}, inplace=True)

        # ================================
        # ATR
        # ================================
        df['h-l'] = df['high'] - df['low']
        df['h-c'] = abs(df['high'] - df['close'].shift(1))
        df['l-c'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['h-l', 'h-c', 'l-c']].max(axis=1)
        df['atr'] = df['tr'].rolling(atr_period).mean()

        # ================================
        # ENTRY RULE (GANTI SESUAI KAMU)
        # ================================
        df['entry_signal'] = df['close'] > df['high'].rolling(20).max().shift(1)

        # ================================
        # BACKTEST (HOLD 1 HARI)
        # ================================
        for i in range(len(df) - 1):  # -1 karena butuh hari berikutnya

            if not df.loc[i, 'entry_signal']:
                continue

            entry_price = df.loc[i, 'close']
            atr = df.loc[i, 'atr']

            if pd.isna(atr):
                continue

            sl = entry_price - (atr * atr_mult)

            # data hari berikutnya
            next_row = df.loc[i + 1]

            o = next_row['open']
            l = next_row['low']
            c = next_row['close']

            # ========================
            # EXIT LOGIC
            # ========================

            # GAP DOWN
            if o <= sl:
                exit_price = o
                reason = 'gap_SL'

            # SL kena intraday
            elif l <= sl:
                if use_partial:
                    exit_price = (0.5 * sl) + (0.5 * c)
                    reason = 'partial_SL'
                else:
                    exit_price = sl
                    reason = 'SL'

            # normal exit (close T+1)
            else:
                exit_price = c
                reason = 'close_exit'

            ret = (exit_price - entry_price) / entry_price

            all_results.append({
                'ticker': ticker,
                'entry_date': df.loc[i, 'date'],
                'exit_date': next_row['date'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'return': ret,
                'reason': reason
            })

    results_df = pd.DataFrame(all_results)

# ================================
# 📊 METRICS
# ================================
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
