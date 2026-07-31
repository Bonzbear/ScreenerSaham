
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np



TOKEN = "8639573881:AAHQfo4YEqjFVMMurZD4-gS416UrMbukGsE"
CHAT_ID = "-1003724967633"

MAX_SCORE = 650

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg,"parse_mode": "HTML"})

def format_telegram(df):
    no = 0

    if df.empty:
        return "Tidak ada sinyal hari ini"

    indonesia_tz = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(indonesia_tz).strftime("%Y-%m-%d %H:%M")

    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n"
    msg += "━━━━━━━━━━━━━━\n"

    for _, row in df.head(5).iterrows():

        warning = row["Warning"] if "Warning" in df.columns else ""

        if warning:
            ticker = f"{row['Ticker'].replace('.JK','')} {warning}"
        else:
            ticker = row["Ticker"].replace(".JK", "")

        no += 1
        msg += f"<b>{no}. {ticker}</b>\n"

    msg += (
        "\n<b>⚠️ Menandakan saham dengan risiko tinggi / volatilitas tinggi</b>\n"
        "\n<b>📌 Entry</b>\n"
        "Pre-closing (bid 3-5 tick di atas IEP)\n\n"
        "<b>🎯 Target</b>\n"
        "TP fleksibel (bisa >1% / ARA)\n\n"
        "<b>🛑 Risiko</b>\n"
        "CL jika bertahan di bawah support hingga penutupan\n\n"
        "<b>ℹ️ Disclaimer</b>\n"
        "Bukan rekomendasi investasi. Lakukan analisa mandiri.\n"
    )

    return msg


# =========================
# LOAD CSV
# =========================
def load_csv_today(file):

    file.seek(0)

    df = pd.read_csv(
        file,
        dtype=str,
        encoding="latin1",
        engine="python",
        keep_default_na=False
    )

    # =========================
    # HAPUS HEADER DOBEL
    # =========================
    df = df[df["Code"] != "Code"]

    # =========================
    # HAPUS KOLOM TIDAK PERLU
    # =========================
    drop_cols = [col for col in df.columns if "Unnamed" in col]

    df = df.drop(columns=drop_cols)

    # =========================
    # CLEAN
    # =========================
    for col in df.columns:

        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.replace(",", "", regex=False)
            .str.replace("¡ã", "", regex=False)
            .str.replace("¡è", "", regex=False)
            .str.replace('"', '', regex=False)
        )

    # =========================
    # NUMERIC
    # =========================
    num_cols = [
        "Last",
        "Prev",
        "Open",
        "High",
        "Low",
        "Value(M)",
        "Volume",
        "Freq"
    ]

    for col in num_cols:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # =========================
    # VOLUME LOT -> SHARE
    # =========================
    df["Volume"] = df["Volume"] * 100

    # =========================
    # FINAL
    # =========================
    df["Ticker"] = df["Code"] + ".JK"
    df["Close"] = df["Last"]

    return df[
        ["Ticker", "Open", "High", "Low", "Close", "Volume"]
    ]
# =========================
# YAHOO
# =========================
@st.cache_data(ttl=600)
def get_data(tickers):

    return yf.download(
        tickers=" ".join(tickers),
        period="5y",
        group_by="ticker",
        progress=False,
        auto_adjust=False
    )


# =========================
# MERGE
# =========================
def merge_today(data, df_today):

    combined = {}

    today_date = pd.Timestamp.today().normalize()

    for _, row in df_today.iterrows():

        ticker = row["Ticker"]

        if ticker not in data:
            continue

        hist = data[ticker].copy()

        if hist.empty:
            continue

        # =========================
        # FIX DATE
        # =========================
        hist.index = pd.to_datetime(hist.index)

        try:
            hist.index = hist.index.tz_localize(None)
        except:
            pass

        hist.index = hist.index.normalize()

        # =========================
        # HAPUS ROW HARI INI
        # =========================
        hist = hist[hist.index != today_date]

        # =========================
        # ROW BARU
        # =========================
        new_row = pd.DataFrame({
            "Open": [float(row["Open"])],
            "High": [float(row["High"])],
            "Low": [float(row["Low"])],
            "Close": [float(row["Close"])],
            "Adj Close": [float(row["Close"])],
            "Volume": [float(row["Volume"])]
        }, index=[today_date])

        # =========================
        # PASTIKAN INDEX SAMA TIPE
        # =========================
        new_row.index = pd.to_datetime(new_row.index)

        # =========================
        # GABUNG
        # =========================
        hist = pd.concat([hist, new_row])

        # =========================
        # SORT
        # =========================
        hist = hist.sort_index()

        # =========================
        # DEBUG
        # =========================

        combined[ticker] = hist

    return combined


# =========================
# PREPARE
# =========================
def prepare_data(df):

    # =========================
    # SORT
    # =========================
    df = df.sort_index()

    # =========================
    # HAPUS CANDLE LIBUR
    # =========================
    df = df.dropna(
        subset=["Open", "High", "Low", "Close", "Volume"]
    )
    # HAPUS CANDLE LIBUR / FAKE YAHOO
    df = df[df["Volume"] > 0]
    # =========================
    # INDICATOR
    # =========================
    df["SMA5"] = df["Close"].rolling(5).mean()

    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["VOLMA5"] = df["Volume"].rolling(5).mean()

    df["Value"] = df["Close"] * df["Volume"]

    df["AvgValue20"] = (
        df["Value"].rolling(20).mean()
    )

    df["ValueRatio"] = (
        df["Value"] / df["AvgValue20"]
    )

    typical = (
        df["High"] +
        df["Low"] +
        df["Close"]
    ) / 3

    df["VWAP"] = (
        (typical * df["Volume"]).cumsum()
        /
        df["Volume"].cumsum()
    )

    # =========================
    # DROP INDIKATOR
    # =========================
    df = df.dropna(
        subset=[
            "SMA5",
            "VOLMA20",
            "VOLMA5",
            "AvgValue20",
            "VWAP"
        ]
    )

    return df

# =========================
# ARA
# =========================
def get_ara_limit(price):

    if price < 200:
        return 0.35
    elif price <= 5000:
        return 0.25
    else:
        return 0.20


# =========================
# SIGNAL
# =========================
def is_signal(df, i):

    today = df.iloc[i]
    prev = df.iloc[i-1]
    open = today["Open"]
    close = today["Close"]
    volume = today["Volume"]

    prev_close = prev["Close"]
    prev_volume = prev["Volume"]

    sma5 = today["SMA5"]
    value = today["Value"]
    avg_value = today["AvgValue20"]
    value_ratio = today["ValueRatio"]
    avg_volume = today["VOLMA20"]

    change_pct = (close - prev_close) / prev_close
    ara = get_ara_limit(prev_close)

    if close > 6500 or close < 50:
        return False

    if ara == 0.25 and change_pct >= 0.24:
        return False
    if ara == 0.35 and change_pct >= 0.33:
        return False

    if not (avg_value > 10_000_000_000 and avg_volume > 1_000_000):
        return False

    if not (
        open < close and                       # Tetap dipertahankan: Memastikan candle hari ini hijau (pembeli dominan)
        today["Volume"] > today["VOLMA20"] and # Tetap dipertahankan: Volume di atas rata-rata 20 hari
        today["Close"] > today["VWAP"] and     # Tetap dipertahankan: Harga penutupan di atas harga rata-rata intraday
        today["Close"] > prev["High"] and      # MODIFIKASI: Menggantikan syarat High/Low kemarin
        close > sma5 and                       # Tetap dipertahankan: Konfirmasi uptrend jangka pendek
        value > 10_000_000_000                 # Tetap dipertahankan: Filter likuiditas Rp 10 Miliar
    ):
    # Skip saham ini
        return False

    return True


# =========================
# SCORE
# =========================
def calculate_score(df):
    today = df.iloc[-1]
    prev = df.iloc[-2]

    open_ = today["Open"]
    high = today["High"]
    low = today["Low"]
    close = today["Close"]
    
    score = 0
    warning = ""

    # --- 1. REVERSAL & BREAKOUT (Milik Anda) ---
    if prev["Close"] < prev["SMA5"]: score += 100
    if prev["Close"] < prev["VWAP"]: score += 100
    if (open_ - low) > (high - close): score += 50  # Demand > Supply intraday

    # --- 2. MOMENTUM EKSTREM (Modifikasi) ---
    # Memberi poin HANYA jika volume benar-benar meledak (> 1.5x rata-rata 5 hari)
    if today["Volume"] > (today["VOLMA5"] * 1.5): score += 100

    # --- 3. KEKUATAN PENUTUPAN (Tambahan Baru) ---
    # Memastikan range hari itu ada untuk menghindari error division by zero
    if high != low: 
        closing_range = (close - low) / (high - low)
        # Jika penutupan berada di 20% area paling pucuk
        if closing_range >= 0.80: 
            score += 100

    # --- 4. TREND & RISK/REWARD (Tambahan Baru) ---
    # Poin plus jika trend menengah (MA20) sedang menanjak
    if today["SMA20"] > prev["SMA20"]: score += 100
    
    # Poin plus jika posisi beli dekat dengan garis Support MA20 (Jarak < 5%)
    jarak_ma20 = (close - today["SMA20"]) / today["SMA20"]
    if 0 < jarak_ma20 <= 0.05: score += 100 

    # --- 5. PENALTI & WARNING (Milik Anda) ---
    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    # Penalti jika ekor atas terlalu panjang (Indikasi distribusi/guyuran)
    if body > 0 and upper_wick > body * 1.5:
        score -= 150  # Penalti diperbesar agar probabilitas langsung anjlok
        warning = "⚠️"

    return score, warning


# =========================
# BACKTEST + EV
# =========================
def backtest_ev(df):
    returns = []

    for i in range(20, len(df)-1):
        if not is_signal(df, i):
            continue

        today = df.iloc[i]
        next_day = df.iloc[i+1]

        close_today = today["Close"]
        high_next = next_day["High"]

        ret = (high_next - close_today) / close_today
        returns.append(ret)

    # 1. Hitung total trade (jumlah sampel)
    total_trades = len(returns)

    # 2. Kembalikan 0 untuk ketiga nilai jika tidak ada trade
    if total_trades == 0:
        return 0, 0, 0

    # Menggunakan variabel total_trades agar kode lebih rapi
    winrate = sum(1 for r in returns if r >= 0.015) / total_trades
    ev = sum(returns) / total_trades

    # 3. Tambahkan total_trades di hasil akhir
    return round(winrate * 100, 2), round(ev * 100, 2), total_trades


# =========================
# SCREENER
# =========================
def run_screener(data):
    results = []
    
    # Pastikan variabel MAX_SCORE sudah didefinisikan sebelumnya (misal: MAX_SCORE = 650)

    for ticker, df in data.items():
        df = prepare_data(df)

        if len(df) < 30:
            continue

        if not is_signal(df, len(df)-1):
            continue

        score, warning = calculate_score(df)
        score_pct = (score / MAX_SCORE) * 100

        # --- PERUBAHAN 1: Tangkap 3 nilai dari backtest_ev ---
        winrate, ev, total_trades = backtest_ev(df)

        # --- PERUBAHAN 2: Validasi sampel minimum ---
        # Jika historis kemunculan sinyal kurang dari 5 kali, winrate dianggap netral (50%)
        if total_trades < 5:
            valid_winrate = 50.0 
        else:
            valid_winrate = winrate

        # Menghitung probabilitas menggunakan valid_winrate
        probability = (score_pct * 0.3) + (valid_winrate * 0.7)

        latest = df.sort_index().tail(1)
        
        results.append({
            "Ticker": ticker,
            "Price": float(latest["Close"].values[0]),
            "SMA5": round(float(latest["SMA5"].values[0]), 2),
            "Warning": warning,
            "Score (%)": round(score_pct, 2),
            "Winrate (%)": winrate, # Tetap tampilkan winrate asli untuk referensi
            "Trades": total_trades, # --- PERUBAHAN 3: Tambahkan kolom jumlah trade ---
            "Probability (%)": round(probability, 2),
            "EV (%)": ev
        })

    # Nama variabel DataFrame diubah sedikit agar tidak bentrok dengan iterasi df di atas
    hasil_df = pd.DataFrame(results)

    if not hasil_df.empty:
        hasil_df = hasil_df.sort_values(by="Probability (%)", ascending=False)
        hasil_df.insert(0, "Rank", range(1, len(hasil_df) + 1))

    return hasil_df
    

# =========================
# UI
# =========================
st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia")

uploaded_file = st.file_uploader("Upload CSV Hari Ini", type=["csv"])

if st.button("▶️ Run Screener"):

    if uploaded_file is None:
        st.error("Upload CSV dulu")
        st.stop()

    with st.spinner("Processing..."):

        df_today = load_csv_today(uploaded_file)
        tickers = df_today["Ticker"].unique().tolist()

        data = get_data(tickers)
        data = merge_today(data, df_today)
        st.session_state["data"] = data
        df = run_screener(data)

    if df.empty:
        st.warning("Tidak ada saham")
    else:
        st.session_state["df"] = df
        st.success(f"{len(df)} saham ditemukan")

# =========================
# DISPLAY + CHECKLIST
# =========================
if "df" in st.session_state:

    df_display = st.session_state["df"].copy()
    df_display["Kirim"] = False

    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True
    )

    st.session_state["edited_df"] = edited_df

# =========================
# TELEGRAM
# =========================
if "edited_df" in st.session_state:

    if st.button("📤 Telegram"):

        selected = st.session_state["edited_df"]
        selected = selected[selected["Kirim"] == True]

        if selected.empty:
            st.warning("Pilih saham dulu")
        else:
            msg = format_telegram(selected)
            send_telegram(msg)
            st.success("Terkirim")
