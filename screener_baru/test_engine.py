"""Uji: simulasi TP/SL, alur engine, dan rumus paket vs implementasi naif (baris per baris).
Jalankan dari root repo:  python -m screener_baru.test_engine
"""
import numpy as np
import pandas as pd

from .backtest import BacktestParams, simulate
from .engine import Strategy, active_dates, align, run, strategy_from_preset
from .presets import PRESETS
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


# ------------------------------------------------------------------ simulasi TP/SL
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
        d = prepare(make_prices(seed))
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
    df.iloc[30, df.columns.get_loc("High")] = 105
    df.iloc[30, df.columns.get_loc("Low")] = 95
    d = prepare(df)
    t = simulate(d, np.array([29]), BacktestParams(tp_pct=2, sl_pct=2, hold_days=1))
    assert t.Outcome.iloc[0] == "SL" and bool(t.TPTouched.iloc[0])
    print("OK TP&SL sama hari -> SL")


def test_engine_flow():
    prices = {f"T{i}.JK": make_prices(i) for i in range(30)}
    prices["ILLIQ.JK"] = make_prices(99, liquid=False)
    last = max(df.index[-1] for df in prices.values())
    crit = dict(DEFAULT_CRITERIA, min_avg_value=1e9, min_value_today=1e9)
    st = [Strategy("-", lambda d: signal_mask(d, crit), BacktestParams(tp_pct=1.5, hold_days=2))]
    cand, trades = run(prices, last, st, 365)
    assert not trades.empty and "ILLIQ.JK" not in set(trades.Ticker)
    assert trades.Date.max() < last
    assert set(trades.Screener) == {"-"}
    print("OK engine:", len(trades), "sinyal, kandidat", len(cand))
    past = prices["T0.JK"].index[200]
    _, tr2 = run(prices, past, st, 365)
    assert tr2.empty or tr2.Date.max() < past
    print("OK tanpa look-ahead")


# ------------------------------------------------------------ paket vs hitungan naif
def naive_preset(name, d, p):
    """Terapkan rumus apa adanya, satu baris per satu baris (tanpa rolling/shift pandas)."""
    C, H, L, O, V, Val = (d[c].to_numpy(float) for c in ["Close", "High", "Low", "Open", "Volume", "Value"])
    n = len(d)
    out = np.zeros(n, bool)

    def sma_arr(k):
        k = int(k)
        a = np.full(n, np.nan)
        for i in range(k - 1, n):
            a[i] = C[i - k + 1:i + 1].mean()
        return a

    def ema_arr(k):
        k = int(k)
        al = 2 / (k + 1)
        e = np.empty(n)
        e[0] = C[0]
        for i in range(1, n):
            e[i] = al * C[i] + (1 - al) * e[i - 1]
        e[:k - 1] = np.nan
        return e

    def line_arr(k, kind):
        return ema_arr(k) if int(kind) == 1 else sma_arr(k)

    def bb_arrays(k=20, m=2.0):
        mid, lo, up = (np.full(n, np.nan) for _ in range(3))
        for i in range(k - 1, n):
            w = C[i - k + 1:i + 1]
            mid[i], sd = w.mean(), w.std()
            lo[i], up[i] = mid[i] - m * sd, mid[i] + m * sd
        return mid, lo, up

    def peak_touch(ln, W):
        W = int(W)
        pv, tc = np.full(n, np.nan), np.full(n, np.nan)
        ext = H / ln - 1
        touched = L <= ln
        for t in range(W, n):
            w = np.where(np.isnan(ext[t - W:t]), -np.inf, ext[t - W:t])
            am = int(np.argmax(w))
            if w[am] == -np.inf:
                continue
            pidx = t - W + am
            pv[t], tc[t] = w[am], touched[pidx + 1:t].sum()
        return pv, tc

    val_ok = lambda i: Val[i] > p["min_value"] * 1e9
    ge = lambda a, b: bool(a >= b)  # NaN -> False

    if name.startswith("Pullback MA"):
        k, ld = int(p["ma_period"]), int(p["llv_days"])
        ma = line_arr(k, p["ma_type"])
        l50, l200 = line_arr(50, p["ma_type"]), line_arr(200, p["ma_type"])
        pv, tc = peak_touch(ma, p["peak_window"])
        for i in range(1, n):
            if i - ld < 0:
                continue
            prev_llv = L[i - ld:i].min()
            ok = prev_llv > ma[i] and p["low_tol"] * ma[i] <= C[i] <= p["high_tol"] * ma[i] and val_ok(i)
            if p["need_trend"]:
                ok = ok and bool(l50[i] > l200[i])
            if p["min_ext_pct"] > 0:
                ok = ok and ge(pv[i] * 100, p["min_ext_pct"])
            if p["need_first_touch"]:
                ok = ok and bool(tc[i] == 0)
            if p["need_from_above"]:
                ok = ok and bool(C[i - 1] > ma[i]) and C[i] < C[i - 1]
            out[i] = ok
    elif name == "Pullback BB Mid":
        mid, lo, up = bb_arrays()
        e10, e20, e50 = ema_arr(10), ema_arr(20), ema_arr(50)
        pv, tc = peak_touch(mid, p["peak_window"])
        for i in range(1, n):
            ok = (p["low_tol"] * mid[i] <= C[i] <= p["high_tol"] * mid[i] and val_ok(i) and bool(e10[i] > e20[i])
                  and bool(e20[i] > e50[i]) and ge((up[i] - lo[i]) / mid[i], p["min_bandwidth"]) and C[i] > mid[i])
            if p["min_ext_pct"] > 0:
                ok = ok and ge(pv[i] * 100, p["min_ext_pct"])
            if p["need_first_touch"]:
                ok = ok and bool(tc[i] == 0)
            if p["need_from_above"]:
                ok = ok and bool(C[i - 1] > mid[i]) and C[i] < C[i - 1]
            out[i] = ok
    elif name == "BB Reversal":
        _, bot, _ = bb_arrays()
        for i in range(1, n):
            ok = (L[i - 1] < bot[i] and C[i - 1] < bot[i] and C[i] > bot[i] and val_ok(i)
                  and V[i] > V[i - 1] and H[i - 1] < H[i] and C[i] > C[i - 1])
            if p["need_body"]:
                ok = ok and abs(C[i] - O[i]) > abs(C[i - 1] - O[i - 1])
            out[i] = ok
    elif name == "Magic V1.1 & V1.3":
        s = sma_arr(p["sma_period"])
        for i in range(1, n):
            out[i] = V[i] > V[i - 1] and C[i - 1] < C[i] and C[i] > s[i] and val_ok(i)
            if p.get("min_naik_pct", 0) > 0:
                out[i] = out[i] and (C[i] / C[i - 1] - 1) * 100 >= p["min_naik_pct"]
    elif name == "Magic V1.2":
        s = sma_arr(p["sma_period"])
        for i in range(3, n):
            out[i] = (C[i] > s[i] and C[i - 1] > s[i] and C[i - 2] > s[i] and H[i - 2] / C[i - 3] >= p["jump"]
                      and C[i - 1] < C[i - 2] and C[i] < C[i - 1] and val_ok(i))
    elif name in ("Magic V2.1", "Magic V2.2"):
        s = sma_arr(p["sma_period"])
        for i in range(1, n):
            out[i] = (V[i] > V[i - 1] and C[i - 1] < C[i] and C[i] > s[i] and val_ok(i)
                      and H[i] / C[i - 1] >= p["high_jump"])
            if p.get("min_naik_pct", 0) > 0:
                out[i] = out[i] and (C[i] / C[i - 1] - 1) * 100 >= p["min_naik_pct"]
    return out


LOOSE = {"min_value": 0.001, "low_tol": 0.90, "high_tol": 1.10, "min_bandwidth": 0.0,
         "jump": 1.02, "high_jump": 1.01, "llv_days": 3, "min_ext_pct": 3, "peak_window": 20}


def _loose(pr, **over):
    p = pr.defaults()
    p.update({k: v for k, v in LOOSE.items() if k in p})
    p.update(over)
    return p


def test_presets_match_naive():
    variants = [("default-longgar", {}), ("naik-min", {"min_naik_pct": 3.0}), ("EMA", {"ma_type": 1}),
                ("tanpa syarat tambahan", {"need_trend": 0, "need_first_touch": 0, "need_from_above": 0,
                                           "min_ext_pct": 0, "need_body": 0})]
    totals = {}
    for seed in range(10):
        d = prepare(make_prices(seed, n=700))
        for label, over in variants:
            for pr in PRESETS:
                p = _loose(pr, **{k: v for k, v in over.items() if k in pr.params})
                fast = pr.mask(d, p).fillna(False).to_numpy(bool)
                slow = naive_preset(pr.name, d, p)
                assert (fast == slow).all(), (pr.name, label, seed, np.flatnonzero(fast != slow)[:5])
                totals[(pr.name, label)] = totals.get((pr.name, label), 0) + int(fast.sum())
    empty = [k for k, v in totals.items() if v == 0]
    assert not empty, f"tes kosong (tidak ada sinyal): {empty}"
    print("OK paket == hitungan naif (3 varian). Contoh jumlah sinyal uji:")
    for k, v in totals.items():
        print("  ", k, v)


def test_syarat_tambahan_mempersempit():
    """Syarat tambahan hanya boleh MENGURANGI sinyal, tidak menambah."""
    for seed in range(5):
        d = prepare(make_prices(seed, n=700))
        for pr in PRESETS:
            if "need_first_touch" not in pr.params and "need_body" not in pr.params:
                continue
            loose_off = _loose(pr, **{k: 0 for k in ("need_trend", "need_first_touch", "need_from_above", "min_ext_pct", "need_body") if k in pr.params})
            on = _loose(pr)
            a = pr.mask(d, loose_off).fillna(False)
            b = pr.mask(d, on).fillna(False)
            assert not (b & ~a).any(), pr.name
    print("OK syarat tambahan hanya mempersempit")


def test_extras_and_engine_columns():
    """Pilih tanggal yang pasti ada sinyal, pastikan kolom info/bonus muncul dan bonus benar."""
    for pr in PRESETS:
        found = False
        for seed in range(30):
            raw = make_prices(seed, n=700)
            d = prepare(raw)
            p = _loose(pr)
            m = pr.mask(d, p).fillna(False).to_numpy(bool)
            idx = [i for i in np.flatnonzero(m) if i > 250]
            if not idx:
                continue
            date = d.index[idx[-1]]
            st = strategy_from_preset(pr, p, BacktestParams())
            cand, _ = run({"X.JK": raw}, date, [st], 600)
            assert len(cand) == 1 and "Bonus" in cand.columns, pr.name
            ex = pr.extras(d, p) if pr.extras else {}
            for k, ser in ex.items():
                if ser.dtype == bool:
                    assert (k in cand.loc[0, "Bonus"]) == bool(ser.loc[date]), (pr.name, k)
                else:
                    assert k in cand.columns
                    assert abs(cand.loc[0, k] - round(float(ser.loc[date]), 2)) < 1e-9
            found = True
            break
        assert found, f"tidak ada tanggal sinyal untuk {pr.name}"
    print("OK kolom info & bonus konsisten dengan extras")


def test_presets_default_params_run():
    prices = {f"T{i}.JK": make_prices(i, n=700) for i in range(10)}
    last = max(df.index[-1] for df in prices.values())
    sts = [strategy_from_preset(p, None, BacktestParams(tp_pct=p.tp_pct, sl_pct=p.sl_pct, hold_days=p.hold_days)) for p in PRESETS]
    cand, trades = run(prices, last, sts, 600)
    assert set(trades.Screener).issubset({p.name for p in PRESETS})
    s = strategy_from_preset(PRESETS[0], {"min_value": 2.0}, BacktestParams())
    assert s.name.endswith("(diubah)")
    print("OK semua paket jalan dengan parameter bawaan;", len(trades), "transaksi")


def _csmi_like():
    """Saham tipis: harga ~230, lonjak ke ~500, lalu banyak hari TANPA transaksi (volume 0, harga datar di 500),
    lalu turun ke 232. Seperti kasus CSMI di Stockbit."""
    idx = pd.bdate_range("2025-06-02", periods=170)
    rows = []
    price = 230.0
    for i, _ in enumerate(idx):
        if i < 100:
            price = 230 + (i % 5)
            vol = 5e6
        elif i < 110:
            price = 230 + (i - 99) * 27          # lonjakan sampai ~500
            vol = 5e7
        elif i < 160:
            vol = 0 if i % 5 else 2e6             # kebanyakan hari tanpa transaksi, harga datar ~500
            price = 500 if i < 155 else 500 - (i - 154) * 45
            vol = vol if i >= 155 else (0 if i % 5 else 2e6)
        else:
            price, vol = 232, 3e7
        rows.append((price, price * 1.003, price * 0.997, price, vol))
    df = pd.DataFrame(rows, index=idx, columns=["Open", "High", "Low", "Close", "Volume"])
    return df


def test_zero_volume_days_dipertahankan_di_MA():
    df = _csmi_like()
    # pasar: 30 saham biasa yang selalu bertransaksi -> hari bursa jelas
    prices = {f"T{i}.JK": make_prices(i, n=170).set_axis(df.index) for i in range(30)}
    prices["CSMI.JK"] = df
    act = active_dates(prices)
    assert len(act) == len(df.index)
    aligned = align(df, act)
    assert len(aligned) == len(df) and (aligned.Volume == 0).sum() == (df.Volume == 0).sum()
    ma_new = prepare(aligned)["Close"].rolling(50).mean().iloc[-1]
    old_style = df[df.Volume > 0]                      # perilaku lama: buang hari volume 0
    ma_old = old_style["Close"].rolling(50).mean().iloc[-1]
    print(f"   MA50 baru (seperti chart) = {ma_new:.0f}, MA50 gaya lama = {ma_old:.0f}, close = {df.Close.iloc[-1]:.0f}")
    assert ma_new > ma_old * 1.15                      # MA yang benar jauh lebih tinggi
    # dengan MA seperti di chart, close ~232 jauh di bawah MA50 -> tidak lolos Pullback MA50
    pr = [p for p in PRESETS if p.name == "Pullback MA50"][0]
    p = pr.defaults(); p["need_trend"] = 0; p["min_value"] = 0.001
    assert not bool(pr.mask(prepare(aligned), p).iloc[-1])
    print("OK hari volume 0 tetap dihitung di MA (MA50 lebih tinggi, close jauh di bawahnya -> tidak lolos)")


def test_align_baris_libur_dibuang_dan_celah_diisi():
    idx = pd.bdate_range("2025-01-01", periods=40)
    prices = {f"T{i}.JK": make_prices(i, n=40).set_axis(idx) for i in range(30)}
    one = prices["T0.JK"].copy()
    holiday = idx[10]
    for k, v in prices.items():                         # hari libur: semua saham volume 0
        if k != "T0.JK":
            v.loc[holiday, "Volume"] = 0
    one.loc[holiday, "Volume"] = 0
    gap = idx[20]
    one = one.drop(gap)                                 # Yahoo tidak punya baris di hari bursa
    prices["T0.JK"] = one
    act = active_dates(prices)
    assert holiday not in act and gap in act
    out = align(one, act)
    assert holiday not in out.index
    assert gap in out.index and out.loc[gap, "Volume"] == 0
    assert out.loc[gap, "Close"] == one.loc[idx[19], "Close"]
    print("OK baris libur dibuang, celah hari bursa diisi")


def test_winrate_hari_sama_per_saham():
    pr = PRESETS[4]  # Magic V1.1 & V1.3
    prices = {f"T{i}.JK": make_prices(i, n=700) for i in range(20)}
    last = max(df.index[-1] for df in prices.values())
    sts = [strategy_from_preset(pr, _loose(pr), BacktestParams())]
    cand, trades = run(prices, last, sts, 600)
    assert not cand.empty
    hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][last.dayofweek]
    assert f"Sinyal {hari}" in cand.columns and f"Winrate {hari} (%)" in cand.columns
    dow = pd.to_datetime(trades["Date"]).dt.dayofweek
    for _, r in cand.iterrows():
        sub = trades[(trades.Ticker == r["Ticker"] + ".JK") & (dow == last.dayofweek)]
        assert int(r[f"Sinyal {hari}"]) == len(sub)
        if len(sub):
            assert abs(r[f"Winrate {hari} (%)"] - round((sub.Outcome == "TP").mean() * 100, 1)) < 1e-9
    print("OK winrate per hari (per saham) cocok dengan hitungan manual")


def test_signal_log():
    import datetime as dt, tempfile, os
    from screener_baru import signal_log as sl
    idx = pd.bdate_range("2025-03-03", periods=6)
    df = pd.DataFrame({"Open": 100.0, "High": [101, 102, 103, 99, 106, 99], "Low": 95.0,
                       "Close": [100, 101, 100, 98, 104, 98], "Volume": 1000}, index=idx)
    prices = {"AAA.JK": df, "BBB.JK": df}
    cand = pd.DataFrame({"Screener": ["Magic V2.2", "Magic V2.2", "Magic V2.2"], "Ticker": ["AAA", "BBB", "AAA"],
                         "Harga": [99.0, 100.0, 99.0], "TP (%)": [1.5, 5.0, 1.5], "Hari": [1, 2, 1],
                         "Winrate (%)": [60.0, 50.0, 60.0], "Sinyal lalu": [12, 12, 12],
                         "Expectancy (%)": [0.4, 0.2, 0.4]}).drop(index=2)
    # AAA sinyal 2025-03-03 (idx0), entry 99 -> D+1 High 102 >= 100.485 => TP
    # BBB entry 100, TP 5%, 2 hari (High 102,103) => tidak TP; close hari ke-2 = 100 -> 0%
    rows = sl.make_rows(cand, idx[0], dt.datetime(2025, 3, 3, 14, 50))
    ev = sl.evaluate(rows, prices)
    assert list(ev["Hasil"]) == ["TP", "Tidak TP"], ev["Hasil"].tolist()
    assert abs(ev["Return (%)"].iloc[0] - 1.5) < 1e-9 and abs(ev["Return (%)"].iloc[1] - 0.0) < 1e-9
    assert abs(ev["Close final vs harga catat (%)"].iloc[0] - (100 / 99 - 1) * 100) < 1e-9
    # belum cukup hari -> Menunggu
    late = sl.make_rows(cand.iloc[:1], idx[5], dt.datetime(2025, 3, 10, 14, 50))
    assert sl.evaluate(late, prices)["Hasil"].iloc[0] == "Menunggu"
    # gabung: kunci sama ditimpa
    again = rows.copy(); again["Harga catat"] = 98.0
    m = sl.merge_logs(rows, again)
    assert len(m) == 2 and (m["Harga catat"].iloc[0] == 98.0 or m["Harga catat"].iloc[1] == 98.0)
    # simpan & muat
    with tempfile.TemporaryDirectory() as t:
        f = os.path.join(t, "x.csv"); sl.save_log(m, f)
        assert len(sl.load_log(f)) == 2
    sm = sl.summarize_log(ev)
    assert sm["Selesai"].iloc[0] == 2 and sm["Winrate aktual (%)"].iloc[0] == 50.0
    print("OK catatan sinyal: evaluasi, gabung, simpan, ringkasan")


if __name__ == "__main__":
    test_simulate_matches_naive()
    test_same_day_tp_sl_is_loss()
    test_engine_flow()
    test_presets_match_naive()
    test_syarat_tambahan_mempersempit()
    test_extras_and_engine_columns()
    test_presets_default_params_run()
    test_zero_volume_days_dipertahankan_di_MA()
    test_align_baris_libur_dibuang_dan_celah_diisi()
    test_winrate_hari_sama_per_saham()
    test_signal_log()
