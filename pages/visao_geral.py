from __future__ import annotations

import logging

import streamlit as st

from b3analytics.config.assets import get_acoes, get_grupos
from b3analytics.domain.engine import find_setup
from b3analytics.domain.trend import analyze_trend
from b3analytics.infrastructure.ai_cache import get_cached
from b3analytics.infrastructure.ai_config import get_ttl
from b3analytics.infrastructure.fetcher import get_historico, get_precos_atuais
from b3analytics.presentation.components import (
    fmt_brl,
    fmt_pct,
    sparkline,
)
from b3analytics.presentation.setup_badges import setup_semaphore_badge

ACOES  = get_acoes()
GRUPOS = get_grupos()

logger = logging.getLogger(__name__)


def _trend_compact(tr: dict | None) -> str:
    if not tr:
        return '<span style="color:#3F3F46">N/D</span>'
    _c = {"ALTA": "#22C55E", "BAIXA": "#EF4444", "LATERAL": "#F59E0B"}
    _a = {"ALTA": "↑", "BAIXA": "↓", "LATERAL": "→"}
    l = tr.get("long",   {}).get("direction", "LATERAL")
    m = tr.get("medium", {}).get("direction", "LATERAL")
    s = tr.get("short",  {}).get("direction", "LATERAL")
    return (
        f'<span style="font-family:Space Mono;font-size:11px">'
        f'<span style="color:{_c[l]}">L{_a[l]}</span> '
        f'<span style="color:{_c[m]}">M{_a[m]}</span> '
        f'<span style="color:{_c[s]}">C{_a[s]}</span>'
        f'</span>'
    )


st.markdown(
    '<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA;margin-bottom:4px">Visão Geral</h2>',
    unsafe_allow_html=True,
)

col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    capital = st.session_state.get("capital", 10000)
    risk_pct = st.session_state.get("risk_pct", 0.02)
    selected_groups = st.session_state.get("selected_groups", [])
    grupos_ativos = selected_groups or list(GRUPOS.keys())
    tickers_visiveis = []
    for g in grupos_ativos:
        tickers_visiveis += GRUPOS.get(g, [])
    tickers_visiveis = list(dict.fromkeys(tickers_visiveis))
    if not tickers_visiveis:
        tickers_visiveis = list(ACOES.keys())

with col_f2:
    only_setups = st.checkbox("Só com setup", value=False)

with col_f3:
    sort_by = st.selectbox("Ordenar por", ["Confiança ↓", "Variação dia ↓", "Nome ↑"], label_visibility="collapsed")

with st.spinner("Carregando cotações..."):
    dados = get_precos_atuais(tuple(tickers_visiveis))

if not dados:
    st.error("Sem dados.")
    st.stop()

ibov = dados.get("^BVSP", {})
variacoes = {t: d["variacao_dia"] for t, d in dados.items() if d.get("variacao_dia") is not None}
ticker_alta  = max(variacoes, key=variacoes.get) if variacoes else None
ticker_baixa = min(variacoes, key=variacoes.get) if variacoes else None

m1, m2, m3, m4 = st.columns(4)
with m1:
    p = ibov.get("preco")
    v = ibov.get("variacao_dia")
    color = "#22C55E" if (v or 0) >= 0 else "#EF4444"
    st.markdown(
        f'<div class="coin-card"><div class="label">Ibovespa</div>'
        f'<div class="value mono">{f"{p:,.0f}" if p else "—"}</div>'
        f'<div class="sub" style="color:{color}">{fmt_pct(v)}</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    if ticker_alta:
        d = dados[ticker_alta]
        st.markdown(
            f'<div class="coin-card" style="border-left:3px solid #22C55E">'
            f'<div class="label">🚀 Maior Alta</div>'
            f'<div style="font-family:\'Space Mono\',monospace;font-size:0.9rem;font-weight:700">{d["nome"]}</div>'
            f'<div class="pos">{fmt_pct(variacoes[ticker_alta])}</div>'
            f'<div class="sub">{fmt_brl(d["preco"])}</div></div>',
            unsafe_allow_html=True,
        )
with m3:
    if ticker_baixa:
        d = dados[ticker_baixa]
        st.markdown(
            f'<div class="coin-card" style="border-left:3px solid #EF4444">'
            f'<div class="label">📉 Maior Queda</div>'
            f'<div style="font-family:\'Space Mono\',monospace;font-size:0.9rem;font-weight:700">{d["nome"]}</div>'
            f'<div class="neg">{fmt_pct(variacoes[ticker_baixa])}</div>'
            f'<div class="sub">{fmt_brl(d["preco"])}</div></div>',
            unsafe_allow_html=True,
        )
with m4:
    st.markdown(
        f'<div class="coin-card"><div class="label">Ativos carregados</div>'
        f'<div class="value mono">{len(dados)}</div>'
        f'<div class="sub">{len(tickers_visiveis)} selecionados</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

calc_setups = st.button("Calcular setups agora", help="Roda análise técnica completa para todos os ativos visíveis")

if "setups_cache" not in st.session_state:
    st.session_state["setups_cache"] = {}
if "trend_cache" not in st.session_state:
    st.session_state["trend_cache"] = {}

if calc_setups:
    prog = st.progress(0)
    tickers = list(dados.keys())
    for i, t in enumerate(tickers):
        df = get_historico(t, "3 meses")
        if df is not None and not df.empty:
            try:
                s = find_setup(df, t, capital, risk_pct)
                st.session_state["setups_cache"][t] = s
                tr = analyze_trend(df)
                st.session_state["trend_cache"][t] = tr
            except Exception:
                logger.warning("Erro ao calcular setup/tendência na visão geral: ticker=%s periodo=3 meses", t)
                st.session_state["setups_cache"][t] = None
        prog.progress((i + 1) / len(tickers))
    prog.empty()

setups = st.session_state["setups_cache"]
trends = st.session_state["trend_cache"]

rows = []
for t, d in dados.items():
    s    = setups.get(t)
    tr   = trends.get(t)
    conf = s["confidence"] if s else 0
    dir_ = s["direction"]  if s else None

    if only_setups and not s:
        continue

    rows.append({
        "_ticker": t,
        "Ticker":  t,
        "Nome":    d.get("nome", t),
        "Preço":   d.get("preco"),
        "Dia %":   d.get("variacao_dia"),
        "Sem %":   d.get("variacao_semana"),
        "Mês %":   d.get("variacao_mes"),
        "_setup":  s,
        "_trend":  tr,
        "_conf":   conf,
        "_dir":    dir_,
    })

if sort_by == "Confiança ↓":
    rows.sort(key=lambda x: -x["_conf"])
elif sort_by == "Variação dia ↓":
    rows.sort(key=lambda x: -(x["Dia %"] or -999))
else:
    rows.sort(key=lambda x: x["Nome"])

def pspan(v):
    if v is None:
        return "—"
    cls = "pos" if v >= 0 else "neg"
    return f'<span class="{cls}">{fmt_pct(v)}</span>'


def _ia_badge_html(ticker: str, ttl: int) -> str:
    c = get_cached(ticker, ttl=ttl)
    if not c:
        return '<span style="color:#3F3F46;font-size:10px">—</span>'
    score = c.get("macro_score", 0)
    label = c.get("macro_label", "NEUTRO")
    clr   = "#22C55E" if score > 20 else "#EF4444" if score < -20 else "#F59E0B"
    return (
        f'<span style="font-family:Space Mono;color:{clr};font-size:10px">'
        f'{score:+d} {label}</span>'
    )


_ttl_vg = get_ttl()

rows_html = ""
for r in rows:
    trend_html = _trend_compact(r["_trend"])
    setup_html = setup_semaphore_badge(r["_setup"], compact=True)
    ia_html    = _ia_badge_html(r["_ticker"], _ttl_vg)

    rows_html += f"""<tr style="border-bottom:1px solid #1F1F23">
        <td style="padding:7px 6px;font-family:'Space Mono',monospace;font-size:0.82rem"><a href="/grafico?ticker={r['_ticker']}" style="color:#2563EB;text-decoration:none">{r['Ticker']}</a></td>
        <td style="padding:7px 6px;font-size:0.82rem;color:#A1A1AA">{r['Nome']}</td>
        <td style="padding:7px 6px;font-family:'Space Mono',monospace;font-size:0.82rem">{fmt_brl(r['Preço'])}</td>
        <td style="padding:7px 6px">{pspan(r['Dia %'])}</td>
        <td style="padding:7px 6px">{pspan(r['Sem %'])}</td>
        <td style="padding:7px 6px">{pspan(r['Mês %'])}</td>
        <td style="padding:7px 6px">{trend_html}</td>
        <td style="padding:7px 6px">{setup_html}</td>
        <td style="padding:7px 6px">{ia_html}</td>
    </tr>"""

st.markdown(f"""
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse;font-size:0.82rem">
    <thead>
        <tr style="color:#71717A;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #27272A">
            <th style="text-align:left;padding:8px 6px">Ticker</th>
            <th style="text-align:left;padding:8px 6px">Nome</th>
            <th style="text-align:left;padding:8px 6px">Preço</th>
            <th style="text-align:left;padding:8px 6px">Dia</th>
            <th style="text-align:left;padding:8px 6px">Sem</th>
            <th style="text-align:left;padding:8px 6px">Mês</th>
            <th style="text-align:left;padding:8px 6px">Tendência</th>
            <th style="text-align:left;padding:8px 6px">Setup</th>
            <th style="text-align:left;padding:8px 6px">IA</th>
        </tr>
    </thead>
    <tbody>{rows_html}</tbody>
</table></div>""", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Tendência 30 dias")
tickers_sp = [t for t in dados if dados[t].get("sparkline") and t != "^BVSP"]
for i in range(0, len(tickers_sp), 5):
    cols = st.columns(5)
    for j, t in enumerate(tickers_sp[i:i+5]):
        sp = dados[t]["sparkline"]
        if len(sp) < 2:
            continue
        cor = "#22C55E" if sp[-1] >= sp[0] else "#EF4444"
        with cols[j]:
            st.markdown(
                f'<div style="font-family:\'Space Mono\',monospace;font-size:10px;color:{cor};text-align:center">{t}</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(sparkline(sp, height=70), width="stretch", config={"displayModeBar": False})
