from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from b3analytics.presentation.setup_badges import setup_semaphore_badge
from b3analytics.presentation.theme import COLORS


def fmt_brl(v, casas: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    s = f"{v:,.{casas}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def fmt_pct(v, casas: int = 2, plus: bool = True) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    sign = "+" if plus and v > 0 else ""
    return f"{sign}{v:.{casas}f}%".replace(".", ",")


def fmt_big(v) -> str:
    if v is None:
        return "—"
    if v >= 1e12:  return f"R$ {v/1e12:.1f}T"
    if v >= 1e9:   return f"R$ {v/1e9:.1f}B"
    if v >= 1e6:   return f"R$ {v/1e6:.1f}M"
    return f"R$ {v:,.0f}"


def fmt_mult(v, casas: int = 1) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{casas}f}x"


def direction_badge(direction: str) -> str:
    css = {"LONG": "badge-long", "SHORT": "badge-short"}.get(direction, "badge-neutro")
    return f'<span class="{css}">{direction}</span>'


def trend_arrow(direction: str) -> str:
    return {"ALTA": "↑", "BAIXA": "↓", "LATERAL": "→"}.get(direction, "—")


def trend_arrow_medium(direction: str, strength: int) -> str:
    if direction == "ALTA":
        return "↑" if strength >= 70 else "↗"
    if direction == "BAIXA":
        return "↓" if strength >= 70 else "↘"
    return "→"


def confidence_bar(score: int, direction: str = "LONG"):
    if score >= 70:
        color = COLORS["success"]
    elif score >= 50:
        color = COLORS["warning"]
    else:
        color = COLORS["neutral"]
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:8px">
            <div style="flex:1;background:#27272A;border-radius:4px;height:7px">
                <div style="background:{color};border-radius:4px;height:7px;width:{score}%"></div>
            </div>
            <span style="font-family:'Space Mono',monospace;font-size:11px;color:{color};min-width:44px">{score}/100</span>
        </div>""",
        unsafe_allow_html=True,
    )


def render_setup_card(setup: dict):
    if not setup:
        return

    ticker  = setup["ticker"]
    nome    = setup["name"]
    tipo    = setup["type"]
    direcao = setup["direction"]
    conf    = setup["confidence"]
    trend   = setup["trend"]
    entry   = setup["entry"]
    stop_d  = setup["stop"]
    targets = setup["targets"]
    sz      = setup["sizing"]
    ind     = setup.get("indicators", {})
    preco   = setup["price_current"]

    dir_color  = "#22C55E" if direcao == "LONG" else "#EF4444"
    dir_bg     = "rgba(34,197,94,0.1)"  if direcao == "LONG" else "rgba(239,68,68,0.1)"
    dir_border = "rgba(34,197,94,0.3)"  if direcao == "LONG" else "rgba(239,68,68,0.3)"

    TIPO_CLR = {
        "PULLBACK":   ("#2563EB", "rgba(37,99,235,0.1)",   "rgba(37,99,235,0.3)"),
        "ROMPIMENTO": ("#F59E0B", "rgba(245,158,11,0.1)",  "rgba(245,158,11,0.3)"),
        "REVERSAO":   ("#84CC16", "rgba(132,204,22,0.1)",  "rgba(132,204,22,0.3)"),
        "CRUZAMENTO": ("#A1A1AA", "rgba(113,113,122,0.1)", "rgba(113,113,122,0.3)"),
    }
    tc, tb, tbr = TIPO_CLR.get(tipo, ("#A1A1AA", "rgba(113,113,122,0.1)", "rgba(113,113,122,0.3)"))

    e_price   = entry["price"]
    s_price   = stop_d["price"]
    alloc_val = sz.get("allocated", 0) or 1
    max_loss     = sz.get("max_loss", 0)
    qty          = sz.get("quantity", 0)
    pct_cap      = sz.get("pct_capital", 0)
    loss_pct     = max_loss / alloc_val * 100 if alloc_val > 0 else 0
    max_loss_pct = sz.get("max_loss_pct", loss_pct)
    capital_op_v = sz.get("capital_op", alloc_val)

    def _tm(alvo):
        g = abs(alvo["price"] - e_price) * qty
        return {
            "ganho": g,
            "roi":   g / alloc_val * 100,
            "pct":   abs(alvo["price"] - e_price) / e_price * 100 if e_price else 0,
            "rr":    alvo["rr"],
        }

    tm = [_tm(t) for t in targets]

    conf_color = "#22C55E" if conf >= 70 else "#F59E0B" if conf >= 50 else "#71717A"

    def _dclr(d: str) -> str:
        return {"ALTA": "#22C55E", "BAIXA": "#EF4444", "LATERAL": "#F59E0B"}.get(d, "#71717A")
    def _darr(d: str) -> str:
        return {"ALTA": "↑", "BAIXA": "↓", "LATERAL": "→"}.get(d, "—")

    lng      = trend.get("long",   {})
    med      = trend.get("medium", {})
    sht      = trend.get("short",  {})
    lng_dir  = lng.get("direction", "LATERAL"); lng_str  = lng.get("strength", 30)
    med_dir  = med.get("direction", "LATERAL"); med_str  = med.get("strength", 30)
    sht_dir  = sht.get("direction", "LATERAL"); sht_str  = sht.get("strength", 30)
    lng_sma  = lng.get("sma_len", 200)
    lng_note = lng.get("note", "")

    lng_note_html = (
        f'<div style="color:#71717A;font-size:10px;margin-top:8px;padding-top:6px;'
        f'border-top:1px solid #27272A">{lng_note}</div>'
        if lng_note else ""
    )
    trend_html = (
        f'<div style="background:#09090B;border:1px solid #27272A;border-radius:6px;'
        f'padding:10px 14px;margin-bottom:14px">'
        f'<div style="color:#A1A1AA;font-size:10px;text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-bottom:8px">Tendência</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">'
        f'<div style="text-align:center">'
        f'<div style="color:#71717A;font-size:9px;text-transform:uppercase;'
        f'letter-spacing:0.06em;margin-bottom:3px">Longo</div>'
        f'<div style="font-family:\'Space Mono\',monospace;font-size:0.9rem;font-weight:700;'
        f'color:{_dclr(lng_dir)}">{_darr(lng_dir)} {lng_dir}</div>'
        f'<div style="background:#27272A;border-radius:2px;height:3px;margin-top:4px">'
        f'<div style="background:{_dclr(lng_dir)};width:{lng_str}%;height:3px;'
        f'border-radius:2px;opacity:0.6"></div></div>'
        f'<div style="color:#71717A;font-size:9px;margin-top:2px">SMA{lng_sma}</div>'
        f'</div>'
        f'<div style="text-align:center">'
        f'<div style="color:#71717A;font-size:9px;text-transform:uppercase;'
        f'letter-spacing:0.06em;margin-bottom:3px">Médio</div>'
        f'<div style="font-family:\'Space Mono\',monospace;font-size:0.9rem;font-weight:700;'
        f'color:{_dclr(med_dir)}">{_darr(med_dir)} {med_dir}</div>'
        f'<div style="background:#27272A;border-radius:2px;height:3px;margin-top:4px">'
        f'<div style="background:{_dclr(med_dir)};width:{med_str}%;height:3px;'
        f'border-radius:2px;opacity:0.6"></div></div>'
        f'<div style="color:#71717A;font-size:9px;margin-top:2px">SMA50</div>'
        f'</div>'
        f'<div style="text-align:center">'
        f'<div style="color:#71717A;font-size:9px;text-transform:uppercase;'
        f'letter-spacing:0.06em;margin-bottom:3px">Curto</div>'
        f'<div style="font-family:\'Space Mono\',monospace;font-size:0.9rem;font-weight:700;'
        f'color:{_dclr(sht_dir)}">{_darr(sht_dir)} {sht_dir}</div>'
        f'<div style="background:#27272A;border-radius:2px;height:3px;margin-top:4px">'
        f'<div style="background:{_dclr(sht_dir)};width:{sht_str}%;height:3px;'
        f'border-radius:2px;opacity:0.6"></div></div>'
        f'<div style="color:#71717A;font-size:9px;margin-top:2px">EMA9/21</div>'
        f'</div>'
        f'</div>'
        f'{lng_note_html}'
        f'</div>'
    )

    sinais = [s.strip() for s in (entry.get("rationale", "") or "").split("|") if s.strip()]
    sinal_chips = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;padding:5px 10px;'
        f'background:#09090B;border:1px solid #27272A;border-radius:5px;margin-bottom:4px">'
        f'<span style="color:#22C55E;font-size:12px">✓</span>'
        f'<span style="font-family:\'DM Sans\',sans-serif;font-size:12px;color:#A1A1AA">{s}</span>'
        f'</div>'
        for s in sinais
    )
    sinal_html = (
        f'<div style="margin-bottom:14px">'
        f'<div style="color:#71717A;font-size:10px;text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-bottom:6px">Sinais detectados</div>'
        f'{sinal_chips}</div>'
        if sinal_chips else ""
    )

    trows = ""
    for i, t in enumerate(targets):
        m = tm[i]
        trows += (
            '<div style="display:grid;grid-template-columns:24px 1fr auto auto auto;gap:8px;align-items:center;'
            'padding:8px 12px;background:#09090B;border-radius:6px;margin-bottom:6px;border:1px solid #27272A">'
            f'<span style="font-family:\'Space Mono\',monospace;font-size:10px;color:#71717A">A{t["n"]}</span>'
            f'<span style="font-family:\'Space Mono\',monospace;font-size:0.92rem;font-weight:700;color:#22C55E">{fmt_brl(t["price"])}</span>'
            f'<span style="font-size:10px;background:rgba(132,204,22,0.1);color:#84CC16;border:1px solid rgba(132,204,22,0.2);padding:1px 6px;border-radius:3px;font-family:\'Space Mono\',monospace">+{m["pct"]:.1f}%</span>'
            f'<span style="font-size:10px;color:#22C55E;font-family:\'Space Mono\',monospace">+{fmt_brl(m["ganho"], casas=0)}</span>'
            f'<span style="font-size:10px;background:rgba(37,99,235,0.1);color:#2563EB;border:1px solid rgba(37,99,235,0.2);padding:1px 6px;border-radius:3px;font-family:\'Space Mono\',monospace">R/R {m["rr"]:.1f}x</span>'
            '</div>'
        )

    ganho_a1 = tm[0]["ganho"] if tm else 0
    ganho_a2 = tm[1]["ganho"] if len(tm) > 1 else 0
    ganho_a3 = tm[2]["ganho"] if len(tm) > 2 else 0
    roi_a1   = tm[0]["roi"]   if tm else 0
    roi_a2   = tm[1]["roi"]   if len(tm) > 1 else 0
    roi_a3   = tm[2]["roi"]   if len(tm) > 2 else 0
    pct_a1   = tm[0]["pct"]   if tm else 0
    rr_a1    = targets[0]["rr"] if targets else 1.5
    barra_r  = round(100 / (1 + rr_a1), 1)

    a2a3_html = ""
    if ganho_a2 > 0:
        a2a3_html = (
            f'<div style="display:flex;gap:20px;margin-top:8px">'
            f'<span style="font-family:\'Space Mono\',monospace;font-size:0.9rem;color:#4ADE80">+{fmt_brl(ganho_a2, casas=0)}'
            f'<span style="font-size:10px;color:#71717A;margin-left:4px">A2 · {roi_a2:.1f}% ROI</span></span>'
            f'<span style="font-family:\'Space Mono\',monospace;font-size:0.9rem;color:#4ADE80">+{fmt_brl(ganho_a3, casas=0)}'
            f'<span style="font-size:10px;color:#71717A;margin-left:4px">A3 · {roi_a3:.1f}% ROI</span></span>'
            f'</div>'
        )

    html = f"""<div style="background:#18181B;border:1px solid #27272A;border-left:3px solid {dir_color};border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.4)">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
    <div>
      <span style="font-family:'Space Mono',monospace;font-size:1rem;font-weight:700;color:#FAFAFA">{ticker}</span>
      <span style="color:#71717A;font-size:0.8rem;margin-left:10px">{nome}</span>
      <div style="margin-top:8px">{setup_semaphore_badge(setup, compact=True)}</div>
    </div>
    <div style="display:flex;gap:6px;align-items:center">
      <span style="background:{tb};color:{tc};border:1px solid {tbr};padding:2px 8px;border-radius:4px;font-family:'Space Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:0.08em">{tipo}</span>
      <span style="background:{dir_bg};color:{dir_color};border:1px solid {dir_border};padding:2px 10px;border-radius:4px;font-family:'Space Mono',monospace;font-size:11px;font-weight:700">{direcao}</span>
    </div>
  </div>
  <div style="margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;margin-bottom:5px">
      <span style="color:#A1A1AA;font-size:11px;text-transform:uppercase;letter-spacing:0.08em">Confiança</span>
      <span style="font-family:'Space Mono',monospace;font-size:12px;color:{conf_color};font-weight:700">{conf}/100</span>
    </div>
    <div style="background:#27272A;border-radius:3px;height:4px"><div style="background:{conf_color};width:{conf}%;height:4px;border-radius:3px"></div></div>
  </div>
  {trend_html}
  {sinal_html}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">
    <div style="background:#09090B;border:1px solid #27272A;border-radius:6px;padding:10px 14px">
      <div style="color:#A1A1AA;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Entrada</div>
      <div style="font-family:'Space Mono',monospace;font-size:1.1rem;font-weight:700;color:#2563EB">{fmt_brl(e_price)}</div>
      <div style="color:#71717A;font-size:10px;margin-top:2px">{entry["type"]}</div>
    </div>
    <div style="background:#09090B;border:1px solid rgba(239,68,68,0.25);border-radius:6px;padding:10px 14px">
      <div style="color:#A1A1AA;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Stop Loss</div>
      <div style="font-family:'Space Mono',monospace;font-size:1.1rem;font-weight:700;color:#EF4444">{fmt_brl(s_price)}</div>
      <div style="color:#EF4444;font-size:10px;font-family:'Space Mono',monospace;margin-top:2px">-{stop_d["distance_pct"]:.1f}%</div>
    </div>
  </div>
  <div style="margin-bottom:14px">
    <div style="color:#A1A1AA;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Alvos</div>
    {trows}
  </div>
  <div style="border-top:1px solid #27272A;padding-top:12px">
    <div style="display:flex;align-items:center;gap:0;margin-bottom:12px;font-family:'Space Mono',monospace;font-size:11px;flex-wrap:wrap">
      <span style="color:#FAFAFA;font-weight:700">{qty}</span>
      <span style="color:#71717A;margin-left:3px">ações</span>
      <span style="color:#3F3F46;margin:0 10px">|</span>
      <span style="color:#FAFAFA;font-weight:700">{fmt_brl(alloc_val)}</span>
      <span style="color:#71717A;margin-left:4px">({pct_cap:.1f}%)</span>
      <span style="color:#3F3F46;margin:0 10px">|</span>
      <span style="color:#71717A">capital/op </span>
      <span style="color:#A1A1AA;margin-left:3px">{fmt_brl(capital_op_v)}</span>
    </div>
    <div style="background:rgba(34,197,94,0.05);border:1px solid rgba(34,197,94,0.2);border-radius:8px;padding:12px 14px;margin-bottom:8px">
      <div style="color:#71717A;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Ganho Potencial</div>
      <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
        <span style="font-family:'Space Mono',monospace;font-size:1.6rem;font-weight:700;color:#22C55E;line-height:1">+{fmt_brl(ganho_a1, casas=0)}</span>
        <span style="font-family:'Space Mono',monospace;font-size:11px;color:#84CC16">+{roi_a1:.1f}% ROI</span>
        <span style="font-size:11px;color:#71717A">A1 (+{pct_a1:.1f}%)</span>
      </div>
      {a2a3_html}
    </div>
    <div style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);border-radius:8px;padding:10px 14px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="color:#71717A;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Risco Máximo</div>
        <span style="font-family:'Space Mono',monospace;font-size:1rem;font-weight:700;color:#EF4444">-{fmt_brl(max_loss, casas=0)}</span>
        <span style="font-family:'Space Mono',monospace;font-size:10px;color:#EF4444;margin-left:8px">-{max_loss_pct:.1f}% capital</span>
      </div>
      <div style="text-align:right">
        <div style="color:#71717A;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Stop</div>
        <span style="font-family:'Space Mono',monospace;font-size:10px;color:#EF4444">-{stop_d["distance_pct"]:.1f}% entrada</span>
      </div>
    </div>
    <div>
      <div style="display:flex;height:8px;border-radius:4px;overflow:hidden;margin-bottom:5px">
        <div style="background:#EF4444;width:{barra_r}%;opacity:0.75"></div>
        <div style="background:#22C55E;flex:1;opacity:0.75"></div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="color:#EF4444;font-size:10px;font-family:'Space Mono',monospace">{barra_r:.0f}% risco</span>
        <span style="color:#A1A1AA;font-size:10px;font-family:'Space Mono',monospace">R/R {rr_a1:.1f}x</span>
        <span style="color:#22C55E;font-size:10px;font-family:'Space Mono',monospace">{round(100-barra_r):.0f}% ganho A1</span>
      </div>
    </div>
    <div style="display:flex;gap:12px;margin-top:10px;flex-wrap:wrap">
      <span style="font-size:10px;color:#71717A">RSI <span style="font-family:'Space Mono',monospace;color:#A1A1AA">{ind.get("rsi", "—")}</span></span>
      <span style="font-size:10px;color:#71717A">ATR <span style="font-family:'Space Mono',monospace;color:#A1A1AA">{fmt_brl(ind.get("atr", 0))}</span></span>
      <span style="font-size:10px;color:#71717A">Vol <span style="font-family:'Space Mono',monospace;color:#A1A1AA">{ind.get("vol_ratio", 0):.1f}x</span></span>
      <span style="font-size:10px;color:#71717A">EMA9 <span style="font-family:'Space Mono',monospace;color:#A1A1AA">{fmt_brl(ind.get("ema9", 0))}</span></span>
      <span style="font-size:10px;color:#71717A">SMA50 <span style="font-family:'Space Mono',monospace;color:#A1A1AA">{fmt_brl(ind.get("sma50", 0))}</span></span>
      <span style="font-size:10px;color:#71717A">Preço <span style="font-family:'Space Mono',monospace;color:#FAFAFA;font-weight:700">{fmt_brl(preco)}</span></span>
    </div>
  </div>
</div>"""
    st.markdown(html, unsafe_allow_html=True)


setup_card = render_setup_card


def _render_ai_details(resultado: dict, ticker: str) -> None:
    import time
    score     = resultado.get("macro_score", 0)
    label     = resultado.get("macro_label", "NEUTRO")
    align     = resultado.get("setup_alinhamento", "SEM_SETUP")
    clr       = "#22C55E" if score > 20 else "#EF4444" if score < -20 else "#F59E0B"
    a_clr     = {"ALINHADO":"#22C55E","CONFLITO":"#EF4444",
                 "NEUTRO":"#F59E0B","SEM_SETUP":"#71717A"}.get(align, "#71717A")
    cached_at = resultado.get("cached_at", 0)
    age_min   = int((time.time() - cached_at) / 60) if cached_at else None
    age_txt   = f" · cache {age_min} min" if age_min is not None else ""

    st.markdown(
        f"<div style='background:#18181B;border:1px solid #27272A;border-radius:8px;"
        f"padding:14px 18px;margin-bottom:8px'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center'>"
        f"<div><span style='font-family:Space Mono;font-size:1.2rem;font-weight:700;"
        f"color:{clr}'>{score:+d}</span>"
        f"<span style='color:{clr};font-size:12px;margin-left:8px'>{label}</span></div>"
        f"<span style='font-family:Space Mono;color:{a_clr};font-size:11px'>{align}</span>"
        f"</div>"
        f"<div style='color:#71717A;font-size:11px;margin-top:4px'>"
        f"{resultado.get('alinhamento_explicacao','')}{age_txt}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    parecer = resultado.get("parecer_integrado") or resultado.get("parecer_macro")
    if parecer:
        if score > 20:
            st.success(parecer)
        elif score < -20:
            st.error(parecer)
        else:
            st.warning(parecer)


def render_ai_badge(
    ticker:  str,
    nome:    str,
    setor:   str,
    setup:   dict | None = None,
    compact: bool = True,
) -> None:
    from b3analytics.infrastructure.ai_cache import get_cached
    from b3analytics.infrastructure.ai_config import (
        AI_PROVIDERS,
        get_active_provider,
        get_ttl,
        is_configured,
        is_local_agent_available,
    )
    resultado = get_cached(ticker, ttl=get_ttl())
    if not resultado:
        _provider     = get_active_provider()
        _requires_key = AI_PROVIDERS[_provider]["requires_key"]
        _ia_ok        = (not _requires_key and is_local_agent_available()) or is_configured(_provider)
        if not compact:
            if _ia_ok:
                if st.button("🧠 Analisar com IA", key=f"ia_badge_btn_{ticker}", width="stretch"):
                    st.session_state["ia_ticker"] = ticker
                    st.switch_page("pages/ia.py")
            else:
                st.caption("IA: configure um provider na página ⚙️ IA.")
        return
    score = resultado.get("macro_score", 0)
    label = resultado.get("macro_label", "NEUTRO")
    align = resultado.get("setup_alinhamento", "SEM_SETUP")
    clr   = "#22C55E" if score > 20 else "#EF4444" if score < -20 else "#F59E0B"
    a_clr = {"ALINHADO":"#22C55E","CONFLITO":"#EF4444",
              "NEUTRO":"#F59E0B","SEM_SETUP":"#71717A"}.get(align, "#71717A")
    if compact:
        col_badge, col_btn = st.columns([6, 1])
        with col_badge:
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"padding:5px 10px;background:#09090B;border:1px solid #27272A;"
                f"border-radius:5px;margin-bottom:2px'>"
                f"<span style='font-family:IBM Plex Mono,monospace;color:{clr};font-size:11px'>"
                f"Macro {score:+d} · {label}</span>"
                f"<span style='font-family:IBM Plex Mono,monospace;color:{a_clr};font-size:11px'>"
                f"{align}</span></div>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("↗", key=f"ia_badge_goto_{ticker}", help="Ver análise IA", width="stretch"):
                st.session_state["ia_ticker"] = ticker
                st.switch_page("pages/ia.py")
    else:
        _render_ai_details(resultado, ticker)


def sparkline(prices: list, height: int = 80) -> go.Figure:
    if not prices or len(prices) < 2:
        return go.Figure()
    color = COLORS["success"] if prices[-1] >= prices[0] else COLORS["error"]
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    fig = go.Figure(go.Scatter(
        y=prices, mode="lines",
        line=dict(color=color, width=1.8),
        fill="tozeroy",
        fillcolor=f"rgba({r},{g},{b},0.10)",
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False,
    )
    return fig


def render_fundamentals(fund: dict):
    if not fund:
        st.info("Dados não disponíveis.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.metric("P/L",         fmt_mult(fund.get("pl")))
        st.metric("P/VP",        fmt_mult(fund.get("pvp")))
        st.metric("EV/EBITDA",   fmt_mult(fund.get("ev_ebitda")))
        st.metric("Market Cap",  fund.get("market_cap") or "—")
    with col2:
        dy = fund.get("dy")
        st.metric("Div. Yield",  f"{dy:.2f}%" if dy else "—")
        roe = fund.get("roe")
        st.metric("ROE",         f"{roe:.1f}%" if roe else "—")
        mg = fund.get("margem_liquida")
        st.metric("Margem Liq.", f"{mg:.1f}%" if mg else "—")
        beta = fund.get("beta")
        st.metric("Beta",        f"{beta:.2f}" if beta else "—")

    mn = fund.get("min_52s")
    mx = fund.get("max_52s")
    if mn and mx:
        st.caption(f"52 semanas: {fmt_brl(mn)} — {fmt_brl(mx)}")
    if fund.get("setor"):
        st.caption(f"Setor: {fund.get('setor')}")
