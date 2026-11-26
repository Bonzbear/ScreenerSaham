"""Uji: simulasi vectorized vs loop naif, dan alur engine dengan data sintetis.
Jalankan dari root repo:  python -m screener_baru.test_engine
"""
import numpy as np
import pandas as pd

from .backtest import BacktestParams, simulate
from .engine import run
from .screener import DEFAULT_CRITERIA, prepare, signal_mask


def make_prices(seed=0, n=400, liquid=True):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n)
    close = 1000 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, n)))
    open_ = close * (1 + rng.normal(0, 0.008, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    vol = rng.integers(8_000_000, 30_000_000, n) if liquid else rng.integers(100, 1000, n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def naive(d, pos, p):
    out = []
    for i in pos:
        if i + p.hold_days >= len(d):
            continue
        entry = d.Close.iloc[i] * (1 + p.slippage_pct / 100)
        tp = entry * (1 + p.tp_pct / 100)
        sl = entry * (1 - p.sl_pct / 100) if p.sl_pct > 0 else None
        res, ex, touched = None, None, False
        for k in range(1, p.hold_days + 1):
            o, h, l = d.Open.iloc[i + k], d.High.iloc[i + k], d.Low.iloc[i + k]
            touched |= h >= tp
            if res:
                continue
            if sl is not None and o <= sl:
                res, ex = "SL", o
            elif o >= tp:
                res, ex = "TP", o
            elif sl is not None and l <= sl:
                res, ex = "SL", sl
            elif h >= tp:
                res, ex = "TP", tp
        if not res:
            res, ex = "TIME", d.Close.iloc[i + p.hold_days]
        net = ex * (1 - p.sell_fee_pct / 100) / (entry * (1 + p.buy_fee_pct / 100)) - 1
        out.append((res, ex, touched, net))
    return out


def test_simulate_matches_naive():
    for seed in range(5):
        d = prepare(make_prices(seed), 5)
        pos = np.arange(25, len(d) - 1, 3)
        for p in [
            BacktestParams(),
            BacktestParams(tp_pct=1.0, sl_pct=1.0, hold_days=3),
            BacktestParams(tp_pct=2.0, sl_pct=0.5, hold_days=5, slippage_pct=0.2),
            BacktestParams(tp_pct=0.5, sl_pct=0, hold_days=4),
        ]:
            fast = simulate(d, pos, p)
            slow = naive(d, pos, p)
            assert len(fast) == len(slow), (seed, p)
            for (_, r), (res, ex, touched, net) in zip(fast.iterrows(), slow):
                assert r.Outcome == res
                assert abs(r.Exit - ex) < 1e-9
                assert bool(r.TPTouched) == touched
                assert abs(r.NetRet - net) < 1e-12
    print("OK simulate == naive")


def test_same_day_tp_sl_is_loss():
    idx = pd.bdate_range("2024-01-01", periods=40)
    df = pd.DataFrame({"Open": 100.0, "High": 100.0, "Low": 100.0, "Close": 100.0, "Volume": 1e7}, index=idx)
    df.iloc[30, df.columns.get_loc("High")] = 105  # TP 2% kena
    df.iloc[30, df.columns.get_loc("Low")] = 95    # SL 2% juga kena
    d = prepare(df, 5)
    t = simulate(d, np.array([29]), BacktestParams(tp_pct=2, sl_pct=2, hold_days=1))
    assert t.Outcome.iloc[0] == "SL" and bool(t.TPTouched.iloc[0])
    print("OK TP&SL sama hari -> SL")


def test_engine_flow():
    prices = {f"T{i}.JK": make_prices(i) for i in range(30)}
    prices["ILLIQ.JK"] = make_prices(99, liquid=False)
    last = max(df.index[-1] for df in prices.values())
    crit = dict(DEFAULT_CRITERIA, min_avg_value=1e9, min_value_today=1e9)
    cand, trades, o = run(prices, last, crit, BacktestParams(tp_pct=1.5, hold_days=2), 365)
    assert not trades.empty and "ILLIQ.JK" not in set(trades.Ticker)
    assert trades.Date.max() < last           # tidak ada kebocoran masa depan
    assert o["n"] == len(trades) and 0 <= o["winrate"] <= 100
    print("OK engine:", o["n"], "sinyal, winrate", round(o["winrate"], 1), "kandidat", len(cand))
    # tanggal di masa lalu tidak boleh memakai data setelahnya
    past = prices["T0.JK"].index[200]
    _, tr2, _ = run(prices, past, crit, BacktestParams(), 365)
    assert tr2.empty or tr2.Date.max() < past
    print("OK tanpa look-ahead")


if __name__ == "__main__":
    test_simulate_matches_naive()
    test_same_day_tp_sl_is_loss()
    test_engine_flow()
