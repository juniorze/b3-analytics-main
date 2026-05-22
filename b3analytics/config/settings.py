from __future__ import annotations

CACHE_TTL_SECONDS: int = 300
DATA_PROVIDER: str = "yfinance"
DATA_DELAY_MINUTES: int = 15

PERIODOS: dict[str, str] = {
    "15 dias": "15d",
    "1 mês":   "1mo",
    "2 meses": "2mo",
    "3 meses": "3mo",
    "6 meses": "6mo",
    "1 ano":   "1y",
    "2 anos":  "2y",
}

INDICATOR_DEFAULTS: dict[str, int | float] = {
    "sma_short":   20,
    "sma_medium":  50,
    "sma_long":    200,
    "ema_fast":    9,
    "ema_slow":    21,
    "rsi_period":  14,
    "rsi_ob":      70,
    "rsi_os":      30,
    "macd_fast":   12,
    "macd_slow":   26,
    "macd_signal": 9,
    "bb_period":   20,
    "bb_std":      2.0,
    "atr_period":  14,
    "stoch_k":     14,
    "stoch_d":     3,
}

CAPITAL_DEFAULT: float = 1_000.0
RISK_PCT_DEFAULT: float = 0.02
COMMISSION_PCT: float = 0.001

FUNDAMENTALS_SANITY: dict[str, tuple[float, float]] = {
    "dy":              (0.0,   50.0),
    "pl":              (0.0,  500.0),
    "pvp":             (0.0,   50.0),
    "ev_ebitda":       (0.0,  200.0),
    "roe":           (-100.0, 200.0),
    "margem_liquida": (-100.0, 100.0),
    "beta":            (-5.0,   5.0),
}

PREGAO_ABERTURA: tuple[int, int] = (10, 0)
PREGAO_FECHAMENTO: tuple[int, int] = (17, 30)
