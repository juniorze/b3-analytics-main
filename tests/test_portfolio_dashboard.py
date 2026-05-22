from __future__ import annotations

import csv
from pathlib import Path

import pytest

from b3analytics.domain.portfolio import (
    PORTFOLIO_EXPORT_COLUMNS,
    PortfolioSnapshot,
    Position,
    RealizedPnL,
    calculate_portfolio_dashboard,
    portfolio_dashboard_to_csv,
)


def test_dashboard_carteira_vazia_gera_totais_zerados():
    dashboard = calculate_portfolio_dashboard(PortfolioSnapshot(positions=[], realized_pnl=[]), {})

    assert dashboard.rows == []
    assert dashboard.totals.current_value == 0
    assert dashboard.totals.total_cost == 0
    assert dashboard.totals.unrealized_pnl == 0
    assert dashboard.totals.unrealized_pnl_pct == 0
    assert dashboard.totals.realized_pnl == 0
    assert dashboard.totals.assets_count == 0
    assert dashboard.totals.missing_quotes_count == 0


def test_dashboard_posicao_com_preco_atual_calcula_valor_atual():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=100, average_price=10, total_cost=1000)],
        realized_pnl=[],
    )

    dashboard = calculate_portfolio_dashboard(snapshot, {"PETR4.SA": {"preco": 12.5}})

    row = dashboard.rows[0]
    assert row.current_price == pytest.approx(12.5)
    assert row.current_value == pytest.approx(1250)
    assert dashboard.totals.current_value == pytest.approx(1250)


def test_dashboard_posicao_sem_preco_atual_nao_quebra():
    snapshot = PortfolioSnapshot(
        positions=[Position("VALE3.SA", quantity=10, average_price=50, total_cost=500)],
        realized_pnl=[],
    )

    dashboard = calculate_portfolio_dashboard(snapshot, {})

    row = dashboard.rows[0]
    assert row.current_price is None
    assert row.current_value is None
    assert row.unrealized_pnl is None
    assert row.unrealized_pnl_pct is None
    assert row.weight_pct is None
    assert row.price_status == "dados indisponiveis"
    assert dashboard.totals.current_value == 0
    assert dashboard.totals.total_cost == pytest.approx(500)
    assert dashboard.totals.missing_quotes_count == 1


def test_dashboard_pl_nao_realizado_rs_e_percentual_corretos():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=100, average_price=10, total_cost=1000)],
        realized_pnl=[],
    )

    dashboard = calculate_portfolio_dashboard(snapshot, {"PETR4.SA": 12.5})

    row = dashboard.rows[0]
    assert row.unrealized_pnl == pytest.approx(250)
    assert row.unrealized_pnl_pct == pytest.approx(25)
    assert dashboard.totals.unrealized_pnl == pytest.approx(250)
    assert dashboard.totals.unrealized_pnl_pct == pytest.approx(25)


def test_dashboard_pesos_somam_cem_para_ativos_com_preco_disponivel():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("PETR4.SA", quantity=100, average_price=10, total_cost=1000),
            Position("VALE3.SA", quantity=20, average_price=50, total_cost=1000),
        ],
        realized_pnl=[],
    )

    dashboard = calculate_portfolio_dashboard(
        snapshot,
        {"PETR4.SA": {"preco": 10}, "VALE3.SA": {"preco": 50}},
    )

    assert sum(row.weight_pct or 0 for row in dashboard.rows) == pytest.approx(100)


def test_dashboard_export_csv_contem_colunas_esperadas():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=100, average_price=10, total_cost=1000)],
        realized_pnl=[],
    )
    dashboard = calculate_portfolio_dashboard(snapshot, {"PETR4.SA": 12})

    content = portfolio_dashboard_to_csv(dashboard.rows)
    rows = list(csv.DictReader(content.splitlines()))

    assert rows
    assert list(rows[0].keys()) == PORTFOLIO_EXPORT_COLUMNS
    assert rows[0]["ticker"] == "PETR4.SA"


def test_dashboard_multiplos_ativos_com_um_sem_cotacao():
    snapshot = PortfolioSnapshot(
        positions=[
            Position("PETR4.SA", quantity=100, average_price=10, total_cost=1000),
            Position("VALE3.SA", quantity=20, average_price=50, total_cost=1000),
        ],
        realized_pnl=[],
    )

    dashboard = calculate_portfolio_dashboard(snapshot, {"PETR4.SA": {"preco": 11}})

    assert dashboard.totals.current_value == pytest.approx(1100)
    assert dashboard.totals.total_cost == pytest.approx(2000)
    assert dashboard.totals.missing_quotes_count == 1
    assert dashboard.rows[0].weight_pct == pytest.approx(100)
    assert dashboard.rows[1].price_status == "dados indisponiveis"


def test_dashboard_pl_realizado_nao_mistura_com_nao_realizado():
    snapshot = PortfolioSnapshot(
        positions=[Position("PETR4.SA", quantity=100, average_price=10, total_cost=1000)],
        realized_pnl=[RealizedPnL("PETR4.SA", realized_pnl=75)],
    )

    dashboard = calculate_portfolio_dashboard(snapshot, {"PETR4.SA": {"preco": 12}})

    assert dashboard.rows[0].unrealized_pnl == pytest.approx(200)
    assert dashboard.rows[0].realized_pnl == pytest.approx(75)
    assert dashboard.totals.unrealized_pnl == pytest.approx(200)
    assert dashboard.totals.realized_pnl == pytest.approx(75)


def test_pagina_carteira_nao_contem_linguagem_proibida():
    page_source = Path("pages/carteira.py").read_text(encoding="utf-8").lower()

    forbidden_terms = [
        "compre",
        "venda",
        "mantenha",
        "recomendado",
        "carteira ideal",
    ]

    assert all(term not in page_source for term in forbidden_terms)
