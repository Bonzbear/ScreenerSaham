"""Screener Saham Indonesia (versi baru) — halaman Streamlit.

Taruh di folder pages/ bersama folder screener_baru/.
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
from screener_baru.engine import MIN_SAMPLE, Strategy, run, strategy_from_preset
from screener_baru.presets import PRESET_BY_NAME, PRESETS
from screener_baru.screener import DEFAULT_CRITERIA, signal_mask

WIB = ZoneInfo("Asia/Jakarta")
MARKET_FINAL = dt.time(16, 15)  # setelah jam ini candle hari itu dianggap final (ubah bila perlu)
ALL, MANUAL = "Semua paket", "Manual (-)"

st.set_page_config(page_title="Screener Saham (Baru)", layout="wide")
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
        return False, "TELEGRAM_TOKEN / TELEGRAM_CHAT_ID belum diisi (Settings -> Secrets)."
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
        return (r.ok, "" if r.ok else r.text[:200])
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def format_telegram(df: pd.DataFrame) -> str:
    now = dt.datetime.now(WIB).strftime("%Y-%m-%d %H:%M")
    if df.empty:
        return "Tidak ada sinyal hari ini"
    msg = f"<b>🚨 SIGNAL TRADE 🚨</b>\n{now}\n━━━━━━━━━━━━━━\n"
    for n, (_, r) in enumerate(df.head(10).iterrows(), 1):
        w = f" {r['Warning']}" if r.get("Warning") else ""
        scr = f" — {r['Screener']}" if r.get("Screener") not in (None, "-") else ""
        msg += f"<b>{n}. {r['Ticker']}{w}</b>{scr} (TP {r['TP (%)']:g}%)\n"
    msg += (
        "\n<b>⚠️ Menandakan saham dengan risiko tinggi / volatilitas tinggi</b>\n"
        "\n<b>📌 Entry</b>\nPre-closing (bid 3-5 tick di atas IEP)\n"
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

# --- pilihan paket
st.session_state.setdefault("tp", 1.5)
st.session_state.setdefault("sl", 0.0)
st.session_state.setdefault("hold", 1)


def _on_pick():
    pr = PRESET_BY_NAME.get(st.session_state["pick"])
    st.session_state["tp"] = float(pr.tp_pct) if pr else 1.5
    st.session_state["sl"] = float(pr.sl_pct) if pr else 0.0
    st.session_state["hold"] = int(pr.hold_days) if pr else 1


sb.subheader("Paket screener")
sel = sb.selectbox("Pilih paket", [ALL] + [p.name for p in PRESETS] + [MANUAL], key="pick", on_change=_on_pick)

preset = PRESET_BY_NAME.get(sel)
values: dict = {}
crit = dict(DEFAULT_CRITERIA)

if sel == ALL:
    sb.caption("Menjalankan semua paket sekaligus, masing-masing dengan TP/SL/hari menahan bawaannya.")
    with sb.expander("TP/SL tiap paket"):
        st.table(pd.DataFrame(
            [{"Paket": p.name, "TP (%)": p.tp_pct, "SL (%)": p.sl_pct or "-", "Hari": p.hold_days} for p in PRESETS]
        ).set_index("Paket"))
elif preset is not None:
    with sb.expander("Parameter paket (opsional diubah)", expanded=False):
        for k, prm in preset.params.items():
            values[k] = st.number_input(prm.label, value=float(prm.default), step=float(prm.step),
                                        format=prm.fmt, key=f"{preset.name}|{k}")
    sb.subheader("Target")
    sb.number_input("TP (%)", 0.1, 100.0, step=0.1, key="tp")
    sb.number_input("SL (%) — 0 = tanpa SL", 0.0, 50.0, step=0.5, key="sl")
    sb.number_input("Maksimal hari menahan (D+N)", 1, 30, key="hold")
else:  # manual
    c = crit
    sb.subheader("Kriteria manual")
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
    sb.subheader("Target")
    sb.number_input("TP (%)", 0.1, 100.0, step=0.1, key="tp")
    sb.number_input("SL (%) — 0 = tanpa SL", 0.0, 50.0, step=0.5, key="sl")
    sb.number_input("Maksimal hari menahan (D+N)", 1, 30, key="hold")

sb.subheader("Backtest")
lookback = sb.number_input("Periode backtest (hari kalender)", 60, 1825, 730, step=30)
with sb.expander("Biaya"):
    bf = st.number_input("Fee beli (%)", 0.0, 2.0, 0.15, step=0.01)
    sf = st.number_input("Fee jual + pajak (%)", 0.0, 2.0, 0.25, step=0.01)
    slip = st.number_input("Slippage entry (%)", 0.0, 3.0, 0.0, step=0.05)


def bt_params(tp, sl, hold) -> BacktestParams:
    return BacktestParams(tp_pct=tp, sl_pct=sl, hold_days=int(hold), buy_fee_pct=bf, sell_fee_pct=sf, slippage_pct=slip)


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
    prices_view = prices
    latest = max(df.index[-1] for df in prices.values())
else:
    prices_view = {t: df[df.index < today] for t, df in prices.items()}
    latest = max(df.index[-1] for df in prices_view.values() if not df.empty)

chosen = st.date_input("Tanggal screener", value=latest.date(), max_value=latest.date())
all_dates = sorted({d for df in prices_view.values() for d in df.index[-400:]})
eff_candidates = [d for d in all_dates if d <= pd.Timestamp(chosen)]
if not eff_candidates:
    st.error("Tidak ada data pada atau sebelum tanggal itu.")
    st.stop()
effective = eff_candidates[-1]
if effective.date() != chosen:
    st.caption(f"{chosen} bukan hari bursa → memakai {effective.date()}.")
st.caption(f"Data terakhir di cache: {latest.date()} • {len(prices)} saham")

# --------------------------------------------------------------------- run
if st.button("▶️ Jalankan Screener", type="primary"):
    if sel == ALL:
        strategies = [strategy_from_preset(p, None, bt_params(p.tp_pct, p.sl_pct, p.hold_days)) for p in PRESETS]
    elif preset is not None:
        strategies = [strategy_from_preset(preset, values, bt_params(st.session_state["tp"], st.session_state["sl"], st.session_state["hold"]))]
    else:
        cc = dict(crit)
        strategies = [Strategy("-", lambda d, _c=cc: signal_mask(d, _c),
                               bt_params(st.session_state["tp"], st.session_state["sl"], st.session_state["hold"]))]
    with st.spinner("Menghitung sinyal & backtest..."):
        cand, trades = run(prices_view, effective, strategies, int(lookback))
    st.session_state["res"] = dict(cand=cand, trades=trades, date=effective.date(), lookback=int(lookback))

res = st.session_state.get("res")
if res:
    cand, trades = res["cand"], res["trades"]
    st.subheader(f"Hasil screener {res['date']}")
    if cand.empty:
        st.warning("Tidak ada saham yang memenuhi kriteria pada tanggal ini.")
    else:
        st.success(f"{len(cand)} sinyal ditemukan.")
        show = cand.copy()
        show["Kirim"] = False
        edited = st.data_editor(
            show, hide_index=True,
            disabled=[x for x in show.columns if x != "Kirim"],
            column_config={"Harga": st.column_config.NumberColumn(format="%d")},
        )
        st.caption(
            f"Winrate = persentase sinyal lampau saham itu (paket yang sama, {res['lookback']} hari ke belakang) "
            f"yang menyentuh TP dalam batas hari menahan; di bawah {MIN_SAMPLE} sinyal dianggap sampel kecil. "
            "Tanpa SL, trade yang tidak kena TP dihitung keluar di close hari terakhir (Expectancy sudah termasuk fee). "
            "CL berdasarkan support TF15 tidak bisa disimulasikan dengan data harian."
        )
        if st.button("📤 Kirim ke Telegram"):
            pick = edited[edited["Kirim"]]
            if pick.empty:
                st.warning("Centang minimal 1 saham pada kolom Kirim.")
            else:
                ok, err = send_telegram(format_telegram(pick))
                st.success("Terkirim ke Telegram.") if ok else st.error(f"Gagal kirim: {err}")

    if not trades.empty:
        with st.expander("Daftar transaksi backtest"):
            st.dataframe(trades)
            st.download_button("Unduh CSV", trades.to_csv(index=False).encode(), "trades.csv", "text/csv")
