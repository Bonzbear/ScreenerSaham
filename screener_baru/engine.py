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


def active_dates(prices: dict, min_frac: float = 0.2, min_count: int = 5) -> pd.DatetimeIndex:
    """Hari bursa = tanggal saat cukup banyak saham bertransaksi (membuang baris libur dari Yahoo)."""
    parts = [df.index[df["Volume"] > 0].to_numpy() for df in prices.values() if len(df)]
    if not parts:
        return pd.DatetimeIndex([])
    cnt = pd.Series(np.concatenate(parts)).value_counts()
    thr = min(max(min_count, min_frac * len(prices)), len(prices))
    return pd.DatetimeIndex(cnt[cnt >= thr].index).sort_values()


def align(df: pd.DataFrame, active: pd.DatetimeIndex) -> pd.DataFrame:
    """Samakan dengan chart sekuritas: setiap hari bursa ada satu candle. Hari tanpa transaksi
    diisi harga penutupan sebelumnya dengan Volume 0; baris libur (volume 0 di luar hari bursa) dibuang."""
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.empty:
        return df
    keep = df.index[df["Volume"].fillna(0) > 0]
    idx = active[(active >= df.index[0]) & (active <= df.index[-1])].union(keep)
    out = df.reindex(idx)
    out["Close"] = out["Close"].ffill()
    for col in ("Open", "High", "Low"):
        out[col] = out[col].fillna(out["Close"])
    out["Volume"] = out["Volume"].fillna(0)
    return out.dropna(subset=["Close"])


@dataclass
class Strategy:
    name: str                                   # tampil di kolom "Screener" ("-" untuk manual)
    mask: Callable[[pd.DataFrame], pd.Series]   # d (hasil prepare) -> boolean per hari
    bt: BacktestParams
    extras: Callable[[pd.DataFrame], dict] | None = None  # kolom info & bonus untuk kandidat


def strategy_from_preset(preset: Preset, values: dict | None, bt: BacktestParams) -> Strategy:
    values = {**preset.defaults(), **(values or {})}
    name = preset.name if values == preset.defaults() else f"{preset.name} (diubah)"
    extras = (lambda d, _v=values: preset.extras(d, _v)) if preset.extras else None
    return Strategy(name, lambda d, _v=values: preset.mask(d, _v), bt, extras)


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

    active = active_dates(prices)
    active = active[active <= screen_date]
    trade_frames, cands = [], []
    for ticker, raw in prices.items():
        df = align(raw.loc[:screen_date], active)
        if len(df) < 30:
            continue
        d = prepare(df)
        if len(d) < 30:
            continue
        for s in strategies:
            # tidak ada sinyal (dan entry) pada hari tanpa transaksi
            mask = s.mask(d).fillna(False).to_numpy(bool) & (d["Volume"].to_numpy() > 0)
            pos = np.flatnonzero(mask & (d.index >= start))
            tr = simulate(d, pos, s.bt)
            if not tr.empty:
                tr.insert(0, "Ticker", ticker)
                tr.insert(1, "Screener", s.name)
                trade_frames.append(tr)

            # kandidat hari ini; saham tanpa candle di tanggal itu (suspend/libur) dilewati
            if mask[-1] and d.index[-1] == screen_date:
                last, prev_close = d.iloc[-1], d["PrevClose"].iloc[-1]
                row = {
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
                bonus = []
                for k, ser in (s.extras(d) if s.extras else {}).items():
                    v = ser.iloc[-1]
                    if ser.dtype == bool:
                        if bool(v):
                            bonus.append(k)
                    else:
                        row[k] = None if pd.isna(v) else round(float(v), 2)
                row["Bonus"] = ", ".join(bonus)
                cands.append(row)

    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame(columns=TRADE_COLS_S)
    if not cands:
        return pd.DataFrame(), trades

    stats = {k: summarize(g) for k, g in trades.groupby(["Ticker", "Screener"])} if not trades.empty else {}
    show_sl = any(s.bt.sl_pct > 0 for s in strategies)
    # winrate saham itu pada hari yang sama dengan tanggal screener (mis. semua sinyalnya yang muncul di hari Jumat)
    dow = screen_date.dayofweek
    hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][dow]
    stats_dow = {}
    if not trades.empty:
        same = trades[pd.to_datetime(trades["Date"]).dt.dayofweek == dow]
        stats_dow = {k: summarize(g) for k, g in same.groupby(["Ticker", "Screener"])}
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
        sd = stats_dow.get((r["Ticker"], r["Screener"]), {"n": 0})
        r[f"Winrate {hari} (%)"] = round(sd["winrate"], 1) if sd["n"] else None
        r[f"Sinyal {hari}"] = sd["n"]
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
