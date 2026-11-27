"""Catatan sinyal harian (forward test).

Setiap sinyal dicatat bersama HARGA SAAT DICATAT (mis. jam 14:50, bukan close final),
lalu setelah hari menahan lewat, hasil nyatanya dicocokkan dengan data High/Close Yahoo.
Tujuannya: membandingkan winrate AKTUAL dengan winrate backtest.

Catatan: disk Streamlit Cloud bisa terhapus saat aplikasi di-reboot -> unduh CSV
secara berkala dan unggah kembali bila perlu.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from .data import CACHE_DIR

LOG_FILE = CACHE_DIR / "signal_log.csv"
LOG_COLS = ["Tanggal", "Dicatat", "Screener", "Ticker", "Harga catat", "TP (%)", "Hari",
            "Winrate backtest (%)", "Sinyal lalu", "Expectancy backtest (%)"]
KEY = ["Tanggal", "Screener", "Ticker"]


def load_log(path: Path = LOG_FILE) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=LOG_COLS)
    df = pd.read_csv(path)
    for c in LOG_COLS:
        if c not in df.columns:
            df[c] = None
    return df[LOG_COLS]


def merge_logs(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Gabung; kunci (Tanggal, Screener, Ticker) yang sama -> baris terbaru menimpa."""
    both = pd.concat([old, new], ignore_index=True)
    both["Tanggal"] = pd.to_datetime(both["Tanggal"]).dt.strftime("%Y-%m-%d")
    both = both.drop_duplicates(KEY, keep="last")
    return both.sort_values(["Tanggal", "Screener", "Ticker"]).reset_index(drop=True)[LOG_COLS]


def make_rows(cand: pd.DataFrame, screen_date, now: dt.datetime) -> pd.DataFrame:
    """Ubah tabel kandidat (tanpa penggabungan paket) menjadi baris log."""
    if cand.empty:
        return pd.DataFrame(columns=LOG_COLS)
    return pd.DataFrame({
        "Tanggal": pd.Timestamp(screen_date).strftime("%Y-%m-%d"),
        "Dicatat": now.strftime("%Y-%m-%d %H:%M"),
        "Screener": cand["Screener"].to_numpy(),
        "Ticker": cand["Ticker"].str.replace(".JK", "", regex=False).to_numpy(),
        "Harga catat": cand["Harga"].to_numpy(),
        "TP (%)": cand["TP (%)"].to_numpy(),
        "Hari": cand["Hari"].to_numpy(),
        "Winrate backtest (%)": cand["Winrate (%)"].to_numpy(),
        "Sinyal lalu": cand["Sinyal lalu"].to_numpy(),
        "Expectancy backtest (%)": cand["Expectancy (%)"].to_numpy(),
    })[LOG_COLS]


def save_log(df: pd.DataFrame, path: Path = LOG_FILE) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def evaluate(log: pd.DataFrame, prices: dict) -> pd.DataFrame:
    """Cocokkan tiap sinyal dengan data harga. Entry = Harga catat.
    Hasil: TP bila High salah satu dari `Hari` hari bursa berikutnya >= entry*(1+TP);
    jika tidak, keluar di close hari terakhir. Return belum termasuk fee."""
    out = log.copy()
    res, ret, hi, gap = [], [], [], []
    for _, r in out.iterrows():
        df = prices.get(f"{r['Ticker']}.JK")
        d0 = pd.Timestamp(r["Tanggal"])
        status, rt, mx, g = "Menunggu", None, None, None
        if df is not None and not df.empty:
            day0 = df.loc[df.index == d0]
            if not day0.empty and day0["Volume"].iloc[0] > 0 and r["Harga catat"]:
                g = (day0["Close"].iloc[0] / r["Harga catat"] - 1) * 100
            fut = df.loc[df.index > d0]
            fut = fut[fut["Volume"] > 0].head(int(r["Hari"]))
            if len(fut) >= int(r["Hari"]):
                entry = float(r["Harga catat"])
                target = entry * (1 + r["TP (%)"] / 100)
                mx = (fut["High"].max() / entry - 1) * 100
                if fut["High"].max() >= target:
                    status, rt = "TP", float(r["TP (%)"])
                else:
                    status, rt = "Tidak TP", (fut["Close"].iloc[-1] / entry - 1) * 100
        res.append(status); ret.append(rt); hi.append(mx); gap.append(g)
    out["Hasil"] = res
    out["Return (%)"] = ret
    out["High maks (%)"] = hi
    out["Close final vs harga catat (%)"] = gap
    return out


def summarize_log(ev: pd.DataFrame) -> pd.DataFrame:
    """Per paket: winrate aktual vs rata-rata winrate backtest saat sinyal dicatat."""
    done = ev[ev["Hasil"] != "Menunggu"]
    if done.empty:
        return pd.DataFrame()
    rows = []
    for name, g in done.groupby("Screener"):
        bt = g["Winrate backtest (%)"].dropna()
        rows.append({
            "Screener": name,
            "Selesai": len(g),
            "Winrate aktual (%)": round((g["Hasil"] == "TP").mean() * 100, 1),
            "Winrate backtest rata-rata (%)": round(bt.mean(), 1) if len(bt) else None,
            "Return rata-rata (%)": round(g["Return (%)"].mean(), 2),
            "Close final vs harga catat (%)": round(g["Close final vs harga catat (%)"].mean(), 2)
            if g["Close final vs harga catat (%)"].notna().any() else None,
        })
    return pd.DataFrame(rows).sort_values("Selesai", ascending=False).reset_index(drop=True)
