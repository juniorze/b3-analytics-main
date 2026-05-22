from __future__ import annotations

import sqlite3

import pytest

from b3analytics.domain.portfolio import PortfolioValidationError, calculate_portfolio
from b3analytics.infrastructure.portfolio_store import PortfolioStore


def _store(tmp_path) -> PortfolioStore:
    return PortfolioStore(tmp_path / "portfolio.sqlite3")


def test_carteira_vazia(tmp_path):
    store = _store(tmp_path)

    assert store.list_transactions() == []
    snapshot = store.get_snapshot()
    assert snapshot.positions == []
    assert snapshot.realized_pnl == []


def test_compra_inicial(tmp_path):
    store = _store(tmp_path)

    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 100, 10, 2))

    position = store.get_snapshot().positions[0]
    assert position.ticker == "PETR4.SA"
    assert position.quantity == 100
    assert position.average_price == pytest.approx(10.02)
    assert position.total_cost == pytest.approx(1002)


def test_compra_adicional_com_novo_preco_medio(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 100, 10, 0))
    store.add_transaction(_tx("2026-01-02", "PETR4", "BUY", 100, 20, 0))

    position = store.get_snapshot().positions[0]

    assert position.quantity == 200
    assert position.average_price == pytest.approx(15)
    assert position.total_cost == pytest.approx(3000)


def test_venda_parcial_mantem_preco_medio(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 100, 10, 0))
    store.add_transaction(_tx("2026-01-02", "PETR4", "SELL", 40, 12, 0))

    position = store.get_snapshot().positions[0]

    assert position.quantity == 60
    assert position.average_price == pytest.approx(10)
    assert position.total_cost == pytest.approx(600)


def test_venda_total_zera_posicao(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 100, 10, 0))
    store.add_transaction(_tx("2026-01-02", "PETR4", "SELL", 100, 11, 0))

    snapshot = store.get_snapshot()

    assert snapshot.positions == []
    assert snapshot.realized_pnl[0].realized_pnl == pytest.approx(100)


def test_recompra_apos_zerar_posicao_usa_novo_preco_medio(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 100, 10, 0))
    store.add_transaction(_tx("2026-01-02", "PETR4", "SELL", 100, 11, 0))
    store.add_transaction(_tx("2026-01-03", "PETR4", "BUY", 50, 20, 0))

    position = store.get_snapshot().positions[0]

    assert position.quantity == 50
    assert position.average_price == pytest.approx(20)
    assert position.total_cost == pytest.approx(1000)


def test_bloqueio_de_venda_maior_que_posicao(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 10, 10, 0))

    with pytest.raises(PortfolioValidationError):
        store.add_transaction(_tx("2026-01-02", "PETR4", "SELL", 11, 10, 0))

    assert len(store.list_transactions()) == 1


def test_calculo_de_pl_realizado_com_taxas(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 100, 10, 5))
    store.add_transaction(_tx("2026-01-02", "PETR4", "SELL", 40, 12, 3))

    realized = store.get_snapshot().realized_pnl[0]

    assert realized.ticker == "PETR4.SA"
    assert realized.realized_pnl == pytest.approx(75)


def test_ticker_lowercase_normalizado(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "petr4.sa", "BUY", 1, 10, 0))

    assert store.list_transactions()[0].ticker == "PETR4.SA"


def test_ticker_sem_sa_tratado_de_forma_padronizada(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "vale3", "BUY", 1, 10, 0))

    assert store.list_transactions()[0].ticker == "VALE3.SA"


def test_operacao_invalida_nao_corrompe_o_banco(tmp_path):
    store = _store(tmp_path)
    store.add_transaction(_tx("2026-01-01", "PETR4", "BUY", 10, 10, 0))

    with pytest.raises(PortfolioValidationError):
        store.add_transactions(
            [
                _tx("2026-01-02", "VALE3", "BUY", 5, 20, 0),
                _tx("2026-01-03", "PETR4", "SELL", 99, 10, 0),
            ]
        )

    transactions = store.list_transactions()
    assert len(transactions) == 1
    assert transactions[0].ticker == "PETR4.SA"

    with sqlite3.connect(store.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert count == 1


def test_calculate_portfolio_aceita_lista_vazia():
    snapshot = calculate_portfolio([])

    assert snapshot.positions == []
    assert snapshot.realized_pnl == []


def _tx(date, ticker, operation_type, quantity, price, fees):
    return {
        "date": date,
        "ticker": ticker,
        "type": operation_type,
        "quantity": quantity,
        "price": price,
        "fees": fees,
        "broker": "",
        "asset_class": "ACAO",
        "notes": "",
    }
