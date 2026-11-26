"""Orkestrasi: jalankan screener pada satu tanggal + backtest historis kriteria yang sama."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import TRADE_COLS, BacktestParams, simulate, summarize
from .screener import DEFAULT_CRITERIA, prepare, signal_mask

MIN_SAMPLE = 10  # di bawah ini winrate per saham dianggap sampel kecil


def run(
    prices: dict[str, pd.DataFrame],
    screen_date,
    criteria: dict | None = None,
    bt: BacktestParams | None = None,
    lookback_days: int = 730,
    min_sample: int = MIN_SAMPLE,
):
    """Return (kandidat_df, trades_df, ringkasan_dict).

    Backtest hanya memakai data sampai screen_date (tidak mengintip masa depan) dan
    sinyal historis dari SELURUH saham, bukan hanya kandidat hari ini.
    """
    c = {**DEFAULT_CRITERIA, **(criteria or {})}
    bt = bt or BacktestParams()
    screen_date = pd.Timestamp(screen_date).normalize()
    start = screen_date - pd.Timedelta(days=lookback_days)

    trade_frames, cands = [], []
    for ticker, raw in prices.items():
        df = raw.loc[:screen_date]
        if len(df) < 30:
            continue
        d = prepare(df, c["sma_period"])
        if len(d) < 30:
            continue
        mask = signal_mask(d, c).to_numpy()

        pos = np.flatnonzero(mask & (d.index >= start))
        tr = simulate(d, pos, bt)
        if not tr.empty:
            tr.insert(0, "Ticker", ticker)
            trade_frames.append(tr)

        # kandidat hari ini; saham tanpa candle di tanggal itu (suspend/libur) dilewati
        if mask[-1] and d.index[-1] == screen_date:
            last, prev_close = d.iloc[-1], d["PrevClose"].iloc[-1]
            cands.append(
                {
                    "Ticker": ticker,
                    "Harga": float(last["Close"]),
                    "Naik (%)": round((last["Close"] / prev_close - 1) * 100, 2),
                    "Nilai (Rp M)": round(last["Value"] / 1e9, 1),
                    "Warning": last["Warning"],
                }
            )

    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame(columns=TRADE_COLS)
    overall = summarize(trades)

    if not cands:
        return pd.DataFrame(), trades, overall

    per_ticker = {t: summarize(g) for t, g in trades.groupby("Ticker")} if not trades.empty else {}
    rows = []
    for r in cands:
        s = per_ticker.get(r["Ticker"], {"n": 0})
        n = s["n"]
        r = dict(r)
        r["Sinyal lalu"] = n
        r["Winrate (%)"] = round(s["winrate"], 1) if n else None
        if bt.sl_pct > 0:
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
    return out.reset_index(drop=True), trades, overall
