from __future__ import annotations

import html

from b3analytics.domain.setup_classifier import classify_setup


def setup_semaphore_badge(setup: dict | None, compact: bool = False) -> str:
    classification = classify_setup(setup)
    label = html.escape(classification["label"])
    status = html.escape(classification["status"])
    icon = html.escape(classification["icon"])
    color = classification["color"]
    details = ""

    if not compact:
        reasons = classification.get("reasons") or []
        warnings = classification.get("warnings") or []
        text = " | ".join([*reasons[:2], *warnings[:1]])
        if text:
            details = (
                f'<span style="color:#71717A;font-size:10px;margin-left:8px">'
                f'{html.escape(text)}</span>'
            )

    return (
        f'<span title="{status}" style="display:inline-flex;align-items:center;gap:6px;'
        f'background:{_rgba(color, 0.12)};color:{color};border:1px solid {_rgba(color, 0.4)};'
        f'padding:2px 8px;border-radius:4px;font-family:\'Space Mono\',monospace;'
        f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em">'
        f'<span>{icon}</span><span>{label}</span></span>{details}'
    )


def _rgba(hex_color: str, alpha: float) -> str:
    raw = hex_color.lstrip("#")
    try:
        r = int(raw[0:2], 16)
        g = int(raw[2:4], 16)
        b = int(raw[4:6], 16)
    except (ValueError, IndexError):
        return f"rgba(113,113,122,{alpha})"
    return f"rgba({r},{g},{b},{alpha})"
