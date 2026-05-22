from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

from b3analytics.config.assets import get_acoes, get_grupos
from b3analytics.domain.engine import calc_sizing, find_setup
from b3analytics.infrastructure.ai_analyst import get_or_analyze
from b3analytics.infrastructure.ai_config import (
    AI_PROVIDERS,
    get_active_provider,
    get_api_key,
    get_model,
    get_preset,
    is_local_agent_available,
)
from b3analytics.infrastructure.fetcher import fetch_all_parallel
from b3analytics.infrastructure.macro import get_macro_context
from b3analytics.presentation.components import render_ai_badge, render_setup_card
from b3analytics.presentation.setup_badges import (
    setup_educational_notice,
    setup_scan_prompt,
    setup_semaphore_legend,
)

ACOES  = get_acoes()
GRUPOS = get_grupos()
from b3analytics.config.settings import INDICATOR_DEFAULTS

logger = logging.getLogger(__name__)


def get_params() -> dict:
    return st.session_state.get("indicator_params", dict(INDICATOR_DEFAULTS))

## Setups Ativos

col1, col2, col3, col4 = st.columns([2, 2, 3, 2])
with col1:
    direcao = st.selectbox("Direção", options=["Todos", "LONG", "SHORT"], index=0)
with col2:
    tipo_label = st.selectbox(
        "Tipo de setup",
        options=["Todos", "Pullback", "Rompimento", "Reversão", "Cruzamento"],
        index=0,
    )
with col3:
    min_conf = st.slider("Confiança mínima", 0, 100, 40, step=5)
with col4:
    ordenar = st.selectbox(
        "Ordenar por",
        options=["Confiança ↓", "R/R ↓", "Ganho A1 ↓"],
        index=0,
    )

tipo_map = {
    "Todos":      None,
    "Pullback":   "PULLBACK",
    "Rompimento": "ROMPIMENTO",
    "Reversão":   "REVERSAO",
    "Cruzamento": "CRUZAMENTO",
}
tipo_filtro = tipo_map[tipo_label]

sidebar_capital = st.session_state.get("capital", 10000)
sidebar_risk    = st.session_state.get("risk_pct", 0.02)
selected_groups = st.session_state.get("selected_groups", [])

grupos_ativos = selected_groups or list(GRUPOS.keys())
tickers_scan  = []
for g in grupos_ativos:
    tickers_scan += GRUPOS.get(g, [])
tickers_scan = list(dict.fromkeys(tickers_scan)) or list(ACOES.keys())

PERIODO_MAP = {
    "15 dias":  "15d",
    "1 mês":    "1mo",
    "2 meses":  "2mo",
    "3 meses":  "3mo",
    "6 meses":  "6mo",
    "1 ano":    "1y",
    "2 anos":   "2y",
}
NOTAS_PERIODO = {
    "15 dias":  ("Swing curto",        "Setups de 1–5 dias.",                        "#F59E0B"),
    "1 mês":    ("Swing trade",        "Setups de 1–3 semanas.",                     "#84CC16"),
    "2 meses":  ("Swing/Position",     "Setups de 2–6 semanas.",                     "#84CC16"),
    "3 meses":  ("Position trade",     "Ponto de partida comum.",                    "#22C55E"),
    "6 meses":  ("Position/Tendência", "Análise de tendência primária.",              "#22C55E"),
    "1 ano":    ("Tendência primária", "Ajuda a avaliar viés de longo prazo.",       "#2563EB"),
    "2 anos":   ("Ciclo completo",     "Menos setups, maior confiabilidade.",        "#2563EB"),
}

st.markdown("---")
col5, col6, col7 = st.columns([2, 2, 3])
with col5:
    capital_op = st.number_input(
        "Capital por op. (R$)", min_value=100, max_value=500_000,
        value=int(st.session_state.get("capital_op", sidebar_capital)),
        step=100, format="%d",
    )
    st.session_state["capital_op"] = capital_op
with col6:
    risco_pct_pct = st.slider(
        "Risco (%)", 0.5, 5.0,
        float(st.session_state.get("risco_pct_pct", sidebar_risk * 100)),
        step=0.5, format="%.1f%%",
    )
    risk_pct = risco_pct_pct / 100
    st.session_state["risco_pct"]     = risk_pct
    st.session_state["risco_pct_pct"] = risco_pct_pct
with col7:
    periodo_label = st.selectbox(
        "Período de análise",
        options=list(PERIODO_MAP.keys()),
        index=3,
    )
    periodo_str = PERIODO_MAP[periodo_label]
    nl, nd, nc  = NOTAS_PERIODO[periodo_label]
    st.markdown(
        f"<span style='color:{nc};font-size:11px;font-family:Space Mono'>● {nl}</span>"
        f"<span style='color:#71717A;font-size:11px'> — {nd}</span>",
        unsafe_allow_html=True,
    )

st.markdown('<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA">Setups Ativos</h2>', unsafe_allow_html=True)

st.caption(setup_semaphore_legend())

run_btn = st.button("⟳  Escanear todos os ativos", width="stretch", type="primary")

if run_btn:
    with st.spinner(f"Buscando dados de {len(tickers_scan)} ativos em paralelo..."):
        dfs = fetch_all_parallel(tickers_scan, periodo=periodo_str, max_workers=10)

    prog   = st.progress(0)
    status = st.empty()
    total  = max(len(dfs), 1)
    found  = 0
    done   = 0

    st.session_state["all_setups"]      = {}
    st.session_state["scan_tickers_n"]  = len(tickers_scan)
    st.session_state.pop("ia_batch_results", None)

    with ThreadPoolExecutor(max_workers=8) as executor:
        _params = get_params()
        futures = {
            executor.submit(find_setup, df, t, capital_op, risk_pct, params=_params): t
            for t, df in dfs.items()
        }
        for future in as_completed(futures):
            t = futures[future]
            try:
                s = future.result()
                if s:
                    st.session_state["all_setups"][t] = s
                    found += 1
            except Exception:
                logger.warning("Erro ao calcular setup durante scan: ticker=%s periodo=%s", t, periodo_label)
            done += 1
            prog.progress(done / total)
            status.caption(f"Analisados: {done}/{total} — setups encontrados: {found}")

    prog.empty()
    status.empty()

elif "all_setups" not in st.session_state:
    st.info(f"{setup_scan_prompt()} Clique em **⟳ Escanear todos os ativos**.")
    st.stop()

all_setups: dict = st.session_state.get("all_setups", {})

if all_setups:
    for s in all_setups.values():
        new_sz = calc_sizing(s["entry"]["price"], s["stop"]["price"], capital_op, risk_pct)
        if new_sz:
            s["sizing"] = new_sz

filtered = {
    t: s for t, s in all_setups.items()
    if s["confidence"] >= min_conf
    and (direcao == "Todos" or s["direction"] == direcao)
    and (tipo_filtro is None or s["type"] == tipo_filtro)
}

if not filtered:
    st.info(f"Nenhum setup encontrado com os filtros atuais ({len(all_setups)} escaneados).")
    st.stop()

items = list(filtered.values())
if ordenar == "Confiança ↓":
    items.sort(key=lambda x: -x["confidence"])
elif ordenar == "R/R ↓":
    items.sort(key=lambda x: -(x["targets"][0]["rr"] if x["targets"] else 0))
elif ordenar == "Ganho A1 ↓":
    items.sort(key=lambda x: -(
        (x["targets"][0]["price"] - x["entry"]["price"]) * x["sizing"]["quantity"]
        if x["targets"] else 0
    ))

n_long   = sum(1 for s in items if s["direction"] == "LONG")
n_short  = sum(1 for s in items if s["direction"] == "SHORT")
avg_rr   = sum(s["targets"][0]["rr"] for s in items if s["targets"]) / max(len(items), 1)
avg_conf = sum(s["confidence"] for s in items) / max(len(items), 1)
n_scan   = st.session_state.get("scan_tickers_n", len(tickers_scan))

st.markdown(f"""
<div class="stat-bar">
  <div class="stat-item">
    <span class="stat-label">Total Setups</span>
    <span class="stat-value blue">{len(items)}</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Long</span>
    <span class="stat-value green">{n_long}</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Short</span>
    <span class="stat-value red">{n_short}</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">R/R Médio (A1)</span>
    <span class="stat-value">{avg_rr:.2f}x</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Confiança Média</span>
    <span class="stat-value">{avg_conf:.0f}/100</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Capital/op</span>
    <span class="stat-value">R${capital_op:,.0f}</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Ativos Escaneados</span>
    <span class="stat-value">{n_scan}</span>
  </div>
</div>
""", unsafe_allow_html=True)

n_total_cache = len(all_setups)
st.caption(f"{len(items)} setups exibidos · {n_total_cache} encontrados no último scan")

st.divider()
st.caption(setup_educational_notice())

_ia_provider   = get_active_provider()
_ia_key        = get_api_key(_ia_provider)
_ia_req_key    = AI_PROVIDERS[_ia_provider]["requires_key"]
_ia_configured = (_ia_req_key and bool(_ia_key)) or (not _ia_req_key and is_local_agent_available())

# ── Batch IA ──────────────────────────────────────────────────────────────────
if _ia_configured:
    col_batch, _ = st.columns([3, 5])
    with col_batch:
        analisar_todos = st.button(
            f"🧠 Analisar todos os {len(items)} setups com IA",
            help="Análise macro em paralelo (máx 3 chamadas simultâneas).",
        )

    if analisar_todos:
        _model  = get_model(_ia_provider)
        _preset = get_preset(_ia_provider)
        _params = get_params()

        prog_b = st.progress(0, "Coletando macro...")
        macro  = get_macro_context()
        total  = len(items)
        resultados_ia: dict = {}

        prog_b.progress(10, f"Analisando {total} setups com IA...")
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {
                ex.submit(
                    get_or_analyze,
                    s["ticker"],
                    ACOES.get(s["ticker"], s["ticker"]),
                    next((g for g, ts in GRUPOS.items() if s["ticker"] in ts), "Geral"),
                    s,
                    _ia_key,
                    _model,
                    macro,
                    _preset,
                ): s["ticker"]
                for s in items
            }
            done = 0
            for future in as_completed(futures):
                t_f  = futures[future]
                done += 1
                pct  = 10 + int(done / total * 90)
                prog_b.progress(pct, f"Analisado {t_f} ({done}/{total})...")
                try:
                    resultados_ia[t_f] = future.result()
                except Exception as e:
                    logger.warning("Erro ao analisar setup com IA em lote: ticker=%s", t_f)
                    resultados_ia[t_f] = {"erro": str(e)}

        prog_b.empty()
        st.session_state["ia_batch_results"] = resultados_ia
        st.success(f"✅ {len(resultados_ia)} análises concluídas.")
        st.rerun()

_batch_results = st.session_state.get("ia_batch_results", {})

for i in range(0, len(items), 2):
    cols = st.columns(2)
    for j in range(2):
        if i + j < len(items):
            with cols[j]:
                render_setup_card(items[i + j])
                t = items[i + j]["ticker"]

                render_ai_badge(
                    t,
                    ACOES.get(t, t),
                    next((g for g, ts in GRUPOS.items() if t in ts), "Geral"),
                    items[i + j],
                    compact=True,
                )

                if _ia_configured:
                    if st.button("🧠 Analisar com IA", key=f"ia_{t}",
                                 width="stretch"):
                        st.session_state["ia_ticker"] = t
                        st.switch_page("pages/ia.py")
                else:
                    st.caption("[🧠 Configure a IA para análise macro →](pages/ia.py)")
