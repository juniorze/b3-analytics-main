from __future__ import annotations

import pandas as pd

from b3analytics.domain.indicators import add_all_indicators


def _v(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return None
    s = df[col].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _v2(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return None
    s = df[col].dropna()
    return float(s.iloc[-2]) if len(s) >= 2 else None


def _close_col(df: pd.DataFrame) -> str | None:
    return next((c for c in ["close", "Close"] if c in df.columns), None)


def _high_col(df: pd.DataFrame) -> str | None:
    return next((c for c in ["high", "High"] if c in df.columns), None)


def _low_col(df: pd.DataFrame) -> str | None:
    return next((c for c in ["low", "Low"] if c in df.columns), None)


def analyze_trend(df: pd.DataFrame) -> dict:
    df = add_all_indicators(df.copy())
    n  = len(df)

    cc = _close_col(df)
    hc = _high_col(df)
    lc = _low_col(df)
    if cc is None:
        return _neutral()

    price = _v(df, cc)
    if price is None:
        return _neutral()

    sma200     = df["SMA_200"].dropna()
    slope_pct  = 0.0

    if len(sma200) >= 20:
        sma_val   = round(float(sma200.iloc[-1]), 2)
        s200_then = float(sma200.iloc[-20])
        slope_pct = round((sma_val - s200_then) / s200_then * 100, 2) if s200_then > 0 else 0.0
        above     = price > sma_val

        if above and slope_pct > 0.3:
            long_dir, long_str = "ALTA", min(95, 60 + int(abs(slope_pct) * 15))
            long_note = f"Preço acima da SMA200 com inclinação positiva (+{slope_pct:.1f}%)"
        elif not above and slope_pct < -0.3:
            long_dir, long_str = "BAIXA", min(95, 60 + int(abs(slope_pct) * 15))
            long_note = f"Preço abaixo da SMA200 com inclinação negativa ({slope_pct:.1f}%)"
        elif above:
            long_dir, long_str = "ALTA", 50
            long_note = f"Preço acima da SMA200, inclinação neutra ({slope_pct:+.1f}%)"
        else:
            long_dir, long_str = "BAIXA", 50
            long_note = "Preço abaixo da SMA200"
    else:
        sma_val   = round(float(sma200.iloc[-1]), 2) if not sma200.empty else round(price, 2)
        long_dir, long_str = "LATERAL", 30
        long_note = f"Dados insuficientes para SMA200 ({n} candles disponíveis)"

    sma50     = df["SMA_50"].dropna()
    sma50_val = round(float(sma50.iloc[-1]), 2) if not sma50.empty else round(price, 2)

    if len(sma50) >= 5:
        above50       = price > sma50_val
        med_dir, med_str = ("ALTA" if above50 else "BAIXA"), 50

        if hc and lc and len(df) >= 20:
            rec   = df.tail(20)
            h_arr = rec[hc].values
            l_arr = rec[lc].values
            mid   = len(h_arr) // 2
            hh = h_arr[-5:].max() > h_arr[mid:mid + 5].max()
            hl = l_arr[-5:].min() > l_arr[mid:mid + 5].min()
            lh = h_arr[-5:].max() < h_arr[mid:mid + 5].max()
            ll = l_arr[-5:].min() < l_arr[mid:mid + 5].min()

            if above50 and hh and hl:
                med_dir, med_str = "ALTA", 80
            elif above50 and (hh or hl):
                med_dir, med_str = "ALTA", 62
            elif not above50 and lh and ll:
                med_dir, med_str = "BAIXA", 80
            elif not above50 and (lh or ll):
                med_dir, med_str = "BAIXA", 62
            else:
                med_dir, med_str = "LATERAL", 40
    else:
        med_dir, med_str = "LATERAL", 30

    ema9_v  = _v(df, "EMA_9")
    ema21_v = _v(df, "EMA_21")
    adx     = _v(df, "ADX_14")
    dmp     = _v(df, "DMP_14")
    dmn     = _v(df, "DMN_14")

    if ema9_v is not None and ema21_v is not None:
        bull_ema   = ema9_v > ema21_v
        adx_strong = adx is not None and adx > 20
        bull_di    = dmp is not None and dmn is not None and dmp > dmn

        if bull_ema and adx_strong and bull_di:
            short_dir, short_str = "ALTA", min(95, 60 + int(adx))
        elif not bull_ema and adx_strong and (dmp is None or dmn > dmp):
            short_dir, short_str = "BAIXA", min(95, 60 + int(adx))
        elif bull_ema:
            short_dir, short_str = "ALTA", 52
        else:
            short_dir, short_str = "BAIXA", 52
    else:
        short_dir, short_str = "LATERAL", 30
        ema9_v = ema21_v = None

    def _score(direction: str, strength: int) -> float:
        sign = 1 if direction == "ALTA" else (-1 if direction == "BAIXA" else 0)
        return sign * strength

    bias_score = int(
        _score(long_dir,  long_str)  * 0.30
        + _score(med_dir,  med_str)  * 0.40
        + _score(short_dir, short_str) * 0.30
    )

    bias = "COMPRADOR" if bias_score > 20 else "VENDEDOR" if bias_score < -20 else "NEUTRO"

    _a = {"ALTA": "↑", "BAIXA": "↓", "LATERAL": "→"}
    summary = (
        f"Longo: {_a.get(long_dir,'—')} {long_dir} | "
        f"Médio: {_a.get(med_dir,'—')} {med_dir} | "
        f"Curto: {_a.get(short_dir,'—')} {short_dir}"
    )

    return {
        "long": {
            "direction": long_dir, "strength": long_str,
            "sma_len": 200, "sma_val": sma_val,
            "slope_pct": slope_pct, "note": long_note,
        },
        "medium": {
            "direction": med_dir, "strength": med_str,
            "sma50": sma50_val,
        },
        "short": {
            "direction": short_dir, "strength": short_str,
            "ema9":  round(ema9_v,  2) if ema9_v  is not None else None,
            "ema21": round(ema21_v, 2) if ema21_v is not None else None,
        },
        "bias":        bias,
        "bias_score":  bias_score,
        "summary":     summary,
    }


def _neutral() -> dict:
    return {
        "long": {
            "direction": "LATERAL", "strength": 30,
            "sma_len": 200, "sma_val": None, "slope_pct": 0.0,
            "note": "Dados insuficientes",
        },
        "medium": {"direction": "LATERAL", "strength": 30, "sma50": None},
        "short":  {"direction": "LATERAL", "strength": 30, "ema9": None, "ema21": None},
        "bias":       "NEUTRO",
        "bias_score": 0,
        "summary":    "Dados insuficientes",
    }
