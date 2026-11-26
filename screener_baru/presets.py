"""Paket screener (preset). Tiap paket = nama + parameter + rumus + TP/SL/hari menahan bawaan.

Cara menambah paket baru: tulis fungsi mask(d, p) lalu tambahkan Preset(...) ke daftar PRESETS
di paling bawah. Parameter (p) otomatis muncul sebagai kolom isian di sidebar.

Aturan pembacaan rumus (sama untuk semua paket):
- "prev X" hanya menggeser kolom X itu sendiri satu hari ke belakang; indikator tanpa "prev"
  (SMA, Bollinger, dst.) memakai nilai hari ini. prev_2 = 2 hari lalu, prev_3 = 3 hari lalu.
- "value" = Close x Volume hari itu. Parameter nilai ditulis dalam Rp miliar.
- llv(low,N) = harga Low terendah dalam N hari terakhir; "prev llv" = nilai llv kemarin.
- Bollinger(20,2): mid = SMA20, bawah/atas = mid -/+ 2 x simpangan baku (populasi);
  bandwidth = (atas - bawah) / mid.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

BILLION = 1e9


@dataclass(frozen=True)
class Param:
    label: str
    default: float
    step: float = 0.01
    fmt: str = "%.2f"


@dataclass(frozen=True)
class Preset:
    name: str
    mask: Callable[[pd.DataFrame, dict], pd.Series]
    params: dict
    tp_pct: float = 1.5
    sl_pct: float = 0.0     # 0 = tanpa SL
    hold_days: int = 1      # D+1

    def defaults(self) -> dict:
        return {k: v.default for k, v in self.params.items()}


# ---------------------------------------------------------------- indikator
def sma(d: pd.DataFrame, n) -> pd.Series:
    return d["Close"].rolling(int(n)).mean()


def ema(d: pd.DataFrame, n) -> pd.Series:
    n = int(n)
    return d["Close"].ewm(span=n, adjust=False, min_periods=n).mean()


def bollinger(d: pd.DataFrame, n=20, k=2.0):
    mid = sma(d, n)
    sd = d["Close"].rolling(int(n)).std(ddof=0)
    return mid, mid - k * sd, mid + k * sd


def _value_ok(d, p):
    return d["Value"] > p["min_value"] * BILLION


# --------------------------------------------------------------------- rumus
def pullback_ma(d, p):
    ma = sma(d, p["ma_period"])
    prev_llv = d["Low"].rolling(int(p["llv_days"])).min().shift(1)
    return (
        (prev_llv > ma)
        & (d["Close"] >= ma * p["low_tol"])
        & (d["Close"] <= ma * p["high_tol"])
        & _value_ok(d, p)
    )


def pullback_bb_mid(d, p):
    mid, low, up = bollinger(d, 20, 2)
    bw = (up - low) / mid
    c = d["Close"]
    return (
        (c >= mid * p["low_tol"])
        & (c <= mid * p["high_tol"])
        & _value_ok(d, p)
        & (ema(d, 10) > ema(d, 20))
        & (ema(d, 20) > ema(d, 50))
        & (bw >= p["min_bandwidth"])
        & (c > mid)
    )


def bb_reversal(d, p):
    _, bottom, _ = bollinger(d, 20, 2)
    c = d["Close"]
    return (
        (d["Low"].shift(1) < bottom)
        & (c.shift(1) < bottom)
        & (c > bottom)
        & _value_ok(d, p)
        & (d["Volume"] > d["Volume"].shift(1))
        & (d["High"].shift(1) < d["High"])
        & (c > c.shift(1))
    )


def magic_v11(d, p):
    c = d["Close"]
    return (
        (d["Volume"] > d["Volume"].shift(1))
        & (c.shift(1) < c)
        & (c > sma(d, p["sma_period"]))
        & _value_ok(d, p)
    )


def magic_v12(d, p):
    c, s5 = d["Close"], sma(d, p["sma_period"])
    return (
        (c > s5)
        & (c.shift(1) > s5)
        & (c.shift(2) > s5)
        & (d["High"].shift(2) / c.shift(3) >= p["jump"])
        & (c.shift(1) < c.shift(2))
        & (c < c.shift(1))
        & _value_ok(d, p)
    )


def magic_v21(d, p):
    c = d["Close"]
    return (
        (d["Volume"] > d["Volume"].shift(1))
        & (c.shift(1) < c)
        & (c > sma(d, p["sma_period"]))
        & _value_ok(d, p)
        & (d["High"] / c.shift(1) >= p["high_jump"])
    )


# ------------------------------------------------------------------ parameter
_VAL = lambda default: Param("Nilai transaksi hari ini min (Rp miliar)", default, 0.5, "%.1f")  # noqa: E731
_TOL_LO = lambda default: Param("Batas bawah (x garis)", default, 0.005, "%.3f")  # noqa: E731
_TOL_HI = lambda default: Param("Batas atas (x garis)", default, 0.005, "%.3f")  # noqa: E731

PRESETS: list[Preset] = [
    Preset(
        "Pullback MA50",
        pullback_ma,
        {
            "ma_period": Param("Periode MA", 50, 1, "%.0f"),
            "llv_days": Param("Low terendah N hari (kemarin) di atas MA", 5, 1, "%.0f"),
            "low_tol": _TOL_LO(0.99),
            "high_tol": _TOL_HI(1.02),
            "min_value": _VAL(1.0),
        },
    ),
    Preset(
        "Pullback MA200",
        pullback_ma,
        {
            "ma_period": Param("Periode MA", 200, 1, "%.0f"),
            "llv_days": Param("Low terendah N hari (kemarin) di atas MA", 5, 1, "%.0f"),
            "low_tol": _TOL_LO(0.99),
            "high_tol": _TOL_HI(1.02),
            "min_value": _VAL(1.0),
        },
    ),
    Preset(
        "Pullback BB Mid",
        pullback_bb_mid,
        {
            "low_tol": _TOL_LO(0.98),
            "high_tol": _TOL_HI(1.02),
            "min_bandwidth": Param("Bandwidth Bollinger minimum", 0.10, 0.01, "%.2f"),
            "min_value": _VAL(1.0),
        },
    ),
    Preset("BB Reversal", bb_reversal, {"min_value": _VAL(1.0)}),
    Preset(
        "Magic V1.1 & V1.3",
        magic_v11,
        {"sma_period": Param("Periode SMA", 5, 1, "%.0f"), "min_value": _VAL(5.0)},
    ),
    Preset(
        "Magic V1.2",
        magic_v12,
        {
            "sma_period": Param("Periode SMA", 5, 1, "%.0f"),
            "jump": Param("High 2 hari lalu / close 3 hari lalu min", 1.10, 0.01, "%.2f"),
            "min_value": _VAL(1.0),
        },
    ),
    Preset(
        "Magic V2.1",
        magic_v21,
        {
            "sma_period": Param("Periode SMA", 5, 1, "%.0f"),
            "high_jump": Param("High hari ini / close kemarin min", 1.10, 0.01, "%.2f"),
            "min_value": _VAL(5.0),
        },
    ),
]

PRESET_BY_NAME = {p.name: p for p in PRESETS}
