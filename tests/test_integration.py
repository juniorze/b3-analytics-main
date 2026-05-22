"""Testes de integração — chama yfinance e APIs públicas."""
import math
import time

import pandas as pd
import pytest

from b3analytics.domain.backtesting import (
    CruzamentoStrategy,
    PullbackStrategy,
    ReversaoStrategy,
    RompimentoStrategy,
    run_backtest,
)
from b3analytics.domain.engine import find_setup
from b3analytics.domain.trend import analyze_trend
from b3analytics.infrastructure.fetcher import (
    _fetch_one,
    fetch_all_parallel,
    get_fundamentals,
)
from b3analytics.infrastructure.macro import get_macro_context


class TestFetcher:
    @pytest.mark.parametrize("ticker,periodo", [
        ("PETR4.SA", "3mo"), ("VALE3.SA", "1mo"), ("^BVSP", "3mo"),
    ])
    def test_fetch_one(self, ticker, periodo):
        _, df = _fetch_one(ticker, periodo)
        assert df is not None, f"{ticker} retornou None"
        assert len(df) >= 15,  f"{ticker} tem só {len(df)} candles"
        assert all(c in df.columns for c in ["Open", "High", "Low", "Close", "Volume"])
        assert (df["Close"] > 0).all()
        assert (df["High"] >= df["Low"]).all()
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.is_monotonic_increasing
        assert df[["Open", "High", "Low", "Close"]].iloc[-5:].isna().sum().sum() == 0

    def test_fetch_parallel_speed(self):
        tickers = ["PETR4.SA", "VALE3.SA", "BBAS3.SA", "ITUB4.SA", "WEGE3.SA"]
        t0  = time.time()
        dfs = fetch_all_parallel(tickers, "3mo")
        elapsed = time.time() - t0
        assert elapsed < 25, f"Fetch demorou {elapsed:.1f}s"
        assert len(dfs) >= 4, f"Retornou só {len(dfs)}"

    @pytest.mark.parametrize("ticker", ["PETR4.SA", "WEGE3.SA", "BBAS3.SA"])
    def test_fundamentals_sanidade(self, ticker):
        f   = get_fundamentals(ticker)
        dy  = f.get("dy")
        pl  = f.get("pl")
        mc  = f.get("market_cap_raw")
        assert isinstance(f, dict)
        if dy  is not None: assert dy  < 50,  f"DY absurdo: {dy}"
        if pl  is not None: assert pl  < 500, f"P/L absurdo: {pl}"
        if mc  is not None: assert mc  > 5e8, f"MCap baixo: {mc}"
        beta = f.get("beta")
        if beta is not None: assert abs(beta) < 10, f"Beta absurdo: {beta}"


class TestMacro:
    def test_get_macro_context(self):
        t0    = time.time()
        macro = get_macro_context()
        assert time.time() - t0 < 20, "Macro demorou > 20s"
        assert isinstance(macro, dict)
        for campo in ["selic_pct", "ipca_12m_pct", "usd_brl", "commodities", "data_coleta"]:
            assert campo in macro, f"Campo '{campo}' ausente"
        usd = macro.get("usd_brl")
        if usd: assert 3 < usd < 15
        selic = macro.get("selic_pct")
        if selic: assert 2 < selic < 30
        comods = macro.get("commodities", {})
        for c in ["petroleo_brent", "vix", "sp500"]:
            assert c in comods


class TestEngine:
    def test_analyze_trend(self):
        _, df = _fetch_one("PETR4.SA", "1y")
        assert df is not None
        t = analyze_trend(df)
        assert isinstance(t, dict)
        for k in ["long", "medium", "short", "bias"]:
            assert k in t
        for horizonte in ["long", "medium", "short"]:
            assert t[horizonte]["direction"] in ("ALTA", "BAIXA", "LATERAL", "N/D")
            assert 0 <= t[horizonte]["strength"] <= 100
        assert t["bias"] in ("COMPRADOR", "VENDEDOR", "NEUTRO")

    def test_find_setup_scan(self):
        tickers = [
            "PETR4.SA", "VALE3.SA", "BBAS3.SA", "ITUB4.SA", "WEGE3.SA",
            "ELET3.SA", "CMIG4.SA", "SUZB3.SA", "PRIO3.SA", "EGIE3.SA",
            "BBDC4.SA", "TIMS3.SA", "VBBR3.SA", "RADL3.SA", "RENT3.SA",
        ]
        dfs    = fetch_all_parallel(tickers, "3mo")
        setups = []
        CAMPOS = ["exists", "ticker", "type", "direction", "confidence",
                  "entry", "stop", "targets", "sizing", "indicators",
                  "price_current", "trend"]

        for ticker, df in dfs.items():
            s = find_setup(df, ticker, capital=1000, risk_pct=0.02)
            if s is None:
                continue
            setups.append(ticker)
            for campo in CAMPOS:
                assert campo in s, f"{ticker}: campo '{campo}' ausente"
            e  = s["entry"]["price"]
            sp = s["stop"]["price"]
            assert e > sp, f"{ticker}: entrada({e}) ≤ stop({sp})"
            rrs = [t["rr"] for t in s["targets"]]
            assert len(rrs) == 3,  f"{ticker}: esperado 3 alvos"
            assert rrs[0] < rrs[1] < rrs[2]
            assert rrs[0] >= 1.4,  f"{ticker}: R/R A1={rrs[0]}"
            assert 20 <= s["confidence"] <= 99
            assert 0.5 <= s["stop"]["distance_pct"] <= 7

        assert len(setups) >= 3, f"Scan encontrou só {len(setups)} setups"

    def test_find_setup_custom_params(self):
        _, df = _fetch_one("PETR4.SA", "3mo")
        assert df is not None
        # deve retornar sem lançar exceção
        find_setup(df, "PETR4.SA", params={"rsi_period": 21, "ema_fast": 12})


class TestBacktesting:
    @pytest.fixture(scope="class")
    def df_bt(self):
        _, df = _fetch_one("PETR4.SA", "2y")
        assert df is not None
        return df

    @pytest.mark.parametrize("strat,nome", [
        (PullbackStrategy,   "Pullback"),
        (RompimentoStrategy, "Rompimento"),
        (ReversaoStrategy,   "Reversão"),
        (CruzamentoStrategy, "Cruzamento"),
    ])
    def test_backtest(self, df_bt, strat, nome):
        bh = (df_bt["Close"].iloc[-1] / df_bt["Close"].iloc[0] - 1) * 100
        bt = run_backtest(df_bt, strat, cash=10_000, commission=0.001)

        for campo in ["return_pct", "buyhold_pct", "sharpe", "max_drawdown",
                      "win_rate", "total_trades", "equity_curve", "trades"]:
            assert campo in bt, f"{nome}: '{campo}' ausente"

        ec = bt["equity_curve"]
        assert isinstance(ec.index, pd.DatetimeIndex), f"{nome}: equity sem DatetimeIndex"
        assert abs(ec.iloc[0] - 10_000) < 1_000
        assert bt["max_drawdown"] <= 0
        assert 0 <= bt["win_rate"] <= 100
        assert not math.isnan(bt["sharpe"])
        assert not math.isinf(bt["sharpe"])
        assert abs(bt["buyhold_pct"] - bh) < 2
