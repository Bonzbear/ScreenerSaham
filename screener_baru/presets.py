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

Syarat tambahan paket Pullback (parameter bisa diubah / dimatikan dengan 0):
- Naik tinggi sebelumnya : High tertinggi dalam N hari terakhir (sampai kemarin) minimal x% di atas garis
                           (garis dihitung pada hari masing-masing).
- Sentuhan pertama       : sejak hari puncak itu, tidak pernah ada hari dengan Low <= garis (sampai kemarin).
- Datang dari atas       : close kemarin di atas garis dan close hari ini turun dibanding kemarin.
Kolom "Jarak ke garis (%)" = (Close / garis - 1) x 100; makin kecil makin dekat.
Kolom "Bonus" = syarat "lebih baik jika ..." yang terpenuhi (tidak menyaring, hanya informasi).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
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
    # extras(d, p) -> {nama: Series}. Series bool = Bonus (ditulis di kolom "Bonus"),
    # Series angka = kolom informasi tambahan.
    extras: Optional[Callable[[pd.DataFrame, dict], dict]] = None
    # conditions(d, p) -> [(label, Series bool), ...]; dipakai panel "Periksa saham"
    conditions: Optional[Callable[[pd.DataFrame, dict], list]] = None

    def defaults(self) -> dict:
        return {k: v.default for k, v in self.params.items()}


# ---------------------------------------------------------------- indikator
def sma(d: pd.DataFrame, n) -> pd.Series:
    return d["Close"].rolling(int(n)).mean()


def ema(d: pd.DataFrame, n) -> pd.Series:
    n = int(n)
    return d["Close"].ewm(span=n, adjust=False, min_periods=n).mean()


def line(d: pd.DataFrame, n, kind=0) -> pd.Series:
    """Garis MA: kind 0 = SMA, 1 = EMA."""
    return ema(d, n) if int(kind) == 1 else sma(d, n)


def bollinger(d: pd.DataFrame, n=20, k=2.0):
    mid = sma(d, n)
    sd = d["Close"].rolling(int(n)).std(ddof=0)
    return mid, mid - k * sd, mid + k * sd


def peak_and_touches(d: pd.DataFrame, ln: pd.Series, window: int):
    """Untuk tiap hari t (jendela = N hari sebelum t, t tidak ikut):
    - peak   : nilai terbesar dari (High/garis - 1) di jendela itu
    - touches: jumlah hari SETELAH hari puncak sampai kemarin yang Low-nya <= garis hari itu
    NaN bila jendela belum penuh atau garis belum tersedia."""
    n, W = len(d), int(window)
    peak = np.full(n, np.nan)
    touches = np.full(n, np.nan)
    if n > W > 0:
        ext = (d["High"] / ln - 1).to_numpy(float)
        touched = (d["Low"] <= ln).to_numpy(bool)
        e = np.where(np.isnan(ext), -np.inf, ext)
        cs = np.concatenate([[0], np.cumsum(touched)])  # cs[k] = jumlah touched di indeks [0, k)
        win = np.lib.stride_tricks.sliding_window_view(e, W)[: n - W]  # baris i = e[i : i+W], t = i+W
        am, pv = win.argmax(axis=1), win.max(axis=1)
        t = np.arange(W, n)
        pidx = t - W + am
        ok = np.isfinite(pv)
        peak[W:][ok] = pv[ok]
        touches[W:][ok] = (cs[t] - cs[pidx + 1])[ok]
    return pd.Series(peak, index=d.index), pd.Series(touches, index=d.index)


def _value_ok(d, p):
    return d["Value"] > p["min_value"] * BILLION


# --------------------------------------------------------------------- rumus
# Tiap paket ditulis sebagai daftar syarat bernama [(label, Series bool), ...]; sinyal = semua syarat terpenuhi.
def _all_of(conds):
    m = None
    for _, s in conds:
        s = s.fillna(False).astype(bool)
        m = s if m is None else (m & s)
    return m


def pullback_ma_conds(d, p):
    ma = line(d, p["ma_period"], p["ma_type"])
    c = d["Close"]
    prev_llv = d["Low"].rolling(int(p["llv_days"])).min().shift(1)
    conds = [
        ("Low terendah N hari (sampai kemarin) di atas MA", prev_llv > ma),
        ("Close ≥ batas bawah × MA", c >= ma * p["low_tol"]),
        ("Close ≤ batas atas × MA", c <= ma * p["high_tol"]),
        ("Nilai transaksi hari ini cukup", _value_ok(d, p)),
    ]
    if p["need_trend"]:
        conds.append(("MA50 > MA200", line(d, 50, p["ma_type"]) > line(d, 200, p["ma_type"])))
    if p["min_ext_pct"] > 0 or p["need_first_touch"]:
        peak, touches = peak_and_touches(d, ma, p["peak_window"])
        if p["min_ext_pct"] > 0:
            conds.append(("Naik tinggi sebelumnya (puncak ≥ x% di atas MA)", peak * 100 >= p["min_ext_pct"]))
        if p["need_first_touch"]:
            conds.append(("Sentuhan pertama sejak puncak", touches == 0))
    if p["need_from_above"]:
        conds.append(("Datang dari atas (close kemarin > MA & close turun)", (c.shift(1) > ma) & (c < c.shift(1))))
    return conds


def pullback_ma_extras(d, p):
    ma = line(d, p["ma_period"], p["ma_type"])
    return {"Jarak ke garis (%)": (d["Close"] / ma - 1) * 100}


def pullback_bb_mid_conds(d, p):
    mid, low, up = bollinger(d, 20, 2)
    bw = (up - low) / mid
    c = d["Close"]
    conds = [
        ("Close ≥ batas bawah × BB mid", c >= mid * p["low_tol"]),
        ("Close ≤ batas atas × BB mid", c <= mid * p["high_tol"]),
        ("Nilai transaksi hari ini cukup", _value_ok(d, p)),
        ("EMA10 > EMA20", ema(d, 10) > ema(d, 20)),
        ("EMA20 > EMA50", ema(d, 20) > ema(d, 50)),
        ("Bandwidth Bollinger cukup", bw >= p["min_bandwidth"]),
        ("Close > BB mid", c > mid),
    ]
    if p["min_ext_pct"] > 0 or p["need_first_touch"]:
        peak, touches = peak_and_touches(d, mid, p["peak_window"])
        if p["min_ext_pct"] > 0:
            conds.append(("Naik tinggi sebelumnya (puncak ≥ x% di atas BB mid)", peak * 100 >= p["min_ext_pct"]))
        if p["need_first_touch"]:
            conds.append(("Sentuhan pertama ke BB mid sejak puncak", touches == 0))
    if p["need_from_above"]:
        conds.append(("Datang dari atas (close kemarin > BB mid & close turun)", (c.shift(1) > mid) & (c < c.shift(1))))
    return conds


def pullback_bb_mid_extras(d, p):
    mid, _, up = bollinger(d, 20, 2)
    hit_upper = (d["High"] > up).astype(float).rolling(int(p["peak_window"])).max().shift(1) == 1
    return {
        "Jarak ke garis (%)": (d["Close"] / mid - 1) * 100,
        "Pernah tembus BB atas": hit_upper,
    }


def bb_reversal_conds(d, p):
    _, bottom, _ = bollinger(d, 20, 2)
    c, o = d["Close"], d["Open"]
    conds = [
        ("Low kemarin < BB bawah", d["Low"].shift(1) < bottom),
        ("Close kemarin < BB bawah", c.shift(1) < bottom),
        ("Close hari ini > BB bawah", c > bottom),
        ("Nilai transaksi hari ini cukup", _value_ok(d, p)),
        ("Volume > volume kemarin", d["Volume"] > d["Volume"].shift(1)),
        ("High kemarin < High hari ini", d["High"].shift(1) < d["High"]),
        ("Close > close kemarin", c > c.shift(1)),
    ]
    if p["need_body"]:
        conds.append(("Body candle > body kemarin", (c - o).abs() > (c.shift(1) - o.shift(1)).abs()))
    return conds


def bb_reversal_extras(d, p):
    return {"Low lebih tinggi dari kemarin": d["Low"] > d["Low"].shift(1)}


def magic_v11_conds(d, p):
    c = d["Close"]
    return [
        ("Volume > volume kemarin", d["Volume"] > d["Volume"].shift(1)),
        ("Close kemarin < close hari ini", c.shift(1) < c),
        ("Close > SMA", c > sma(d, p["sma_period"])),
        ("Nilai transaksi hari ini cukup", _value_ok(d, p)),
    ]


def magic_v12_conds(d, p):
    c, s5 = d["Close"], sma(d, p["sma_period"])
    return [
        ("Close > SMA", c > s5),
        ("Close kemarin > SMA", c.shift(1) > s5),
        ("Close 2 hari lalu > SMA", c.shift(2) > s5),
        ("High 2 hari lalu / close 3 hari lalu ≥ batas", d["High"].shift(2) / c.shift(3) >= p["jump"]),
        ("Close kemarin < close 2 hari lalu", c.shift(1) < c.shift(2)),
        ("Close hari ini < close kemarin", c < c.shift(1)),
        ("Nilai transaksi hari ini cukup", _value_ok(d, p)),
    ]


def magic_v21_conds(d, p):
    return magic_v11_conds(d, p) + [
        ("High hari ini / close kemarin ≥ batas", d["High"] / d["Close"].shift(1) >= p["high_jump"]),
    ]


def magic_continuation_extras(d, p):
    c, o, h = d["Close"], d["Open"], d["High"]
    body = (c - o).abs()
    return {
        "Close=High (≤0,5%)": c >= h * 0.995,
        "Candle lebih kuat dari kemarin": body > body.shift(1),
        "Volume > 1,5x rata-rata 20 hari": d["Volume"] > 1.5 * d["Volume"].rolling(20).mean(),
    }


def magic_reversal_extras(d, p):
    c, o, l = d["Close"], d["Open"], d["Low"]
    body = (c - o).abs()
    lower_wick = d[["Open", "Close"]].min(axis=1) - l
    return {"Ekor bawah panjang (≥2x body)": (lower_wick > 0) & (lower_wick >= 2 * body)}


# ------------------------------------------------------------------ parameter
_VAL = lambda default: Param("Nilai transaksi hari ini min (Rp miliar)", default, 0.5, "%.1f")  # noqa: E731
_TOL_LO = lambda default: Param("Batas bawah (x garis)", default, 0.005, "%.3f")  # noqa: E731
_TOL_HI = lambda default: Param("Batas atas (x garis)", default, 0.005, "%.3f")  # noqa: E731
_YN = lambda label, default: Param(f"{label} (1 = ya, 0 = tidak)", default, 1, "%.0f")  # noqa: E731


def _ma_params(period: int, ext_pct: float, window: int) -> dict:
    return {
        "ma_period": Param("Periode MA", period, 1, "%.0f"),
        "ma_type": Param("Jenis garis (0 = SMA, 1 = EMA)", 0, 1, "%.0f"),
        "llv_days": Param("Low terendah N hari (kemarin) di atas MA", 5, 1, "%.0f"),
        "low_tol": _TOL_LO(0.99),
        "high_tol": _TOL_HI(1.02),
        "min_value": _VAL(1.0),
        "need_trend": _YN("Wajib MA50 > MA200", 1),
        "min_ext_pct": Param("Naik tinggi sebelumnya: High min x% di atas garis (0 = abaikan)", ext_pct, 1, "%.0f"),
        "peak_window": Param("Cari puncak dalam N hari terakhir", window, 5, "%.0f"),
        "need_first_touch": _YN("Wajib sentuhan pertama sejak puncak", 1),
        "need_from_above": _YN("Wajib datang dari atas (close kemarin > garis & close turun)", 1),
    }


def _preset(name, conds_fn, params, **kw) -> Preset:
    return Preset(name, lambda d, p, _f=conds_fn: _all_of(_f(d, p)), params, conditions=conds_fn, **kw)


PRESETS: list[Preset] = [
    _preset("Pullback MA50", pullback_ma_conds, _ma_params(50, 15, 60), extras=pullback_ma_extras),
    _preset("Pullback MA200", pullback_ma_conds, _ma_params(200, 25, 120), extras=pullback_ma_extras),
    _preset(
        "Pullback BB Mid",
        pullback_bb_mid_conds,
        {
            "low_tol": _TOL_LO(0.98),
            "high_tol": _TOL_HI(1.02),
            "min_bandwidth": Param("Bandwidth Bollinger minimum", 0.10, 0.01, "%.2f"),
            "min_value": _VAL(1.0),
            "min_ext_pct": Param("Naik tinggi sebelumnya: High min x% di atas BB mid (0 = abaikan)", 8, 1, "%.0f"),
            "peak_window": Param("Cari puncak dalam N hari terakhir", 30, 5, "%.0f"),
            "need_first_touch": _YN("Wajib sentuhan pertama ke BB mid sejak puncak", 1),
            "need_from_above": _YN("Wajib datang dari atas (close kemarin > BB mid & close turun)", 1),
        },
        extras=pullback_bb_mid_extras,
    ),
    _preset(
        "BB Reversal",
        bb_reversal_conds,
        {"min_value": _VAL(1.0), "need_body": _YN("Wajib body candle > body kemarin", 1)},
        extras=bb_reversal_extras,
    ),
    _preset(
        "Magic V1.1 & V1.3",
        magic_v11_conds,
        {"sma_period": Param("Periode SMA", 5, 1, "%.0f"), "min_value": _VAL(5.0)},
        extras=magic_continuation_extras,
    ),
    _preset(
        "Magic V1.2",
        magic_v12_conds,
        {
            "sma_period": Param("Periode SMA", 5, 1, "%.0f"),
            "jump": Param("High 2 hari lalu / close 3 hari lalu min", 1.10, 0.01, "%.2f"),
            "min_value": _VAL(1.0),
        },
        extras=magic_reversal_extras,
    ),
    _preset(
        "Magic V2.1",
        magic_v21_conds,
        {
            "sma_period": Param("Periode SMA", 5, 1, "%.0f"),
            "high_jump": Param("High hari ini / close kemarin min", 1.10, 0.01, "%.2f"),
            "min_value": _VAL(5.0),
        },
        extras=magic_continuation_extras,
    ),
]

PRESET_BY_NAME = {p.name: p for p in PRESETS}
