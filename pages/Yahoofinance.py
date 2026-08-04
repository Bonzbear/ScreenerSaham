import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import numpy as np

TOKEN = ""
CHAT_ID = ""

MAX_SCORE = 1000

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

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
# GET ALL IDX TICKERS
# =========================
@st.cache_data(ttl=86400) # Cache 1 hari (24 jam)
def get_all_active_tickers():
    """Mengambil daftar seluruh saham yang listing di BEI secara otomatis"""
    tickers = []
    try:
        # Mengambil dari tabel Wikipedia (Paling stabil dan sering di-update komunitas)
        url = "https://id.wikipedia.org/wiki/Daftar_perusahaan_yang_tercatat_di_Bursa_Efek_Indonesia"
        tables = pd.read_html(url)
        
        for df in tables:
            # Mencari kolom yang berisi kode saham
            for col in df.columns:
                if 'Kode' in str(col):
                    codes = df[col].dropna().astype(str).tolist()
                    for code in codes:
                        code = code.strip()
                        # Pastikan format kode saham valid (4 huruf)
                        if len(code) == 4 and code.isalpha():
                            tickers.append(code + ".JK")
                            
        tickers = list(set(tickers)) # Hapus duplikat
        
        if len(tickers) > 500:
            return tickers
    except Exception as e:
        pass
    
    # Fallback darurat jika gagal scrape
    st.error("Gagal mengambil seluruh daftar saham. Menggunakan daftar cadangan (LQ45).")
    return ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "GOTO.JK", "AMMN.JK", "ADRO.JK", "BRPT.JK"]


# =========================
# YAHOO FINANCE DATA
# =========================
@st.cache_data(ttl=3600) # Cache 1 jam agar run selanjutnya instan
def get_yahoo_data(tickers):
    combined = {}
    chunk_size = 150 # Batching agar request API Yahoo Finance tidak ditolak
    
    # Progress Bar untuk UI
    progress_text = "Mengunduh histori harga..."
    my_bar = st.progress(0, text=progress_text)
    
    total_chunks = (len(tickers) // chunk_size) + 1
    
    for idx, i in enumerate(range(0, len(tickers), chunk_size)):
        chunk = tickers[i:i+chunk_size]
        
        # Update progress bar
        percent_complete = int(((idx + 1) / total_chunks) * 100)
        my_bar.progress(percent_complete if percent_complete <= 100 else 100, 
                        text=f"Mendownload data saham batch {idx+1}/{total_chunks} dari Yahoo Finance...")

        data = yf.download(
            tickers=chunk,
            period="5y",
            group_by="ticker",
            progress=False,
            auto_adjust=False,
            threads=True
        )
        
        if len(chunk) == 1:
            ticker = chunk[0]
            df = data.copy()
            df = df.dropna(subset=["Open", "Close", "Volume"])
            if not df.empty:
                df.index = pd.to_datetime(df.index).normalize()
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                combined[ticker] = df
        else:
            for ticker in chunk:
                if ticker in data.columns.levels[0]:
                    df = data[ticker].copy()
                    df = df.dropna(subset=["Open", "Close", "Volume"])
                    if not df.empty:
                        df.index = pd.to_datetime(df.index).normalize()
                        if df.index.tz is not None:
                            df.index = df.index.tz_localize(None)
                        combined[ticker] = df
                        
    my_bar.empty() # Hilangkan progress bar setelah selesai
    return combined


# =========================
# PREPARE
# =========================
def prepare_data(df):
    df = df.sort_index()

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    df = df[df["Volume"] > 0]
    
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["VOLMA20"] = df["Volume"].rolling(20).mean()
    df["VOLMA5"] = df["Volume"].rolling(5).mean()
    df["Value"] = df["Close"] * df["Volume"]
    df["AvgValue20"] = df["Value"].rolling(20).mean()
    df["ValueRatio"] = df["Value"] / df["AvgValue20"]

    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()

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
    
    open_ = today["Open"]
    close = today["Close"]
    volume = today["Volume"]

    prev_close = prev["Close"]
    prev_volume = prev["Volume"]

    sma5 = today["SMA5"]
    value = today["Value"]
    avg_value = today["AvgValue20"]
    avg_volume = today["VOLMA20"]

    change_pct = (close - prev_close) / prev_close
    ara = get_ara_limit(prev_close)

    # Filter Harga
    if close > 6500 or close < 50:
        return False

    if ara == 0.25 and change_pct >= 0.24:
        return False
    if ara == 0.35 and change_pct >= 0.33:
        return False

    # Filter Likuiditas
    if not (avg_value > 10_000_000_000 and avg_volume > 1_000_000):
        return False

    # Kriteria Sinyal Utama
    if not (
        open_ < close and
        volume > prev_volume and
        prev_close < close and
        close > sma5 and
        value > 10_000_000_000
    ):
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

    if prev["Close"] < prev["SMA5"]: score += 125
    if today["Volume"] > today["VOLMA20"]: score += 125
    if today["Volume"] > today["VOLMA5"]: score += 125
    if today["Low"] > prev["Low"]: score += 125
    if today["High"] > prev["High"]: score += 125
    if (open_ - low) > (high - close): score += 125
    if today["Close"] > today["VWAP"]: score += 125
    if prev["Close"] < prev["VWAP"]: score += 125

    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    if body > 0 and upper_wick > body * 1.5:
        score -= 100
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

    total_trades = len(returns)

    if total_trades == 0:
        return 0, 0, 0

    winrate = sum(1 for r in returns if r >= 0.015) / total_trades
    ev = sum(returns) / total_trades

    return round(winrate * 100, 2), round(ev * 100, 2), total_trades


# =========================
# SCREENER
# =========================
def run_screener(data):
    results = []
    
    # Progress bar untuk kalkulasi sinyal
    calc_bar = st.progress(0, text="Mengkalkulasi Signal & Backtest EV...")
    total_items = len(data)

    for idx, (ticker, df) in enumerate(data.items()):
        # Update progress bar tiap 50 saham agar UI tidak ngelag
        if idx % 50 == 0 or idx == total_items - 1:
            calc_bar.progress((idx + 1) / total_items, text=f"Menganalisis {ticker} ({idx+1}/{total_items})...")
            
        df = prepare_data(df)

        if len(df) < 30:
            continue

        if not is_signal(df, len(df)-1):
            continue

        score, warning = calculate_score(df)
        score_pct = (score / MAX_SCORE) * 100

        winrate, ev, total_trades = backtest_ev(df)

        if total_trades < 5:
            valid_winrate = 50.0 
        else:
            valid_winrate = winrate

        probability = (score_pct * 0.3) + (valid_winrate * 0.7)

        latest = df.sort_index().tail(1)
        
        results.append({
            "Ticker": ticker,
            "Price": float(latest["Close"].values[0]),
            "SMA5": round(float(latest["SMA5"].values[0]), 2),
            "Warning": warning,
            "Score (%)": round(score_pct, 2),
            "Winrate (%)": winrate, 
            "Trades": total_trades, 
            "Probability (%)": round(probability, 2),
            "EV (%)": ev
        })

    calc_bar.empty()
    df_result = pd.DataFrame(results)

    if not df_result.empty:
        df_result = df_result.sort_values(by="Probability (%)", ascending=False)
        df_result.insert(0, "Rank", range(1, len(df_result)+1))

    return df_result
    

# =========================
# UI
# =========================
st.set_page_config(page_title="Screener Semua Saham", layout="wide")
st.title("Screener Seluruh Saham Indonesia")

st.markdown("""
Sistem ini akan **otomatis mengambil daftar ~900 saham aktif di IHSG**, mengunduh histori harga 5 tahun terakhir dari Yahoo Finance, lalu menyeleksi sinyal secara masif.
*Catatan: Proses pertama kali akan memakan waktu **1-3 menit**.*
""")

if st.button("▶️ Scan Seluruh Saham IHSG"):
    
    with st.spinner("Mengambil daftar kode saham dari bursa..."):
        tickers = get_all_active_tickers()
        st.info(f"Berhasil menemukan **{len(tickers)}** saham aktif di BEI.")

    # Mengunduh Data Yahoo Finance
    data = get_yahoo_data(tickers)
    st.session_state["data"] = data
    
    # Menjalankan Screener
    df = run_screener(data)

    if df.empty:
        st.warning("Tidak ada sinyal saham yang memenuhi kriteria kuat hari ini.")
    else:
        st.session_state["df"] = df
        st.success(f"Selesai! {len(df)} saham potensial ditemukan.")

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
    st.write("---")
    if st.button("📤 Kirim ke Telegram"):
        selected = st.session_state["edited_df"]
        selected = selected[selected["Kirim"] == True]

        if selected.empty:
            st.warning("Pilih minimal 1 saham pada checkbox (Kirim) terlebih dahulu.")
        else:
            msg = format_telegram(selected)
            send_telegram(msg)
            st.success("Sinyal berhasil dikirim ke Telegram!")
