def is_signal(df, i):

    today = df.iloc[i]
    prev = df.iloc[i-1]

    close = today["Close"]
    high = today["High"]
    volume = today["Volume"]

    prev_close = prev["Close"]
    prev_high = prev["High"]
    prev_volume = prev["Volume"]

    sma5 = today["SMA5"]
    sma20 = today["SMA20"]

    value = today["Value"]
    avg_value = today["AvgValue20"]

    value_ratio = today["ValueRatio"]

    avg_volume = today["VOLMA20"]

    change_pct = (close - prev_close) / prev_close

    ara = get_ara_limit(prev_close)

    # =========================
    # FILTER HARGA
    # =========================

    if close > 6500 or close < 50:
        return False

    # =========================
    # HINDARI SAHAM SUDAH TERLALU NAIK
    # =========================

    if ara == 0.25 and change_pct >= 0.24:
        return False

    if ara == 0.35 and change_pct >= 0.33:
        return False

    # hindari candle terlalu tinggi
    if change_pct > 0.06:
        return False

    # minimal ada momentum
    if change_pct < 0.01:
        return False

    # =========================
    # LIQUIDITY FILTER
    # =========================

    if not (
        avg_value > 10_000_000_000 and
        avg_volume > 1_000_000
    ):
        return False

    # =========================
    # MAIN SIGNAL
    # =========================

    if not (

        # close lebih tinggi dari kemarin
        close > prev_close and

        # trend pendek bullish
        close > sma5 and
        sma5 > sma20 and

        # volume expansion
        volume > avg_volume * 1.5 and

        # transaksi hari ini besar
        value > 15_000_000_000 and

        # relative volume/value
        value_ratio > 1.5 and

        # breakout high kemarin
        close > prev_high and

        # close dekat high
        close >= high * 0.98

    ):
        return False

    return True
