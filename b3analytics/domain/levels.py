import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


def _cols(df: pd.DataFrame) -> tuple:
    close  = next((c for c in ["close",  "Close"]  if c in df.columns), None)
    high   = next((c for c in ["high",   "High"]   if c in df.columns), None)
    low    = next((c for c in ["low",    "Low"]    if c in df.columns), None)
    return close, high, low


def _find_pivots(values: np.ndarray, order: int = 5, find_max: bool = True):
    if len(values) < 2 * order + 1:
        return np.array([]), np.array([])
    comparator = np.greater_equal if find_max else np.less_equal
    idx = argrelextrema(values, comparator, order=order)[0]
    return idx, values[idx]


def _cluster_levels(price_idx_pairs: list, threshold_pct: float = 0.008) -> list[list]:
    if not price_idx_pairs:
        return []
    sorted_items = sorted(price_idx_pairs, key=lambda x: x[0])
    clusters: list[list] = []
    current = [sorted_items[0]]
    for item in sorted_items[1:]:
        if current[0][0] == 0 or abs(item[0] - current[0][0]) / current[0][0] <= threshold_pct:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)
    return clusters


def _score_cluster(cluster: list, df_len: int) -> dict:
    prices   = [x[0] for x in cluster]
    indices  = [x[1] for x in cluster]
    centroid = float(np.mean(prices))
    touches  = len(prices)
    recency  = float(np.mean([i / max(df_len - 1, 1) for i in indices]))
    strength = int(touches * (1 + recency) * 10)
    return {"price": round(centroid, 2), "touches": touches, "strength": strength}


def find_key_levels(df: pd.DataFrame, lookback: int = 90) -> dict:
    df_look   = df.tail(lookback).reset_index(drop=True)
    df_len    = len(df_look)
    close, high, low = _cols(df_look)

    current_price = float(df_look[close].iloc[-1]) if close else 0.0

    if current_price == 0.0:
        return _empty_levels(current_price)

    if high is None or low is None or df_len < 11:
        return _empty_levels(current_price)

    h_arr = df_look[high].values
    l_arr = df_look[low].values

    h_idx, h_prices = _find_pivots(h_arr, order=5, find_max=True)
    l_idx, l_prices = _find_pivots(l_arr, order=5, find_max=False)

    h_pairs = list(zip(h_prices.tolist(), h_idx.tolist()))
    l_pairs = list(zip(l_prices.tolist(), l_idx.tolist()))

    h_clusters = _cluster_levels(h_pairs)
    l_clusters = _cluster_levels(l_pairs)

    resistances = []
    for c in h_clusters:
        lvl = _score_cluster(c, df_len)
        if lvl["price"] > current_price * 1.003:
            resistances.append(lvl)

    supports = []
    for c in l_clusters:
        lvl = _score_cluster(c, df_len)
        if lvl["price"] < current_price * 0.997:
            supports.append(lvl)

    resistances.sort(key=lambda x: x["price"])
    supports.sort(key=lambda x: -x["price"])
    resistances = resistances[:4]
    supports    = supports[:4]

    nearest_res = resistances[0] if resistances else None
    nearest_sup = supports[0]    if supports    else None

    dist_res = ((nearest_res["price"] - current_price) / current_price * 100) if nearest_res else 999.0
    dist_sup = ((current_price - nearest_sup["price"]) / current_price * 100) if nearest_sup else 999.0

    return {
        "supports":            supports,
        "resistances":         resistances,
        "nearest_support":     nearest_sup,
        "nearest_resistance":  nearest_res,
        "dist_support_pct":    round(dist_sup, 2),
        "dist_resistance_pct": round(dist_res, 2),
        "current_price":       current_price,
    }


def pivot_points_classico(df: pd.DataFrame) -> dict:
    close, high, low = _cols(df)
    if not all([close, high, low]) or len(df) < 2:
        return {}
    last = df.iloc[-2]
    H = float(last[high])
    L = float(last[low])
    C = float(last[close])
    PP = (H + L + C) / 3
    return {
        "PP": round(PP, 2),
        "R1": round(2 * PP - L, 2),
        "R2": round(PP + (H - L), 2),
        "R3": round(H + 2 * (PP - L), 2),
        "S1": round(2 * PP - H, 2),
        "S2": round(PP - (H - L), 2),
        "S3": round(L - 2 * (H - PP), 2),
    }


def _empty_levels(current_price: float) -> dict:
    return {
        "supports":            [],
        "resistances":         [],
        "nearest_support":     None,
        "nearest_resistance":  None,
        "dist_support_pct":    999.0,
        "dist_resistance_pct": 999.0,
        "current_price":       current_price,
    }
