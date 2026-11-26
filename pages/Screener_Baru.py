"""Screener Saham Indonesia — Streamlit.

Jalankan:  streamlit run app.py
"""
from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from screener_baru import data as dm
from screener_baru.backtest import BacktestParams
from screener_baru.engine import MIN_SAMPLE, run
from screener_baru.screener import DEFAULT_CRITERIA

WIB = ZoneInfo("Asia/Jakarta")
MARKET_FINAL = dt.time(16, 15)  # setelah jam ini candle hari itu dianggap final (ubah bila perlu)

st.set_page_config(page_title="Screener Saham", layout="wide")
st.title("Screener Saham Indonesia (Baru)")


# ------------------------------------------------------------------ helper
def market_is_final(now: dt.datetime) -> bool:
    return now.weekday() >= 5 or now.time() >= MARKET_FINAL


def get_secret(name: str) -> str:
    try:
        v = st.secrets.get(name)
        if v:
            return str(v)
    except Exception:
        pass
    return os.environ.get(name, "")


def send_telegram(msg: str) -> tuple[bool, str]:
    token, chat = get_secret("TELEGRAM_TOKEN"), get_secret("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False, "TELEGRAM_TOKEN / TELEGRAM_CHAT_ID belum diisi (lihat .streamlit/secrets.toml.example)."
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
        return (r.ok, "" if r.ok else r.text[:200])
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def format_telegram(df: pd.DataFrame, tp_pct: float) -> str:
    now = dt.datetime.now(WIB).strftime("%Y-%m-%d %H:%M")
    if df.empty:
        return "Tidak ada sinyal hari ini"
    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n━━━━━━━━━━━━━━\n"
    for n, (_, r) in enumerate(df.head(10).iterrows(), 1):
        w = f" {r['Warning']}" if r.get("Warning") else ""
        msg += f"<b>{n}. {r['Ticker']}{w}</b>\n"
    msg += (
        "\n<b>⚠️ Menandakan saham dengan risiko tinggi / volatilitas tinggi</b>\n"
        "\n<b>📌 Entry</b>\nPre-closing (bid 3-5 tick di atas IEP)\n"
        f"\n<b>🎯 Target</b>\nTP {tp_pct:g}% atau lebih (fleksibel)\n"
        "\n<b>🛑 Risiko</b>\nCL jika bertahan di bawah support TF15 hingga penutupan\n"
        "\n<b>ℹ️ Disclaimer</b>\nBukan rekomendasi investasi. Lakukan analisa mandiri.\n"
    )
    return msg


@st.cache_resource(show_spinner="Membaca data tersimpan...")
def cached_prices(mtime: float, tickers_key: tuple):
    return dm.load_prices(list(tickers_key))


# ------------------------------------------------------------------ sidebar
sb = st.sidebar
sb.header("Pengaturan")

tickers = dm.load_tickers()
with sb.expander(f"Daftar saham ({len(tickers)})"):
    txt = st.text_area("Tempel daftar kode (boleh dengan koma/kutip)", value=", ".join(t[:-3] for t in tickers), height=150)
    if st.button("Simpan daftar"):
        tickers = dm.save_tickers(txt)
        st.success(f"{len(tickers)} saham disimpan. Klik 'Perbarui data' untuk mengunduh saham baru.")

if sb.button("🔄 Perbarui data Yahoo"):
    bar = st.progress(0.0, text="Memulai...")
    info = dm.update_prices(tickers, progress=lambda f, t: bar.progress(min(f, 1.0), text=t))
    bar.empty()
    st.cache_resource.clear()
    if info["failed_chunks"]:
        st.warning(f"{info['failed_chunks']} batch gagal diunduh (rate limit?). Coba perbarui lagi nanti.")
    st.success(f"Data diperbarui: {info['tickers_in_cache']} saham di cache, {info['no_data']} kode tanpa data Yahoo.")

sb.subheader("Kriteria screener")
c = dict(DEFAULT_CRITERIA)
c["min_price"] = sb.number_input("Harga minimum", 0, 100000, DEFAULT_CRITERIA["min_price"], step=10)
c["max_price"] = sb.number_input("Harga maksimum", 0, 100000, DEFAULT_CRITERIA["max_price"], step=100)
c["ara_buffer_pct"] = sb.number_input("Buang jika naik ≥ ARA − (%)", 0.0, 20.0, DEFAULT_CRITERIA["ara_buffer_pct"], step=0.5)
c["min_avg_value"] = sb.number_input("Rata-rata nilai transaksi 20 hari min (Rp miliar)", 0.0, 10000.0, 10.0, step=1.0) * 1e9
c["min_value_today"] = sb.number_input("Nilai transaksi hari ini min (Rp miliar)", 0.0, 10000.0, 10.0, step=1.0) * 1e9
c["min_avg_volume"] = sb.number_input("Rata-rata volume 20 hari min (lembar)", 0, 10**10, DEFAULT_CRITERIA["min_avg_volume"], step=100_000)
c["sma_period"] = sb.number_input("Periode SMA", 2, 200, DEFAULT_CRITERIA["sma_period"])
c["need_bullish_candle"] = sb.checkbox("Candle hijau (open < close)", True)
c["need_volume_up"] = sb.checkbox("Volume > volume kemarin", True)
c["need_price_up"] = sb.checkbox("Close > close kemarin", True)
c["need_above_sma"] = sb.checkbox("Close > SMA", True)

sb.subheader("Target & backtest")
tp = sb.number_input("TP (%)", 0.1, 100.0, 1.5, step=0.1)
sl = sb.number_input("SL (%) — 0 = tanpa SL", 0.0, 50.0, 0.0, step=0.5)
hold = sb.number_input("Maksimal hari menahan (D+N)", 1, 30, 1)
lookback = sb.number_input("Periode backtest (hari kalender)", 60, 1825, 730, step=30)
with sb.expander("Biaya"):
    bf = st.number_input("Fee beli (%)", 0.0, 2.0, 0.15, step=0.01)
    sf = st.number_input("Fee jual + pajak (%)", 0.0, 2.0, 0.25, step=0.01)
    slip = st.number_input("Slippage entry (%)", 0.0, 3.0, 0.0, step=0.05)

# --------------------------------------------------------------------- data
prices = cached_prices(dm.cache_mtime(), tuple(tickers))
if not prices:
    st.info("Belum ada data. Klik **Perbarui data Yahoo** di sidebar (pertama kali butuh beberapa menit).")
    st.stop()

now = dt.datetime.now(WIB)
today = pd.Timestamp(now.date())
use_live = True
if any(df.index[-1] == today for df in prices.values()) and not market_is_final(now):
    use_live = st.toggle(
        "Pakai candle hari ini yang masih berjalan (untuk entry pre-closing)",
        value=True,
        help="Harga & volume belum final dan data Yahoo bisa tertunda ± 10 menit. "
        "Matikan untuk memakai hari bursa sebelumnya.",
    )
    if use_live:
        st.warning("⏱ Candle hari ini belum final. Sinyal dihitung dari harga sementara — "
                   "backtest memakai candle final, jadi hasil live bisa sedikit berbeda.")

if use_live:
    latest = max(df.index[-1] for df in prices.values())
else:
    latest = max(df.loc[df.index < today].index[-1] for df in prices.values() if (df.index < today).any())

chosen = st.date_input("Tanggal screener", value=latest.date(), max_value=latest.date())
effective = pd.Timestamp(chosen)
if not use_live:
    prices_view = {t: df[df.index < today] for t, df in prices.items()}
else:
    prices_view = prices
all_dates = sorted({d for df in prices_view.values() for d in df.index[-400:]})
eff_candidates = [d for d in all_dates if d <= effective]
if not eff_candidates:
    st.error("Tidak ada data pada atau sebelum tanggal itu.")
    st.stop()
effective = eff_candidates[-1]
if effective.date() != chosen:
    st.caption(f"{chosen} bukan hari bursa → memakai {effective.date()}.")

st.caption(f"Data terakhir di cache: {latest.date()} • {len(prices)} saham")

# --------------------------------------------------------------------- run
if st.button("▶️ Jalankan Screener", type="primary"):
    bt = BacktestParams(tp_pct=tp, sl_pct=sl, hold_days=int(hold), buy_fee_pct=bf, sell_fee_pct=sf, slippage_pct=slip)
    with st.spinner("Menghitung sinyal & backtest..."):
        cand, trades, overall = run(prices_view, effective, c, bt, int(lookback))
    st.session_state["res"] = dict(cand=cand, trades=trades, overall=overall, tp=tp, sl=sl, hold=int(hold),
                                   date=effective.date(), lookback=int(lookback))

res = st.session_state.get("res")
if res:
    cand, trades, o = res["cand"], res["trades"], res["overall"]
    st.subheader(f"Hasil screener {res['date']}")

    st.markdown("**Winrate seluruh sinyal historis** (kriteria yang sama, semua saham, "
                f"{res['lookback']} hari ke belakang)")
    if o["n"] == 0:
        st.warning("Tidak ada sinyal historis dengan kriteria ini.")
    else:
        sl_txt = f"SL {res['sl']:g}%" if res["sl"] > 0 else "tanpa SL"
        cols = st.columns(5)
        cols[0].metric("Jumlah sinyal", f"{o['n']:,}")
        cols[1].metric(f"Winrate (TP {res['tp']:g}% kena)", f"{o['winrate']:.1f}%")
        cols[2].metric("Expectancy / trade (bersih)", f"{o['expectancy']:.2f}%")
        pf = "∞" if o["profit_factor"] == float("inf") else f"{o['profit_factor']:.2f}"
        cols[3].metric("Profit factor", pf)
        cols[4].metric("Keluar karena waktu habis", f"{o['time_pct']:.0f}%",
                       help=f"Dari yang keluar karena waktu habis, {o['time_positive_pct']:.0f}% berakhir untung.")
        extra = (f"Rata-rata menang {o['avg_win']:.2f}% • rata-rata kalah {o['avg_loss']:.2f}% • "
                 f"{sl_txt}, tahan maksimal D+{res['hold']}.")
        if res["sl"] > 0:
            extra += f" Winrate jika SL diabaikan (High ≥ TP saja): {o['winrate_simple']:.1f}% — selisihnya menunjukkan seberapa rapuh hasilnya."
        st.caption(extra)
        st.caption("Catatan: stop-loss berdasarkan support TF15 tidak bisa disimulasikan dengan data harian; "
                   "tanpa SL, trade yang tidak kena TP dihitung keluar di close hari terakhir.")

    if cand.empty:
        st.warning("Tidak ada saham yang memenuhi kriteria pada tanggal ini.")
    else:
        st.success(f"{len(cand)} saham lolos screener.")
        show = cand.copy()
        show["Kirim"] = False
        edited = st.data_editor(
            show, hide_index=True,
            disabled=[x for x in show.columns if x != "Kirim"],
            column_config={"Harga": st.column_config.NumberColumn(format="%d")},
        )
        st.caption(f"Winrate per saham dihitung dari riwayat sinyal saham itu sendiri; di bawah {MIN_SAMPLE} sinyal dianggap sampel kecil.")
        if st.button("📤 Kirim ke Telegram"):
            pick = edited[edited["Kirim"]]
            if pick.empty:
                st.warning("Centang minimal 1 saham pada kolom Kirim.")
            else:
                ok, err = send_telegram(format_telegram(pick, res["tp"]))
                st.success("Terkirim ke Telegram.") if ok else st.error(f"Gagal kirim: {err}")

    if not trades.empty:
        with st.expander("Daftar transaksi backtest"):
            st.dataframe(trades)
            st.download_button("Unduh CSV", trades.to_csv(index=False).encode(), "trades.csv", "text/csv")
