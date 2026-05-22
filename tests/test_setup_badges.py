from __future__ import annotations

from b3analytics.presentation.setup_badges import (
    portfolio_empty_setup_state,
    setup_educational_notice,
    setup_empty_state,
    setup_scan_prompt,
    setup_semaphore_legend,
    setup_status_label,
)


def test_setup_presentation_texts_are_educational_and_neutral():
    texts = [
        setup_educational_notice(),
        setup_semaphore_legend(),
        setup_empty_state(),
        setup_scan_prompt(),
        portfolio_empty_setup_state(),
    ]
    prohibited = {
        "compre",
        "venda",
        "mantenha",
        "pode comprar",
        "recomendado para voce",
        "carteira ideal",
        "aumente posicao",
        "reduza posicao",
        "zere posicao",
    }

    for text in texts:
        normalized = text.casefold()
        for term in prohibited:
            assert term not in normalized


def test_setup_status_label_uses_classifier_icon_and_label():
    assert setup_status_label({"icon": "!", "label": "Atencao"}) == "! Atencao"
