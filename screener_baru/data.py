"""Pengambilan & cache data harian Yahoo Finance.

Data disimpan di cache/prices.parquet (format panjang: Ticker, Date, OHLCV).
Update berikutnya hanya mengunduh hari-hari baru, bukan 5 tahun ulang.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

BASE = Path(__file__).parent
CACHE_DIR = BASE / "cache"
CACHE_FILE = CACHE_DIR / "prices.parquet"
NO_DATA_FILE = CACHE_DIR / "no_data.txt"
TICKERS_FILE = BASE / "tickers.txt"

COLS = ["Open", "High", "Low", "Close", "Volume"]
CHUNK = 150          # jumlah saham per request ke Yahoo
OVERLAP_DAYS = 7     # unduh ulang N hari terakhir supaya candle berjalan tertimpa data final

ProgressFn = Callable[[float, str], None]


# ---------------------------------------------------------------- daftar saham
def parse_tickers(text: str) -> list[str]:
    """Terima teks bebas: dipisah koma/spasi/baris, boleh dengan tanda kutip
    atau kurung siku (tempel langsung list Python). Akhiran .JK ditambah otomatis."""
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        for tok in line.replace(",", " ").split():
            t = tok.strip().strip("[]()'\"").upper()
            if not t:
                continue
            if not t.endswith(".JK"):
                t += ".JK"
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def load_tickers(path: Path = TICKERS_FILE) -> list[str]:
    if not path.exists():
        return []
    return parse_tickers(path.read_text(encoding="utf-8"))


def save_tickers(text: str, path: Path = TICKERS_FILE) -> list[str]:
    tickers = parse_tickers(text)
    path.write_text("\n".join(t.replace(".JK", "") for t in tickers) + "\n", encoding="utf-8")
    return tickers


# ---------------------------------------------------------------------- cache
def read_cache() -> pd.DataFrame:
    if not CACHE_FILE.exists():
        return pd.DataFrame(columns=["Ticker", "Date"] + COLS)
    return pd.read_parquet(CACHE_FILE)


def cache_mtime() -> float:
    return CACHE_FILE.stat().st_mtime if CACHE_FILE.exists() else 0.0


def _read_no_data() -> set[str]:
    if NO_DATA_FILE.exists():
        return set(NO_DATA_FILE.read_text().split())
    return set()


def _write_no_data(s: set[str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    NO_DATA_FILE.write_text("\n".join(sorted(s)))


def _download_chunk(chunk: list[str], start: pd.Timestamp) -> Optional[pd.DataFrame]:
    """Kembalikan data format panjang, atau None kalau request gagal."""
    import yfinance as yf

    data = None
    for attempt in range(2):
        try:
            data = yf.download(
                tickers=chunk,
                start=start.strftime("%Y-%m-%d"),
                group_by="ticker",
                progress=False,
                auto_adjust=False,
                threads=True,
            )
            break
        except Exception:
            time.sleep(2)
    if data is None:
        return None
    if data.empty:
        return pd.DataFrame(columns=["Ticker", "Date"] + COLS)

    frames = []
    if isinstance(data.columns, pd.MultiIndex):
        present = set(data.columns.get_level_values(0))
        items = [(t, data[t]) for t in chunk if t in present]
    else:  # satu saham saja
        items = [(chunk[0], data)]
    for t, d in items:
        if not set(COLS).issubset(d.columns):
            continue
        d = d[COLS].dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
        if d.empty:
            continue
        idx = pd.to_datetime(d.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        d.index = idx.normalize()
        d.index.name = "Date"
        d = d.reset_index()
        d.insert(0, "Ticker", t)
        frames.append(d)
    if not frames:
        return pd.DataFrame(columns=["Ticker", "Date"] + COLS)
    return pd.concat(frames, ignore_index=True)


def update_prices(
    tickers: list[str],
    years: int = 5,
    progress: Optional[ProgressFn] = None,
    retry_no_data: bool = False,
) -> dict:
    """Unduh data baru dan gabungkan ke cache. Mengembalikan ringkasan."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = read_cache()
    known = set(cache["Ticker"].unique()) if not cache.empty else set()
    no_data = set() if retry_no_data else _read_no_data()

    todo = [t for t in tickers if t not in no_data]
    old_t = [t for t in todo if t in known]
    new_t = [t for t in todo if t not in known]

    today = pd.Timestamp.today().normalize()
    jobs: list[tuple[list[str], pd.Timestamp]] = []
    if old_t:
        last = pd.to_datetime(cache["Date"]).max()
        start = last - pd.Timedelta(days=OVERLAP_DAYS)
        jobs += [(old_t[i:i + CHUNK], start) for i in range(0, len(old_t), CHUNK)]
    if new_t:
        start = today - pd.Timedelta(days=int(years * 366))
        jobs += [(new_t[i:i + CHUNK], start) for i in range(0, len(new_t), CHUNK)]

    frames = [cache] if not cache.empty else []
    failed_chunks = 0
    new_no_data = set(no_data)
    for n, (chunk, start) in enumerate(jobs, 1):
        if progress:
            progress((n - 1) / max(len(jobs), 1), f"Mengunduh batch {n}/{len(jobs)} dari Yahoo Finance...")
        res = _download_chunk(chunk, start)
        if res is None:
            failed_chunks += 1
            continue
        got = set(res["Ticker"].unique()) if not res.empty else set()
        new_no_data |= {t for t in chunk if t in new_t and t not in got}
        if not res.empty:
            frames.append(res)
        time.sleep(1)  # jeda kecil supaya tidak kena rate limit

    if frames:
        full = pd.concat(frames, ignore_index=True)
        full["Date"] = pd.to_datetime(full["Date"])
        full = (
            full.drop_duplicates(["Ticker", "Date"], keep="last")
            .sort_values(["Ticker", "Date"])
            .reset_index(drop=True)
        )
        full.to_parquet(CACHE_FILE, index=False)
    _write_no_data(new_no_data)
    if progress:
        progress(1.0, "Selesai.")
    return {
        "jobs": len(jobs),
        "failed_chunks": failed_chunks,
        "no_data": len(new_no_data),
        "tickers_in_cache": int(full["Ticker"].nunique()) if frames else 0,
    }


def load_prices(tickers: Optional[list[str]] = None) -> dict[str, pd.DataFrame]:
    """Baca cache -> dict {ticker: DataFrame OHLCV berindeks tanggal, terurut}."""
    df = read_cache()
    if df.empty:
        return {}
    df["Date"] = pd.to_datetime(df["Date"])
    if tickers:
        df = df[df["Ticker"].isin(set(tickers))]
    out = {}
    for t, g in df.groupby("Ticker", sort=False):
        out[t] = g.drop(columns="Ticker").set_index("Date").sort_index()
    return out
