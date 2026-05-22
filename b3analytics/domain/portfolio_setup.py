from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from b3analytics.domain.setup_classifier import (
    STATUS_ATENCAO,
    STATUS_CONTRARIO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_ERRO_CALCULO,
    STATUS_FAVORAVEL_ESTUDO,
    STATUS_SEM_SETUP,
)

PORTFOLIO_TECHNICAL_READINGS = {
    STATUS_FAVORAVEL_ESTUDO: "Sinal técnico favorável à posição atual",
    STATUS_ATENCAO: "Sinal técnico com ressalvas",
    STATUS_CONTRARIO: "Atenção: sinal técnico contrário à posição atual",
    STATUS_SEM_SETUP: "Sem setup técnico atual",
    STATUS_DADOS_INSUFICIENTES: "Dados insuficientes para análise técnica",
    STATUS_ERRO_CALCULO: "Não foi possível calcular a avaliação técnica",
}


def portfolio_technical_reading(classification: Mapping[str, Any] | None) -> str:
    if not classification:
        return PORTFOLIO_TECHNICAL_READINGS[STATUS_ERRO_CALCULO]
    status = str(classification.get("status", STATUS_ERRO_CALCULO))
    return PORTFOLIO_TECHNICAL_READINGS.get(
        status,
        PORTFOLIO_TECHNICAL_READINGS[STATUS_ERRO_CALCULO],
    )
