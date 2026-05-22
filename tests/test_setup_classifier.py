from __future__ import annotations

from b3analytics.domain.setup_classifier import (
    MIN_CONF_ATENCAO,
    MIN_CONF_FAVORAVEL,
    MIN_RR_ATENCAO,
    MIN_RR_FAVORAVEL,
    classify_setup,
)


def _setup(
    direction: str = "LONG",
    confidence: int | None = 75,
    rr: float | None = 2.0,
) -> dict:
    setup = {
        "direction": direction,
        "entry": {"price": 10.0},
        "stop": {"price": 9.0},
        "targets": [{"n": 1, "price": 12.0}],
    }
    if confidence is not None:
        setup["confidence"] = confidence
    if rr is not None:
        setup["targets"][0]["rr"] = rr
    return setup


def test_setup_none_retorna_sem_setup():
    assert classify_setup(None)["status"] == "SEM_SETUP"


def test_long_confianca_75_rr_2_retorna_favoravel_estudo():
    result = classify_setup(_setup(confidence=MIN_CONF_FAVORAVEL, rr=MIN_RR_FAVORAVEL))
    assert result["status"] == "FAVORAVEL_ESTUDO"


def test_long_confianca_65_rr_2_retorna_atencao():
    result = classify_setup(_setup(confidence=MIN_CONF_ATENCAO + 5, rr=MIN_RR_FAVORAVEL))
    assert result["status"] == "ATENCAO"


def test_long_confianca_75_rr_1_7_retorna_atencao():
    result = classify_setup(_setup(confidence=MIN_CONF_FAVORAVEL, rr=MIN_RR_ATENCAO + 0.2))
    assert result["status"] == "ATENCAO"


def test_short_retorna_contrario():
    assert classify_setup(_setup(direction="SHORT"))["status"] == "CONTRARIO"


def test_setup_sem_targets_retorna_dados_insuficientes():
    setup = _setup()
    setup["targets"] = []
    assert classify_setup(setup)["status"] == "DADOS_INSUFICIENTES"


def test_target_sem_rr_retorna_dados_insuficientes():
    assert classify_setup(_setup(rr=None))["status"] == "DADOS_INSUFICIENTES"


def test_entry_price_none_retorna_dados_insuficientes():
    setup = _setup()
    setup["entry"]["price"] = None
    assert classify_setup(setup)["status"] == "DADOS_INSUFICIENTES"


def test_stop_price_none_retorna_dados_insuficientes():
    setup = _setup()
    setup["stop"]["price"] = None
    assert classify_setup(setup)["status"] == "DADOS_INSUFICIENTES"


def test_confidence_ausente_retorna_atencao():
    assert classify_setup(_setup(confidence=None))["status"] == "ATENCAO"


def test_direction_invalida_retorna_dados_insuficientes():
    assert classify_setup(_setup(direction="LATERAL"))["status"] == "DADOS_INSUFICIENTES"


def test_estrutura_inesperada_retorna_erro_calculo():
    assert classify_setup(["invalid"])["status"] == "ERRO_CALCULO"


def test_estrutura_inesperada_sem_vazar_erro_interno():
    result = classify_setup({"direction": "LONG", "entry": {"price": 10.0}, "stop": 9.0})

    assert result["status"] in {"DADOS_INSUFICIENTES", "ERRO_CALCULO"}
    assert all("Traceback" not in warning for warning in result["warnings"])


def test_labels_nao_contem_linguagem_proibida():
    prohibited = {
        "compre",
        "venda",
        "mantenha",
        "recomendacao",
        "carteira ideal",
        "pode comprar",
    }
    samples = [
        None,
        _setup(confidence=75, rr=2.0),
        _setup(confidence=65, rr=2.0),
        _setup(confidence=75, rr=1.7),
        _setup(direction="SHORT"),
        {**_setup(), "targets": []},
        ["invalid"],
    ]

    for sample in samples:
        label = classify_setup(sample)["label"].casefold()
        for term in prohibited:
            assert term not in label
