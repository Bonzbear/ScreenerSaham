"""Kriteria screener (vectorized). Nilai default = kriteria `is_signal` di kode lama."""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_CRITERIA = {
    "min_price": 50,                    # harga close minimum
    "max_price": 6500,                  # harga close maksimum
    "ara_buffer_pct": 1.0,              # buang saham yang naik >= (batas ARA - buffer)
    "min_avg_value": 10_000_000_000,    # rata-rata nilai transaksi 20 hari (Rp)
    "min_avg_volume": 1_000_000,        # rata-rata volume 20 hari (lembar)
    "min_value_today": 10_000_000_000,  # nilai transaksi hari ini (Rp)
    "sma_period": 5,
    "need_bullish_candle": True,        # open < close
    "need_volume_up": True,             # volume > volume kemarin
    "need_price_up": True,              # close > close kemarin
    "need_above_sma": True,             # close > SMA
}


def ara_limit(prev_close: pd.Series) -> np.ndarray:
    """Batas ARA persentase berdasarkan harga kemarin (sama seperti kode lama)."""
    p = prev_close.to_numpy(dtype=float)
    return np.where(p < 200, 0.35, np.where(p <= 5000, 0.25, 0.20))


def prepare(df: pd.DataFrame, sma_period: int = 5) -> pd.DataFrame:
    # Hari tanpa transaksi (Volume 0) SENGAJA tetap dipakai supaya MA sama dengan chart sekuritas
    # (saham tipis sering tidak transaksi berhari-hari). Sinyal pada hari volume 0 dicegah di engine.
    d = df.sort_index().dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    d["SMA"] = d["Close"].rolling(sma_period).mean()
    d["VOLMA20"] = d["Volume"].rolling(20).mean()
    d["Value"] = d["Close"] * d["Volume"]
    d["AvgValue20"] = d["Value"].rolling(20).mean()
    d["PrevClose"] = d["Close"].shift(1)
    d["PrevVolume"] = d["Volume"].shift(1)

    body = (d["Close"] - d["Open"]).abs()
    upper_wick = d["High"] - d[["Open", "Close"]].max(axis=1)
    d["Warning"] = np.where((body > 0) & (upper_wick > 1.5 * body), "⚠️", "")
    return d


def signal_mask(d: pd.DataFrame, c: dict) -> pd.Series:
    """Boolean per hari: apakah kriteria terpenuhi pada candle hari itu."""
    chg = d["Close"] / d["PrevClose"] - 1
    near_ara = chg >= (ara_limit(d["PrevClose"]) - c["ara_buffer_pct"] / 100)

    m = (d["Close"] >= c["min_price"]) & (d["Close"] <= c["max_price"])
    m &= ~near_ara.fillna(True)
    m &= (d["AvgValue20"] > c["min_avg_value"]) & (d["VOLMA20"] > c["min_avg_volume"])
    m &= d["Value"] > c["min_value_today"]
    if c["need_bullish_candle"]:
        m &= d["Open"] < d["Close"]
    if c["need_volume_up"]:
        m &= d["Volume"] > d["PrevVolume"]
    if c["need_price_up"]:
        m &= d["Close"] > d["PrevClose"]
    if c["need_above_sma"]:
        m &= d["Close"] > d["Close"].rolling(int(c["sma_period"])).mean()
    return m.fillna(False)
