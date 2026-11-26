"""Orkestrasi: jalankan satu/banyak strategi (paket screener) pada satu tanggal + backtest historis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .backtest import TRADE_COLS, BacktestParams, simulate, summarize
from .presets import Preset
from .screener import prepare

MIN_SAMPLE = 10  # di bawah ini winrate per saham dianggap sampel kecil
TRADE_COLS_S = ["Ticker", "Screener"] + TRADE_COLS[1:]


@dataclass
class Strategy:
    name: str                                   # tampil di kolom "Screener" ("-" untuk manual)
    mask: Callable[[pd.DataFrame], pd.Series]   # d (hasil prepare) -> boolean per hari
    bt: BacktestParams


def strategy_from_preset(preset: Preset, values: dict | None, bt: BacktestParams) -> Strategy:
    values = {**preset.defaults(), **(values or {})}
    name = preset.name if values == preset.defaults() else f"{preset.name} (diubah)"
    return Strategy(name, lambda d, _v=values: preset.mask(d, _v), bt)


def run(
    prices: dict[str, pd.DataFrame],
    screen_date,
    strategies: list[Strategy],
    lookback_days: int = 730,
    min_sample: int = MIN_SAMPLE,
):
    """Return (kandidat_df, trades_df).

    Backtest hanya memakai data sampai screen_date (tidak mengintip masa depan) dan
    sinyal historis dari SELURUH saham, bukan hanya kandidat hari ini.
    """
    screen_date = pd.Timestamp(screen_date).normalize()
    start = screen_date - pd.Timedelta(days=lookback_days)

    trade_frames, cands = [], []
    for ticker, raw in prices.items():
        df = raw.loc[:screen_date]
        if len(df) < 30:
            continue
        d = prepare(df)
        if len(d) < 30:
            continue
        for s in strategies:
            mask = s.mask(d).fillna(False).to_numpy(bool)
            pos = np.flatnonzero(mask & (d.index >= start))
            tr = simulate(d, pos, s.bt)
            if not tr.empty:
                tr.insert(0, "Ticker", ticker)
                tr.insert(1, "Screener", s.name)
                trade_frames.append(tr)

            # kandidat hari ini; saham tanpa candle di tanggal itu (suspend/libur) dilewati
            if mask[-1] and d.index[-1] == screen_date:
                last, prev_close = d.iloc[-1], d["PrevClose"].iloc[-1]
                cands.append(
                    {
                        "Screener": s.name,
                        "Ticker": ticker,
                        "Harga": float(last["Close"]),
                        "Naik (%)": round((last["Close"] / prev_close - 1) * 100, 2),
                        "Nilai (Rp M)": round(last["Value"] / 1e9, 1),
                        "Warning": last["Warning"],
                        "TP (%)": s.bt.tp_pct,
                        "SL (%)": s.bt.sl_pct,
                        "Hari": s.bt.hold_days,
                    }
                )

    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame(columns=TRADE_COLS_S)
    if not cands:
        return pd.DataFrame(), trades

    stats = {k: summarize(g) for k, g in trades.groupby(["Ticker", "Screener"])} if not trades.empty else {}
    show_sl = any(s.bt.sl_pct > 0 for s in strategies)
    rows = []
    for r in cands:
        s = stats.get((r["Ticker"], r["Screener"]), {"n": 0})
        n = s["n"]
        r = dict(r)
        r["Sinyal lalu"] = n
        r["Winrate (%)"] = round(s["winrate"], 1) if n else None
        if show_sl:
            r["Winrate abaikan SL (%)"] = round(s["winrate_simple"], 1) if n else None
        r["Expectancy (%)"] = round(s["expectancy"], 2) if n else None
        r["Catatan"] = "" if n >= min_sample else ("belum ada riwayat" if n == 0 else "sampel kecil")
        rows.append(r)

    out = pd.DataFrame(rows)
    out["_ok"] = out["Sinyal lalu"] >= min_sample
    out = out.sort_values(
        ["_ok", "Winrate (%)", "Sinyal lalu"], ascending=[False, False, False], na_position="last"
    ).drop(columns="_ok")
    out.insert(0, "Rank", range(1, len(out) + 1))
    out["Ticker"] = out["Ticker"].str.replace(".JK", "", regex=False)
    return out.reset_index(drop=True), trades
