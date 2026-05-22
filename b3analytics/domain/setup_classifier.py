from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

STATUS_FAVORAVEL_ESTUDO = "FAVORAVEL_ESTUDO"
STATUS_ATENCAO = "ATENCAO"
STATUS_CONTRARIO = "CONTRARIO"
STATUS_SEM_SETUP = "SEM_SETUP"
STATUS_DADOS_INSUFICIENTES = "DADOS_INSUFICIENTES"
STATUS_ERRO_CALCULO = "ERRO_CALCULO"

MIN_CONF_FAVORAVEL = 70
MIN_CONF_ATENCAO = 60
MIN_RR_FAVORAVEL = 2.0
MIN_RR_ATENCAO = 1.5


_META = {
    STATUS_FAVORAVEL_ESTUDO: {
        "label": "Favoravel para estudo",
        "icon": "●",
        "color": "#22C55E",
        "severity": "success",
    },
    STATUS_ATENCAO: {
        "label": "Atencao",
        "icon": "●",
        "color": "#F59E0B",
        "severity": "warning",
    },
    STATUS_CONTRARIO: {
        "label": "Sinal tecnico baixista",
        "icon": "●",
        "color": "#EF4444",
        "severity": "danger",
    },
    STATUS_SEM_SETUP: {
        "label": "Sem setup atual",
        "icon": "○",
        "color": "#71717A",
        "severity": "neutral",
    },
    STATUS_DADOS_INSUFICIENTES: {
        "label": "Dados insuficientes",
        "icon": "○",
        "color": "#71717A",
        "severity": "neutral",
    },
    STATUS_ERRO_CALCULO: {
        "label": "Erro de calculo",
        "icon": "!",
        "color": "#EF4444",
        "severity": "error",
    },
}


def classify_setup(setup: Mapping[str, Any] | None) -> dict:
    try:
        if setup is None:
            return _result(STATUS_SEM_SETUP, ["Nenhum setup tecnico identificado."])

        if not isinstance(setup, Mapping):
            return _result(
                STATUS_ERRO_CALCULO,
                ["Estrutura de setup inesperada."],
                warnings=["setup deve ser um mapeamento."],
            )

        direction = setup.get("direction")
        confidence = _as_float(setup.get("confidence"))
        entry_price = _nested_number(setup, "entry", "price")
        stop_price = _nested_number(setup, "stop", "price")
        targets = setup.get("targets")
        rr_a1 = _target_rr(targets)
        target_price = _target_price(targets)

        missing = []
        if entry_price is None:
            missing.append("entry")
        if stop_price is None:
            missing.append("stop")
        if not targets:
            missing.append("targets")
        elif rr_a1 is None:
            missing.append("rr")
        if target_price is None:
            missing.append("target")

        if missing:
            return _result(
                STATUS_DADOS_INSUFICIENTES,
                [f"Campos tecnicos ausentes ou invalidos: {', '.join(dict.fromkeys(missing))}."],
                warnings=["Classificacao limitada por dados incompletos."],
            )

        warnings = []
        if confidence is None:
            warnings.append("Confianca ausente ou invalida.")

        if direction == "SHORT":
            return _result(STATUS_CONTRARIO, ["Direcao SHORT indica sinal tecnico baixista."], warnings)

        if direction != "LONG":
            return _result(
                STATUS_DADOS_INSUFICIENTES,
                ["Direcao tecnica ausente ou inesperada."],
                warnings + ["Direcao esperada: LONG ou SHORT."],
            )

        valid_prices = entry_price > 0 and stop_price > 0 and target_price > 0
        if (
            confidence is not None
            and confidence >= MIN_CONF_FAVORAVEL
            and rr_a1 >= MIN_RR_FAVORAVEL
            and valid_prices
        ):
            return _result(
                STATUS_FAVORAVEL_ESTUDO,
                [
                    f"Direcao LONG, confianca >= {MIN_CONF_FAVORAVEL} "
                    f"e R/R do alvo 1 >= {MIN_RR_FAVORAVEL:.1f}."
                ],
                warnings,
            )

        reasons = []
        if confidence is None:
            reasons.append("Confianca tecnica ausente ou invalida.")
        elif MIN_CONF_ATENCAO <= confidence < MIN_CONF_FAVORAVEL:
            reasons.append(f"Confianca entre {MIN_CONF_ATENCAO} e {MIN_CONF_FAVORAVEL - 1}.")
        elif confidence < MIN_CONF_ATENCAO:
            reasons.append(f"Confianca abaixo de {MIN_CONF_ATENCAO}.")
        if MIN_RR_ATENCAO <= rr_a1 < MIN_RR_FAVORAVEL:
            reasons.append(
                f"R/R do alvo 1 entre {MIN_RR_ATENCAO:.1f} e {MIN_RR_FAVORAVEL - 0.01:.2f}."
            )
        elif rr_a1 < MIN_RR_ATENCAO:
            reasons.append(f"R/R do alvo 1 abaixo de {MIN_RR_ATENCAO:.1f}.")
        if not valid_prices:
            reasons.append("Precos tecnicos parciais ou invalidos.")
        if not reasons:
            reasons.append("Setup LONG valido, mas sem todos os criterios de destaque.")

        return _result(STATUS_ATENCAO, reasons, warnings)
    except Exception:
        return _result(
            STATUS_ERRO_CALCULO,
            ["Falha tratada ao classificar setup."],
            warnings=["Erro interno tratado durante a classificacao."],
        )


def _result(status: str, reasons: list[str], warnings: list[str] | None = None) -> dict:
    meta = _META[status]
    return {
        "status": status,
        "label": meta["label"],
        "icon": meta["icon"],
        "color": meta["color"],
        "severity": meta["severity"],
        "reasons": reasons,
        "warnings": warnings or [],
    }


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    return float(value)


def _nested_number(data: Mapping[str, Any], key: str, subkey: str) -> float | None:
    nested = data.get(key)
    if not isinstance(nested, Mapping):
        return None
    return _as_float(nested.get(subkey))


def _first_target(targets: Any) -> Mapping[str, Any] | None:
    if not isinstance(targets, list) or not targets:
        return None
    first = targets[0]
    return first if isinstance(first, Mapping) else None


def _target_rr(targets: Any) -> float | None:
    target = _first_target(targets)
    if target is None:
        return None
    return _as_float(target.get("rr"))


def _target_price(targets: Any) -> float | None:
    target = _first_target(targets)
    if target is None:
        return None
    return _as_float(target.get("price"))
