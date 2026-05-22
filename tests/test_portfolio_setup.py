from __future__ import annotations

from b3analytics.domain.portfolio_setup import portfolio_technical_reading
from b3analytics.domain.setup_classifier import (
    STATUS_ATENCAO,
    STATUS_CONTRARIO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_ERRO_CALCULO,
    STATUS_FAVORAVEL_ESTUDO,
    STATUS_SEM_SETUP,
)


def test_portfolio_technical_reading_mapeia_status_esperados():
    expected = {
        STATUS_FAVORAVEL_ESTUDO: "Sinal técnico favorável à posição atual",
        STATUS_ATENCAO: "Sinal técnico com ressalvas",
        STATUS_CONTRARIO: "Atenção: sinal técnico contrário à posição atual",
        STATUS_SEM_SETUP: "Sem setup técnico atual",
        STATUS_DADOS_INSUFICIENTES: "Dados insuficientes para análise técnica",
        STATUS_ERRO_CALCULO: "Não foi possível calcular a avaliação técnica",
    }

    for status, reading in expected.items():
        assert portfolio_technical_reading({"status": status}) == reading


def test_portfolio_technical_reading_status_desconhecido_retorna_erro_calculo():
    assert (
        portfolio_technical_reading({"status": "DESCONHECIDO"})
        == "Não foi possível calcular a avaliação técnica"
    )


def test_portfolio_technical_reading_nao_usa_linguagem_proibida():
    prohibited = {
        "compre",
        "venda",
        "mantenha",
        "recomendado para você",
        "carteira ideal",
        "pode comprar",
        "aumente posição",
        "reduza posição",
        "zere posição",
    }

    for status in (
        STATUS_FAVORAVEL_ESTUDO,
        STATUS_ATENCAO,
        STATUS_CONTRARIO,
        STATUS_SEM_SETUP,
        STATUS_DADOS_INSUFICIENTES,
        STATUS_ERRO_CALCULO,
    ):
        reading = portfolio_technical_reading({"status": status}).casefold()
        for term in prohibited:
            assert term not in reading
