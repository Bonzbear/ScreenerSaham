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
    from .engine import Strategy
    from .screener import signal_mask
    prices = {f"T{i}.JK": make_prices(i) for i in range(30)}
    prices["ILLIQ.JK"] = make_prices(99, liquid=False)
    last = max(df.index[-1] for df in prices.values())
    crit = dict(DEFAULT_CRITERIA, min_avg_value=1e9, min_value_today=1e9)
    st = [Strategy("-", lambda d: signal_mask(d, crit), BacktestParams(tp_pct=1.5, hold_days=2))]
    cand, trades = run(prices, last, st, 365)
    assert not trades.empty and "ILLIQ.JK" not in set(trades.Ticker)
    assert trades.Date.max() < last           # tidak ada kebocoran masa depan
    assert set(trades.Screener) == {"-"}
    print("OK engine:", len(trades), "sinyal, kandidat", len(cand))
    past = prices["T0.JK"].index[200]
    _, tr2 = run(prices, past, st, 365)
    assert tr2.empty or tr2.Date.max() < past
    print("OK tanpa look-ahead")


# ------------------------------------------------------------ paket vs hitungan naif
def naive_preset(name, d, p):
    """Terapkan rumus apa adanya, satu baris per satu baris (tanpa rolling/shift pandas)."""
    C, H, L, V, Val = (d[c].to_numpy(float) for c in ["Close", "High", "Low", "Volume", "Value"])
    n = len(d)
    out = np.zeros(n, bool)

    def sma(i, k):
        k = int(k)
        return C[i - k + 1:i + 1].mean() if i >= k - 1 else np.nan

    def ema_series(k):
        k = int(k); a = 2 / (k + 1)
        e = np.empty(n); e[0] = C[0]
        for i in range(1, n):
            e[i] = a * C[i] + (1 - a) * e[i - 1]
        e[:k - 1] = np.nan
        return e

    def bb(i, k=20, m=2.0):
        w = C[i - k + 1:i + 1]
        mid, sd = w.mean(), w.std()
        return mid, mid - m * sd, mid + m * sd

    e10, e20, e50 = ema_series(10), ema_series(20), ema_series(50)
    val_ok = lambda i: Val[i] > p["min_value"] * 1e9
    for i in range(n):
        try:
            if name.startswith("Pullback MA"):
                k, ld = int(p["ma_period"]), int(p["llv_days"])
                if i < k - 1 or i - ld < 0:
                    continue
                ma = sma(i, k)
                prev_llv = L[i - ld:i].min()
                out[i] = prev_llv > ma and p["low_tol"] * ma <= C[i] <= p["high_tol"] * ma and val_ok(i)
            elif name == "Pullback BB Mid":
                if i < 49:
                    continue
                mid, lo, up = bb(i)
                out[i] = (p["low_tol"] * mid <= C[i] <= p["high_tol"] * mid and val_ok(i) and e10[i] > e20[i]
                          and e20[i] > e50[i] and (up - lo) / mid >= p["min_bandwidth"] and C[i] > mid)
            elif name == "BB Reversal":
                if i < 20:
                    continue
                _, bot, _ = bb(i)
                out[i] = (L[i - 1] < bot and C[i - 1] < bot and C[i] > bot and val_ok(i)
                          and V[i] > V[i - 1] and H[i - 1] < H[i] and C[i] > C[i - 1])
            elif name == "Magic V1.1 & V1.3":
                if i < 1:
                    continue
                out[i] = V[i] > V[i - 1] and C[i - 1] < C[i] and C[i] > sma(i, p["sma_period"]) and val_ok(i)
            elif name == "Magic V1.2":
                if i < 3:
                    continue
                s5 = sma(i, p["sma_period"])
                out[i] = (C[i] > s5 and C[i - 1] > s5 and C[i - 2] > s5 and H[i - 2] / C[i - 3] >= p["jump"]
                          and C[i - 1] < C[i - 2] and C[i] < C[i - 1] and val_ok(i))
            elif name == "Magic V2.1":
                if i < 1:
                    continue
                out[i] = (V[i] > V[i - 1] and C[i - 1] < C[i] and C[i] > sma(i, p["sma_period"]) and val_ok(i)
                          and H[i] / C[i - 1] >= p["high_jump"])
        except FloatingPointError:
            pass
    return out


def test_presets_match_naive():
    from .presets import PRESETS
    loose = {"min_value": 0.001, "low_tol": 0.90, "high_tol": 1.10, "min_bandwidth": 0.0,
             "jump": 1.02, "high_jump": 1.01, "llv_days": 3}
    totals = {p.name: 0 for p in PRESETS}
    for seed in range(8):
        d = prepare(make_prices(seed, n=700))
        for pr in PRESETS:
            p = pr.defaults()
            p.update({k: v for k, v in loose.items() if k in p})
            fast = pr.mask(d, p).fillna(False).to_numpy(bool)
            slow = naive_preset(pr.name, d, p)
            assert (fast == slow).all(), (pr.name, seed, np.flatnonzero(fast != slow)[:5])
            totals[pr.name] += int(fast.sum())
    assert all(v > 0 for v in totals.values()), totals  # pastikan tes tidak kosong
    print("OK paket == hitungan naif; jumlah sinyal uji:", totals)


def test_presets_default_params_run():
    from .presets import PRESETS
    from .engine import strategy_from_preset
    prices = {f"T{i}.JK": make_prices(i, n=700) for i in range(10)}
    last = max(df.index[-1] for df in prices.values())
    sts = [strategy_from_preset(p, None, BacktestParams(tp_pct=p.tp_pct, sl_pct=p.sl_pct, hold_days=p.hold_days)) for p in PRESETS]
    cand, trades = run(prices, last, sts, 600)
    assert set(trades.Screener).issubset({p.name for p in PRESETS})
    s = strategy_from_preset(PRESETS[0], {"min_value": 2.0}, BacktestParams())
    assert s.name.endswith("(diubah)")
    print("OK semua paket jalan;", len(trades), "transaksi")


if __name__ == "__main__":
    test_simulate_matches_naive()
    test_same_day_tp_sl_is_loss()
    test_engine_flow()
    test_presets_match_naive()
    test_presets_default_params_run()
