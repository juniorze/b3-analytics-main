from __future__ import annotations

from b3analytics.infrastructure.portfolio_import import parse_portfolio_csv

HEADER = "date,ticker,type,quantity,price,fees,broker,asset_class,notes\n"


def test_csv_valido():
    content = (
        HEADER
        + "2026-01-01,petr4,BUY,100,10,1,Corretora,ACAO,entrada\n"
        + "2026-01-02,PETR4.SA,SELL,40,12,0,Corretora,ACAO,saida\n"
    )

    preview = parse_portfolio_csv(content)

    assert preview.errors == []
    assert preview.can_import is True
    assert len(preview.valid_rows) == 2
    assert preview.valid_rows[0].ticker == "PETR4.SA"


def test_csv_com_coluna_faltando():
    content = "date,ticker,type,quantity,price,broker,asset_class,notes\n"
    preview = parse_portfolio_csv(content)

    assert preview.valid_rows == []
    assert len(preview.errors) == 1
    assert "fees" in preview.errors[0].message
    assert preview.can_import is False


def test_csv_com_tipo_invalido():
    content = HEADER + "2026-01-01,PETR4,HOLD,100,10,0,,ACAO,\n"

    preview = parse_portfolio_csv(content)

    assert preview.valid_rows == []
    assert preview.errors[0].line == 2
    assert "BUY ou SELL" in preview.errors[0].message
    assert preview.can_import is False


def test_csv_com_quantidade_negativa():
    content = HEADER + "2026-01-01,PETR4,BUY,-1,10,0,,ACAO,\n"

    preview = parse_portfolio_csv(content)

    assert preview.valid_rows == []
    assert preview.errors[0].line == 2
    assert "Quantidade" in preview.errors[0].message


def test_csv_com_venda_maior_que_posicao():
    content = HEADER + "2026-01-01,PETR4,SELL,1,10,0,,ACAO,\n"

    preview = parse_portfolio_csv(content)

    assert preview.valid_rows == []
    assert preview.errors[0].line == 2
    assert "posicao atual" in preview.errors[0].message
    assert preview.can_import is False
