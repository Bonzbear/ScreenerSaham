"""Simulasi TP/SL pada data harian.

Aturan (sengaja konservatif supaya angka tidak terlalu bagus):
- Entry di harga close hari sinyal (D), + slippage.
- Dicek hari D+1 ... D+hold_days.
- TP kena jika High >= TP. SL (opsional) kena jika Low <= SL.
- Jika TP dan SL kena di hari yang sama -> dianggap SL kena duluan.
- Jika harga buka sudah melewati TP/SL (gap) -> keluar di harga buka.
- Jika sampai hari terakhir TP/SL tidak kena -> keluar di close hari terakhir.
  (Tanpa SL, ini mewakili "tahan, lalu CL/keluar" — besarnya bisa untung atau rugi.)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADE_COLS = ["Ticker", "Date", "Entry", "Exit", "Outcome", "TPTouched", "GrossRet", "NetRet"]


@dataclass
class BacktestParams:
    tp_pct: float = 1.5
    sl_pct: float = 0.0          # 0 = tanpa SL
    hold_days: int = 1           # D+1 secara default
    buy_fee_pct: float = 0.15
    sell_fee_pct: float = 0.25   # termasuk pajak jual; sesuaikan dengan broker kamu
    slippage_pct: float = 0.0    # tambahan biaya entry (mis. bid di atas IEP)


def simulate(d: pd.DataFrame, sig_pos: np.ndarray, p: BacktestParams) -> pd.DataFrame:
    """d: DataFrame hasil prepare(); sig_pos: posisi baris (integer) yang bersinyal."""
    N = int(p.hold_days)
    n = len(d)
    pos = np.asarray(sig_pos, dtype=int)
    pos = pos[pos + N < n]  # hanya sinyal yang jendelanya lengkap
    if len(pos) == 0:
        return pd.DataFrame(columns=TRADE_COLS[1:])

    O = d["Open"].to_numpy(float)
    H = d["High"].to_numpy(float)
    L = d["Low"].to_numpy(float)
    C = d["Close"].to_numpy(float)

    m = len(pos)
    entry = C[pos] * (1 + p.slippage_pct / 100)
    tp = entry * (1 + p.tp_pct / 100)
    sl = entry * (1 - p.sl_pct / 100) if p.sl_pct > 0 else np.full(m, -np.inf)

    exit_price = np.full(m, np.nan)
    outcome = np.full(m, "", dtype=object)
    alive = np.ones(m, bool)
    touched = np.zeros(m, bool)  # TP tersentuh High di hari mana pun (mengabaikan SL)

    for k in range(1, N + 1):
        j = pos + k
        o, h, l = O[j], H[j], L[j]
        touched |= h >= tp

        gap_sl = alive & (o <= sl)
        gap_tp = alive & ~gap_sl & (o >= tp)
        rest = alive & ~gap_sl & ~gap_tp
        sl_hit = rest & (l <= sl)           # termasuk kasus TP & SL sama hari -> SL duluan
        tp_hit = rest & ~sl_hit & (h >= tp)

        gap = gap_sl | gap_tp
        exit_price[gap] = o[gap]
        outcome[gap_sl] = "SL"
        outcome[gap_tp] = "TP"
        exit_price[sl_hit] = sl[sl_hit]
        outcome[sl_hit] = "SL"
        exit_price[tp_hit] = tp[tp_hit]
        outcome[tp_hit] = "TP"
        alive &= ~(gap | sl_hit | tp_hit)

    exit_price[alive] = C[pos[alive] + N]
    outcome[alive] = "TIME"

    gross = exit_price / entry - 1
    net = exit_price * (1 - p.sell_fee_pct / 100) / (entry * (1 + p.buy_fee_pct / 100)) - 1
    return pd.DataFrame(
        {
            "Date": d.index[pos],
            "Entry": entry,
            "Exit": exit_price,
            "Outcome": outcome,
            "TPTouched": touched,
            "GrossRet": gross,
            "NetRet": net,
        }
    )


def summarize(t: pd.DataFrame) -> dict:
    n = len(t)
    if n == 0:
        return {"n": 0}
    net = t["NetRet"].astype(float)
    wins, losses = net[net > 0], net[net <= 0]
    loss_sum = abs(losses.sum())
    return {
        "n": n,
        "winrate": float((t["Outcome"] == "TP").mean() * 100),          # TP kena (hasil simulasi)
        "winrate_simple": float(t["TPTouched"].mean() * 100),           # High >= TP, abaikan SL
        "sl_pct": float((t["Outcome"] == "SL").mean() * 100),
        "time_pct": float((t["Outcome"] == "TIME").mean() * 100),       # keluar karena waktu habis
        "time_positive_pct": float(
            ((t["Outcome"] == "TIME") & (net > 0)).sum() / max((t["Outcome"] == "TIME").sum(), 1) * 100
        ),
        "avg_win": float(wins.mean() * 100) if len(wins) else 0.0,
        "avg_loss": float(losses.mean() * 100) if len(losses) else 0.0,
        "expectancy": float(net.mean() * 100),
        "profit_factor": float(wins.sum() / loss_sum) if loss_sum > 0 else float("inf"),
    }
