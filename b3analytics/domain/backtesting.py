from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

from b3analytics.config.settings import INDICATOR_DEFAULTS

logger = logging.getLogger(__name__)


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        lc = col.lower()
        if lc == "open":    col_map[col] = "Open"
        elif lc == "high":  col_map[col] = "High"
        elif lc == "low":   col_map[col] = "Low"
        elif lc in ("close", "adj close"): col_map[col] = "Close"
        elif lc == "volume": col_map[col] = "Volume"
    df = df.rename(columns=col_map)
    needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[needed].dropna()


def _sma(x, n):
    return pd.Series(x).rolling(n).mean().values

def _ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values

def _rsi(x, n=14):
    s = pd.Series(x, dtype=float)
    delta = s.diff()
    gain  = delta.clip(lower=0).rolling(n).mean()
    loss  = (-delta.clip(upper=0)).rolling(n).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    return rsi.fillna(50).values

def _atr(high, low, close, n=14):
    h = pd.Series(high, dtype=float)
    l = pd.Series(low,  dtype=float)
    c = pd.Series(close, dtype=float)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().fillna(0).values

def _macd_hist(x, fast=12, slow=26, signal=9):
    s     = pd.Series(x, dtype=float)
    ema_f = s.ewm(span=fast, adjust=False).mean()
    ema_s = s.ewm(span=slow, adjust=False).mean()
    line  = ema_f - ema_s
    sig   = line.ewm(span=signal, adjust=False).mean()
    return (line - sig).fillna(0).values


class PullbackStrategy(Strategy):
    _params: dict = {}

    def init(self):
        p = type(self)._params or INDICATOR_DEFAULTS
        sma_n       = int(p.get("sma_medium", 50))
        self._rsi_lo = int(p.get("rsi_os", 35))
        self._rsi_hi = self._rsi_lo + 20
        self.sma = self.I(_sma, self.data.Close, sma_n)
        self.rsi = self.I(_rsi, self.data.Close)
        self.atr = self.I(_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        price = self.data.Close[-1]
        s     = self.sma[-1]
        rsi   = self.rsi[-1]
        atr   = self.atr[-1]
        if np.isnan(s) or np.isnan(rsi) or atr == 0:
            return
        in_zone = s <= price <= s * 1.08
        rsi_ok  = self._rsi_lo <= rsi <= self._rsi_hi
        if not self.position and in_zone and rsi_ok:
            self.buy(sl=price - atr * 1.5, tp=price + atr * 2.5)
        elif self.position.is_long and rsi > 75:
            self.position.close()


class RompimentoStrategy(Strategy):
    lookback = 20
    vol_mult = 1.4
    _params: dict = {}

    def init(self):
        self.atr = self.I(_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        if len(self.data.Close) < self.lookback + 2:
            return
        price       = self.data.Close[-1]
        p_prev      = self.data.Close[-2]
        recent_high = max(self.data.High[-(self.lookback + 1):-1])
        avg_vol     = np.mean(self.data.Volume[-(self.lookback + 1):-1])
        atr         = self.atr[-1]
        breakout    = p_prev <= recent_high < price
        vol_confirm = self.data.Volume[-1] > avg_vol * self.vol_mult
        if not self.position and breakout and vol_confirm and atr > 0:
            self.buy(sl=price - atr * 2.0, tp=price + atr * 3.0)


class ReversaoStrategy(Strategy):
    _params: dict = {}

    def init(self):
        p = type(self)._params or INDICATOR_DEFAULTS
        sma_n              = int(p.get("sma_medium", 50))
        self._rsi_threshold = int(p.get("rsi_os", 33))
        self.rsi = self.I(_rsi, self.data.Close)
        self.sma = self.I(_sma, self.data.Close, sma_n)
        self.atr = self.I(_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        price = self.data.Close[-1]
        rsi   = self.rsi[-1]
        s     = self.sma[-1]
        atr   = self.atr[-1]
        if np.isnan(rsi) or np.isnan(s) or atr == 0:
            return
        near_support = price < s * 1.15
        oversold     = rsi < self._rsi_threshold
        rsi_rising   = len(self.rsi) >= 2 and self.rsi[-1] > self.rsi[-2]
        if not self.position and near_support and oversold and rsi_rising:
            self.buy(sl=price - atr * 1.5, tp=price + atr * 3.0)
        elif self.position.is_long and rsi > 65:
            self.position.close()


class CruzamentoStrategy(Strategy):
    _params: dict = {}

    def init(self):
        p = type(self)._params or INDICATOR_DEFAULTS
        ema_fast   = int(p.get("ema_fast",    9))
        ema_slow   = int(p.get("ema_slow",   21))
        sma_n      = int(p.get("sma_medium", 50))
        macd_fast  = int(p.get("macd_fast",  12))
        macd_slow  = int(p.get("macd_slow",  26))
        macd_sig   = int(p.get("macd_signal", 9))
        self.ema_f = self.I(_ema, self.data.Close, ema_fast)
        self.ema_s = self.I(_ema, self.data.Close, ema_slow)
        self.sma   = self.I(_sma, self.data.Close, sma_n)
        self.macdh = self.I(_macd_hist, self.data.Close, macd_fast, macd_slow, macd_sig)
        self.atr   = self.I(_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        price = self.data.Close[-1]
        s     = self.sma[-1]
        atr   = self.atr[-1]
        if np.isnan(s) or atr == 0:
            return
        if crossover(self.ema_f, self.ema_s) and price > s and self.macdh[-1] > 0:
            if not self.position:
                self.buy(sl=price - atr * 1.5, tp=price + atr * 2.5)
        elif crossover(self.ema_s, self.ema_f):
            if self.position.is_long:
                self.position.close()


STRATEGIES: dict[str, type] = {
    "Pullback (SMA50)":        PullbackStrategy,
    "Rompimento (Volume)":     RompimentoStrategy,
    "Reversão em Suporte":     ReversaoStrategy,
    "Cruzamento EMA9×EMA21":   CruzamentoStrategy,
}


def run_backtest(
    df: pd.DataFrame,
    strategy_class,
    cash: float = 10_000.0,
    commission: float = 0.001,
    params: dict | None = None,
) -> dict:
    p = params or dict(INDICATOR_DEFAULTS)
    strategy_class._params = p

    df_bt = _prep(df)
    if df_bt.empty or len(df_bt) < 50:
        return {}
    try:
        bt    = Backtest(df_bt, strategy_class, cash=cash, commission=commission, exclusive_orders=True)
        stats = bt.run()

        trades  = stats["_trades"]
        equity  = stats["_equity_curve"]["Equity"]
        bah     = (df_bt["Close"] / df_bt["Close"].iloc[0]) * cash

        orig_close = df["Close"] if "Close" in df.columns else df["close"]
        bh_pct_full = round(
            (float(orig_close.dropna().iloc[-1]) / float(orig_close.dropna().iloc[0]) - 1) * 100,
            3
        )

        def _safe(v, default=None):
            try:
                fv = float(v)
                return round(fv, 3) if not np.isnan(fv) and not np.isinf(fv) else default
            except (TypeError, ValueError):
                return default

        n = int(stats["# Trades"])
        return {
            "return_pct":    _safe(stats["Return [%]"], 0.0),
            "buyhold_pct":   bh_pct_full,
            "sharpe":        _safe(stats["Sharpe Ratio"], 0.0),
            "max_drawdown":  _safe(stats["Max. Drawdown [%]"], 0.0),
            "win_rate":      _safe(stats["Win Rate [%]"], 0.0),
            "total_trades":  n,
            "profit_factor": _safe(stats.get("Profit Factor"), None),
            "equity_curve":  equity,
            "bah_curve":     bah,
            "trades":        trades,
        }
    except Exception as e:
        logger.warning("Falha ao rodar backtest: strategy=%s linhas=%s", strategy_class.__name__, len(df_bt))
        return {"error": str(e)}
