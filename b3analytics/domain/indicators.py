from __future__ import annotations

import numpy as np
import pandas as pd

from b3analytics.config.settings import INDICATOR_DEFAULTS


def _cols(df: pd.DataFrame) -> tuple:
    close  = next((c for c in ["close",  "Close"]  if c in df.columns), None)
    high   = next((c for c in ["high",   "High"]   if c in df.columns), None)
    low    = next((c for c in ["low",    "Low"]    if c in df.columns), None)
    volume = next((c for c in ["volume", "Volume"] if c in df.columns), None)
    return close, high, low, volume


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(length).mean()
    loss  = (-delta.clip(upper=0)).rolling(length).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> tuple:
    up   = high.diff()
    down = -low.diff()
    dm_p = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    dm_n = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
    tr   = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr  = tr.rolling(length).mean()
    di_p = 100 * dm_p.rolling(length).mean() / atr.replace(0, np.nan)
    di_n = 100 * dm_n.rolling(length).mean() / atr.replace(0, np.nan)
    dx   = 100 * (di_p - di_n).abs() / (di_p + di_n).replace(0, np.nan)
    adx  = dx.rolling(length).mean()
    return adx, di_p, di_n


def _stoch(high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, d: int = 3) -> tuple:
    low_k  = low.rolling(k).min()
    high_k = high.rolling(k).max()
    stoch_k = 100 * (close - low_k) / (high_k - low_k).replace(0, np.nan)
    stoch_d = stoch_k.rolling(d).mean()
    return stoch_k, stoch_d


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical = (high + low + close) / 3
    cum_vol = volume.cumsum()
    cum_pv  = (typical * volume).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def add_all_indicators(df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    p = {**INDICATOR_DEFAULTS, **(params or {})}
    df = df.copy()
    close, high, low, volume = _cols(df)
    if close is None:
        return df

    c = df[close]
    h = df[high]   if high   else None
    l = df[low]    if low    else None
    v = df[volume] if volume else None

    df["SMA_20"]  = c.rolling(p.get("sma_short",  20)).mean()
    df["SMA_50"]  = c.rolling(p.get("sma_medium", 50)).mean()
    df["SMA_200"] = c.rolling(p.get("sma_long",  200)).mean()
    df["EMA_9"]   = c.ewm(span=p.get("ema_fast",   9), adjust=False).mean()
    df["EMA_21"]  = c.ewm(span=p.get("ema_slow",  21), adjust=False).mean()
    df["RSI_14"]  = _rsi(c, length=p.get("rsi_period", 14))

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    df["MACD"]        = macd_line
    df["MACD_signal"] = macd_signal
    df["MACD_hist"]   = macd_line - macd_signal

    bb_len = p.get("bb_period", 20)
    bb_std = p.get("bb_std", 2.0)
    bb_mid = c.rolling(bb_len).mean()
    bb_s   = c.rolling(bb_len).std()
    df["BB_mid"]   = bb_mid
    df["BB_upper"] = bb_mid + bb_std * bb_s
    df["BB_lower"] = bb_mid - bb_std * bb_s

    if h is not None and l is not None:
        df["ATR_14"] = _atr(h, l, c, length=p.get("atr_period", 14))
        adx, di_p, di_n = _adx(h, l, c, length=14)
        df["ADX_14"] = adx
        df["DMP_14"] = di_p
        df["DMN_14"] = di_n
        stoch_k, stoch_d = _stoch(h, l, c, k=p.get("stoch_k", 14), d=p.get("stoch_d", 3))
        df["Stoch_K"] = stoch_k
        df["Stoch_D"] = stoch_d

    if v is not None:
        df["OBV"] = _obv(c, v)
        if h is not None and l is not None:
            df["VWAP"] = _vwap(h, l, c, v)

    return df


def calcular_retorno_normalizado(df: pd.DataFrame) -> pd.Series:
    close, *_ = _cols(df)
    if close is None:
        return pd.Series(dtype=float)
    prices = df[close].dropna()
    if prices.empty:
        return pd.Series(dtype=float)
    return ((prices / prices.iloc[0]) - 1) * 100


def calcular_correlacao(dfs: dict) -> pd.DataFrame:
    series = {}
    for ticker, df in dfs.items():
        close, *_ = _cols(df)
        if close and not df.empty:
            series[ticker] = df[close]
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).dropna().corr()
