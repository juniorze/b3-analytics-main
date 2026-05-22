from __future__ import annotations

import numpy as np
import pandas as pd

from b3analytics.config.assets import ACOES
from b3analytics.config.settings import INDICATOR_DEFAULTS, RISK_PCT_DEFAULT

SCORE_MAX: dict[str, int] = {
    "PULLBACK":   100,
    "ROMPIMENTO": 100,
    "REVERSAO":   100,
    "CRUZAMENTO": 100,
}


def apply_penalties(
    score: int, tipo: str, atr_v: float, price: float,
    rsi_v: float, vr: float, med_bull: bool, rr1: float,
) -> int:
    penalties = 0
    if tipo in ("PULLBACK", "CRUZAMENTO") and not med_bull:
        penalties += 25
    if vr < 0.5:
        penalties += 10
    if tipo == "PULLBACK" and rsi_v > 65:
        penalties += 15
    if tipo == "REVERSAO" and rsi_v > 45:
        penalties += 10
    if rr1 < 1.6:
        penalties += 10
    if price > 0 and atr_v / price > 0.05:
        penalties += 10
    return max(20, score - penalties)


def normalize_confidence(
    score_bruto: int, score_max: int,
    n_conditions_met: int, n_conditions_total: int,
) -> int:
    base  = (score_bruto / score_max) * 70
    bonus = (n_conditions_met / max(n_conditions_total, 1)) * 30
    return min(99, max(20, int(base + bonus)))


def calc_sizing(entry: float, stop: float, capital_op: float, risk_pct: float) -> dict | None:
    risco_unit = abs(entry - stop)
    if risco_unit <= 0 or entry <= 0:
        return None
    risco_max   = capital_op * risk_pct
    qtd_risco   = int(risco_max / risco_unit)
    qtd_capital = int(capital_op / entry)
    qtd         = max(1, min(qtd_risco, qtd_capital))
    alocado     = round(qtd * entry, 2)
    perda_max   = round(qtd * risco_unit, 2)
    pct_cap     = round(alocado / capital_op * 100, 1) if capital_op > 0 else 0
    return {
        "quantity":     qtd,
        "allocated":    alocado,
        "pct_capital":  pct_cap,
        "max_loss":     perda_max,
        "max_loss_pct": round(perda_max / capital_op * 100, 2) if capital_op > 0 else 0,
        "capital_op":   capital_op,
    }


def find_setup(
    df: pd.DataFrame,
    ticker: str,
    capital: float = 1_000.0,
    risk_pct: float = RISK_PCT_DEFAULT,
    params: dict | None = None,
) -> dict | None:
    p = {**INDICATOR_DEFAULTS, **(params or {})}

    if df is None or len(df) < 30:
        return None

    df = df.copy()
    rename = {}
    for c in df.columns:
        lc = c.lower()
        if lc == "open":                   rename[c] = "Open"
        elif lc == "high":                 rename[c] = "High"
        elif lc == "low":                  rename[c] = "Low"
        elif lc in ("close", "adj close"): rename[c] = "Close"
        elif lc == "volume":               rename[c] = "Volume"
    if rename:
        df = df.rename(columns=rename)

    if "Close" not in df.columns:
        return None

    close = df["Close"]
    high  = df["High"]   if "High"   in df.columns else close
    low   = df["Low"]    if "Low"    in df.columns else close
    vol   = df["Volume"] if "Volume" in df.columns else pd.Series(1.0, index=df.index)

    sma_short  = p.get("sma_short", 20)
    sma_medium = p.get("sma_medium", 50)
    sma_long   = p.get("sma_long", 200)
    ema_fast   = p.get("ema_fast", 9)
    ema_slow   = p.get("ema_slow", 21)
    rsi_os     = p.get("rsi_os", 30)
    rsi_ob     = p.get("rsi_ob", 70)

    sma20  = close.rolling(sma_short).mean()
    n50    = min(sma_medium, len(df) // 2)
    sma50  = close.rolling(n50).mean()
    n200   = min(sma_long, len(df))
    sma200 = close.rolling(n200).mean()
    ema9   = close.ewm(span=ema_fast, adjust=False).mean()
    ema21  = close.ewm(span=ema_slow, adjust=False).mean()
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()

    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))

    macd_line   = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = macd_line - macd_signal

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    vol_ma20  = vol.rolling(20).mean()
    vol_ratio = vol / vol_ma20.replace(0, np.nan)

    price_v  = float(close.iloc[-1])
    rsi_v    = float(rsi.iloc[-1])
    atr_v    = float(atr.iloc[-1])
    ema9_v   = float(ema9.iloc[-1])
    ema21_v  = float(ema21.iloc[-1])
    sma20_v  = float(sma20.iloc[-1])
    sma50_v  = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else price_v
    vr       = float(vol_ratio.iloc[-1]) if not pd.isna(vol_ratio.iloc[-1]) else 1.0
    mh_now   = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0.0
    mh_3ago  = float(macd_hist.iloc[-4]) if len(macd_hist) >= 4 and not pd.isna(macd_hist.iloc[-4]) else mh_now

    if pd.isna(price_v) or pd.isna(rsi_v) or pd.isna(atr_v) or atr_v == 0:
        return None

    short_bull = ema9_v > ema21_v
    med_bull   = price_v > sma50_v

    highs20 = high.iloc[-20:]
    lows20  = low.iloc[-20:]
    hh = float(highs20.iloc[-1]) > float(highs20.iloc[:-1].max())
    ll = float(lows20.iloc[-1])  < float(lows20.iloc[:-1].min())
    hl = float(lows20.iloc[-1])  > float(lows20.iloc[:-5].min()) if len(lows20) >= 5 else False

    bull_pts = int(short_bull) + int(med_bull) + int(hh or hl)
    bear_pts = int(not short_bull) + int(not med_bull) + int(ll)

    if bull_pts >= 2:   bias = "LONG"
    elif bear_pts >= 2: bias = "SHORT"
    else:               bias = "NEUTRO"

    best_setup = None
    best_score = 0

    if bias == "LONG":
        score, conds = 0, []

        if med_bull:
            score += 30; conds.append("Preço acima da SMA50")

        if rsi_os <= rsi_v <= 58:
            score += 20; conds.append(f"RSI em correção ({rsi_v:.1f})")
        elif rsi_v < rsi_os:
            score += 15; conds.append(f"RSI sobrevendido ({rsi_v:.1f})")

        if price_v < ema9_v:
            score += 15; conds.append("Preço abaixo da EMA9 (pullback)")

        if vr < 0.9:
            score += 10; conds.append(f"Volume seco ({vr:.1f}x)")

        if mh_now > mh_3ago:
            score += 10; conds.append("MACD em recuperação")

        dist_sma20 = abs(price_v - sma20_v) / sma20_v * 100 if sma20_v > 0 else 99
        if dist_sma20 < 3:
            score += 15; conds.append(f"Próximo à SMA20 ({dist_sma20:.1f}%)")

        if score >= 45:
            entry = round(ema9_v * 1.003, 2)
            stop  = round(price_v - atr_v * 1.5, 2)
            risco = entry - stop
            if risco > 0 and (risco / entry) <= 0.06:
                best_setup = {"type": "PULLBACK", "score": score, "entry": entry,
                              "stop": stop, "risco": risco, "rationale": " | ".join(conds),
                              "direction": "LONG",
                              "n_conditions_met": len(conds), "n_conditions_total": 6}
                best_score = score

    score_b, conds_b = 0, []

    atr_rec = float(atr.iloc[-5:].mean())    if len(atr) >= 5  else atr_v
    atr_old = float(atr.iloc[-20:-5].mean()) if len(atr) >= 20 else atr_v
    if atr_old > 0 and atr_rec / atr_old < 0.85:
        score_b += 25; conds_b.append("Compressão de volatilidade")

    range_5d = (float(high.iloc[-5:].max()) - float(low.iloc[-5:].min())) / price_v * 100
    if range_5d < 5:
        score_b += 25; conds_b.append(f"Range estreito 5d: {range_5d:.1f}%")

    if vr > 1.2:
        score_b += 25; conds_b.append(f"Volume acima da média ({vr:.1f}x)")

    if med_bull:
        score_b += 25; conds_b.append("Tendência de alta (médio)")

    if score_b >= 50 and score_b > best_score:
        resist = float(high.iloc[-30:].quantile(0.9))
        entry_b = round(resist * 1.003, 2)
        stop_b  = round(float(low.iloc[-5:].min()) * 0.994, 2)
        risco_b = entry_b - stop_b
        if risco_b > 0 and (risco_b / entry_b) <= 0.07:
            best_setup = {"type": "ROMPIMENTO", "score": score_b, "entry": entry_b,
                          "stop": stop_b, "risco": risco_b, "rationale": " | ".join(conds_b),
                          "direction": "LONG" if med_bull else "SHORT",
                          "n_conditions_met": len(conds_b), "n_conditions_total": 4}
            best_score = score_b

    score_c, conds_c = 0, []

    if rsi_v < rsi_os + 5:
        score_c += 30; conds_c.append(f"RSI sobrevendido ({rsi_v:.1f})")

    rsi_prev2 = float(rsi.iloc[-2]) if len(rsi) >= 2 and not pd.isna(rsi.iloc[-2]) else rsi_v
    rsi_prev3 = float(rsi.iloc[-3]) if len(rsi) >= 3 and not pd.isna(rsi.iloc[-3]) else rsi_v
    if rsi_v > rsi_prev2 and rsi_prev2 < rsi_prev3:
        score_c += 25; conds_c.append("RSI virando para cima")

    q10 = float(low.iloc[-20:].quantile(0.1))
    if price_v <= q10 * 1.03:
        score_c += 20; conds_c.append("Preço em zona de mínimos recente")

    close5ago = float(close.iloc[-6]) if len(close) >= 6 else price_v
    mh5ago    = float(macd_hist.iloc[-6]) if len(macd_hist) >= 6 and not pd.isna(macd_hist.iloc[-6]) else mh_now
    if price_v < close5ago and mh_now > mh5ago:
        score_c += 25; conds_c.append("Divergência bullish MACD/preço")

    if score_c >= 50 and score_c > best_score:
        entry_c = round(float(high.iloc[-3:].max()) * 1.002, 2)
        stop_c  = round(float(low.iloc[-5:].min()) * 0.994, 2)
        risco_c = entry_c - stop_c
        if risco_c > 0 and (risco_c / entry_c) <= 0.065:
            best_setup = {"type": "REVERSAO", "score": score_c, "entry": entry_c,
                          "stop": stop_c, "risco": risco_c, "rationale": " | ".join(conds_c),
                          "direction": "LONG",
                          "n_conditions_met": len(conds_c), "n_conditions_total": 4}
            best_score = score_c

    score_d, conds_d = 0, []

    ema9_s  = ema9.iloc[-4:]
    ema21_s = ema21.iloc[-4:]
    crossed_up = any(
        float(ema9_s.iloc[i]) > float(ema21_s.iloc[i]) and
        float(ema9_s.iloc[i-1]) <= float(ema21_s.iloc[i-1])
        for i in range(1, len(ema9_s))
        if not (pd.isna(ema9_s.iloc[i]) or pd.isna(ema21_s.iloc[i]))
    )
    if crossed_up:
        score_d += 40; conds_d.append("EMA9 cruzou EMA21 para cima")

    if med_bull:
        score_d += 25; conds_d.append("Preço acima da SMA50")

    if 45 <= rsi_v <= rsi_ob - 5:
        score_d += 20; conds_d.append(f"RSI saudável ({rsi_v:.1f})")

    if mh_now > 0:
        score_d += 15; conds_d.append("MACD histograma positivo")

    if score_d >= 55 and score_d > best_score:
        entry_d = round(price_v * 1.001, 2)
        stop_d  = round(float(ema21_v) * 0.99, 2)
        risco_d = entry_d - stop_d
        if risco_d > 0 and (risco_d / entry_d) <= 0.05:
            best_setup = {"type": "CRUZAMENTO", "score": score_d, "entry": entry_d,
                          "stop": stop_d, "risco": risco_d, "rationale": " | ".join(conds_d),
                          "direction": "LONG",
                          "n_conditions_met": len(conds_d), "n_conditions_total": 4}
            best_score = score_d

    if best_setup is None or best_score < 40:
        return None

    entry = best_setup["entry"]
    stop  = best_setup["stop"]
    risco = best_setup["risco"]

    alvo1 = round(entry + risco * 1.5, 2)
    alvo2 = round(entry + risco * 2.5, 2)
    alvo3 = round(entry + risco * 4.0, 2)
    rr1   = round((alvo1 - entry) / risco, 2)
    rr2   = round((alvo2 - entry) / risco, 2)
    rr3   = round((alvo3 - entry) / risco, 2)

    if rr1 < 1.4:
        return None

    sz = calc_sizing(entry, stop, capital, risk_pct)
    if sz is None:
        return None

    sma200_s     = sma200.dropna()
    sma200_v     = float(sma200_s.iloc[-1]) if not sma200_s.empty else price_v
    sma200_slope = 0.0
    if len(sma200_s) >= 20:
        s200_then = float(sma200_s.iloc[-20])
        if s200_then > 0:
            sma200_slope = round((sma200_v - s200_then) / s200_then * 100, 2)
    long_bull = price_v > sma200_v
    if len(sma200_s) >= 20:
        if long_bull and sma200_slope > 0.3:
            long_dir, long_str = "ALTA",    min(95, 60 + int(abs(sma200_slope) * 15))
            long_note = f"Preço acima da SMA{n200} com inclinação positiva (+{sma200_slope:.1f}%)"
        elif not long_bull and sma200_slope < -0.3:
            long_dir, long_str = "BAIXA",   min(95, 60 + int(abs(sma200_slope) * 15))
            long_note = f"Preço abaixo da SMA{n200} com inclinação negativa ({sma200_slope:.1f}%)"
        elif long_bull:
            long_dir, long_str = "ALTA",    50
            long_note = f"Preço acima da SMA{n200}, inclinação neutra ({sma200_slope:+.1f}%)"
        else:
            long_dir, long_str = "BAIXA",   50
            long_note = f"Preço abaixo da SMA{n200}"
    else:
        long_dir, long_str = "LATERAL", 30
        long_note = f"Período insuficiente para SMA{n200} ({len(df)} candles)"

    med_dir = "ALTA" if med_bull else "BAIXA"
    if med_bull and (hh or hl):
        med_str = 75
    elif med_bull:
        med_str = 55
    elif ll:
        med_str = 70
    else:
        med_str = 50

    sht_dir = "ALTA" if short_bull else "BAIXA"
    sht_str = 65 if (short_bull and rsi_v > 50) else 50

    score_pen  = apply_penalties(
        score=best_score, tipo=best_setup["type"],
        atr_v=atr_v, price=price_v, rsi_v=rsi_v,
        vr=vr, med_bull=med_bull, rr1=rr1,
    )
    confidence = normalize_confidence(
        score_bruto=score_pen,
        score_max=SCORE_MAX[best_setup["type"]],
        n_conditions_met=best_setup.get("n_conditions_met", 3),
        n_conditions_total=best_setup.get("n_conditions_total", 6),
    )

    return {
        "exists":    True,
        "ticker":    ticker,
        "name":      ACOES.get(ticker, ticker),
        "type":      best_setup["type"],
        "direction": best_setup["direction"],
        "confidence": confidence,
        "trend": {
            "bias":       bias,
            "bias_score": bull_pts * 20 - bear_pts * 20,
            "long": {
                "direction": long_dir, "strength": long_str,
                "sma_len": n200, "sma_val": round(sma200_v, 2),
                "slope_pct": sma200_slope, "note": long_note,
            },
            "medium": {"direction": med_dir, "strength": med_str},
            "short":  {"direction": sht_dir, "strength": sht_str},
            "summary": best_setup["rationale"],
        },
        "entry": {
            "price":    entry,
            "type":     "STOP" if best_setup["type"] in ("PULLBACK", "ROMPIMENTO") else "MERCADO",
            "rationale": best_setup["rationale"],
        },
        "stop": {
            "price":        stop,
            "distance_pct": round((entry - stop) / entry * 100, 2),
            "rationale":    "ATR × 1.5 abaixo da entrada",
        },
        "targets": [
            {"n": 1, "price": alvo1, "rr": rr1},
            {"n": 2, "price": alvo2, "rr": rr2},
            {"n": 3, "price": alvo3, "rr": rr3},
        ],
        "sizing": sz,
        "indicators": {
            "rsi":       round(rsi_v, 1),
            "ema9":      round(ema9_v, 2),
            "ema21":     round(ema21_v, 2),
            "sma50":     round(sma50_v, 2),
            "atr":       round(atr_v, 2),
            "vol_ratio": round(vr, 2),
        },
        "price_current": round(price_v, 2),
        "score_raw":     best_score,
    }
