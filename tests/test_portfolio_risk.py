from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from b3analytics.domain.portfolio import PortfolioSnapshot, Position
from b3analytics.domain.portfolio_risk import PortfolioRiskLimits, calculate_portfolio_risk


def test_risco_carteira_vazia_nao_quebra():
    risk = calculate_portfolio_risk(PortfolioSnapshot(positions=[], realized_pnl=[]), {})

    assert risk.total_priced_value == 0
    assert risk.asset_concentrations == []
    assert risk.group_concentrations == []
    assert risk.portfolio_volatility_pct is None
    assert risk.max_drawdown_pct is None
    assert risk.correlation.empty


def test_concentracao_acima_do_limite_gera_alerta():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("PETR4.SA", quantity=90, average_price=10, total_cost=900),
            Position("VALE3.SA", quantity=10, average_price=10, total_cost=100),
        ],
        realized_pnl=[],
    )

    risk = calculate_portfolio_risk(
        snapshot,
        {"PETR4.SA": 10, "VALE3.SA": 10},
        limits=PortfolioRiskLimits(max_asset_pct=60),
    )

    assert risk.asset_concentrations[0].ticker == "PETR4.SA"
    assert risk.asset_concentrations[0].weight_pct == pytest.approx(90)
    assert risk.asset_concentrations[0].status == "acima do limite"


def test_ativos_dentro_do_limite_nao_sao_alerta():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("PETR4.SA", quantity=50, average_price=10, total_cost=500),
            Position("VALE3.SA", quantity=50, average_price=10, total_cost=500),
        ],
        realized_pnl=[],
    )

    risk = calculate_portfolio_risk(
        snapshot,
        {"PETR4.SA": 10, "VALE3.SA": 10},
        limits=PortfolioRiskLimits(max_asset_pct=60),
    )

    assert {item.status for item in risk.asset_concentrations} == {"dentro do limite"}


def test_concentracao_por_grupo_acima_do_limite():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("ITUB4.SA", quantity=50, average_price=10, total_cost=500),
            Position("BBDC4.SA", quantity=40, average_price=10, total_cost=400),
            Position("VALE3.SA", quantity=10, average_price=10, total_cost=100),
        ],
        realized_pnl=[],
    )

    risk = calculate_portfolio_risk(
        snapshot,
        {"ITUB4.SA": 10, "BBDC4.SA": 10, "VALE3.SA": 10},
        groups={"Financeiro": ["ITUB4.SA", "BBDC4.SA"], "Mineracao": ["VALE3.SA"]},
        limits=PortfolioRiskLimits(max_group_pct=70),
    )

    assert risk.group_concentrations[0].group == "Financeiro"
    assert risk.group_concentrations[0].weight_pct == pytest.approx(90)
    assert risk.group_concentrations[0].status == "acima do limite"


def test_ativo_sem_preco_fica_fora_do_risco_de_mercado():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("PETR4.SA", quantity=10, average_price=10, total_cost=100),
            Position("VALE3.SA", quantity=10, average_price=10, total_cost=100),
        ],
        realized_pnl=[],
    )

    risk = calculate_portfolio_risk(snapshot, {"PETR4.SA": 10})

    assert risk.missing_price_tickers == ["VALE3.SA"]
    assert risk.total_priced_value == pytest.approx(100)
    assert [item.ticker for item in risk.asset_concentrations] == ["PETR4.SA"]


def test_historico_insuficiente_nao_calcula_volatilidade():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=10, average_price=10, total_cost=100)],
        realized_pnl=[],
    )
    histories = {"PETR4.SA": _history([10])}

    risk = calculate_portfolio_risk(snapshot, {"PETR4.SA": 10}, histories=histories)

    assert risk.insufficient_history_tickers == ["PETR4.SA"]
    assert risk.volatility_by_ticker_pct == {}
    assert risk.portfolio_volatility_pct is None


def test_volatilidade_valida():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=10, average_price=10, total_cost=100)],
        realized_pnl=[],
    )
    histories = {"PETR4.SA": _history([10, 11, 10, 12])}

    risk = calculate_portfolio_risk(snapshot, {"PETR4.SA": 12}, histories=histories)

    assert risk.volatility_by_ticker_pct["PETR4.SA"] > 0
    assert risk.portfolio_volatility_pct == pytest.approx(
        risk.volatility_by_ticker_pct["PETR4.SA"]
    )


def test_drawdown_correto():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=1, average_price=100, total_cost=100)],
        realized_pnl=[],
    )
    histories = {"PETR4.SA": _history([100, 120, 90, 110])}

    risk = calculate_portfolio_risk(snapshot, {"PETR4.SA": 110}, histories=histories)

    assert risk.max_drawdown_pct == pytest.approx(-25)


def test_correlacao_com_multiplos_ativos():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("PETR4.SA", quantity=1, average_price=10, total_cost=10),
            Position("VALE3.SA", quantity=1, average_price=20, total_cost=20),
        ],
        realized_pnl=[],
    )
    histories = {
        "PETR4.SA": _history([10, 11, 12, 13]),
        "VALE3.SA": _history([20, 19, 18, 17]),
    }

    risk = calculate_portfolio_risk(
        snapshot,
        {"PETR4.SA": 13, "VALE3.SA": 17},
        histories=histories,
    )

    assert list(risk.correlation.columns) == ["PETR4.SA", "VALE3.SA"]
    assert list(risk.correlation.index) == ["PETR4.SA", "VALE3.SA"]


def test_pagina_carteira_risco_nao_contem_linguagem_proibida():
    page_source = Path("pages/carteira.py").read_text(encoding="utf-8").lower()

    forbidden_terms = [
        "compre",
        "venda",
        "mantenha",
        "recomendado",
        "carteira ideal",
    ]

    assert all(term not in page_source for term in forbidden_terms)


def _history(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": closes},
        index=pd.date_range("2026-01-01", periods=len(closes), freq="B"),
    )
