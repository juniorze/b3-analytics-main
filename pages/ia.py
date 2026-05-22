from __future__ import annotations

import html
import logging
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from b3analytics.config.assets import get_acoes, get_grupos
from b3analytics.domain.engine import find_setup
from b3analytics.infrastructure.ai_analyst import analyze, test_local_agent_connection
from b3analytics.infrastructure.ai_cache import (
    cache_stats,
    get_cached,
    invalidate_all,
    list_cached,
    save_cache,
)
from b3analytics.infrastructure.ai_config import (
    AI_PRESETS,
    AI_PROVIDERS,
    TTL_OPTIONS,
    delete_api_key,
    fetch_available_models,
    get_active_provider,
    get_all_sources,
    get_api_key,
    get_config_path,
    get_local_agent_info,
    get_model,
    get_model_options,
    get_preset,
    get_sources_enabled,
    get_ttl,
    get_ttl_label,
    is_configured,
    is_local_agent_available,
    save_active_provider,
    save_api_key,
    save_model,
    save_preset,
    save_sources,
    save_sources_enabled,
    save_ttl,
    test_api_key,
)
from b3analytics.infrastructure.fetcher import _fetch_one
from b3analytics.infrastructure.macro import get_macro_context

ACOES  = get_acoes()
GRUPOS = get_grupos()
import time as _time

from b3analytics.config.settings import INDICATOR_DEFAULTS

logger = logging.getLogger(__name__)


# ── Helpers de renderização ────────────────────────────────────────────────────

def _rec_label(key: str | None, mean: float | None) -> tuple:
    """Retorna (label_pt, cor) para recomendação de analistas."""
    if key:
        k = key.lower().replace(" ", "_")
        mapping = {
            "strong_buy":   ("Compra Forte",   "#22C55E"),
            "buy":          ("Compra",          "#84CC16"),
            "hold":         ("Neutro/Hold",     "#F59E0B"),
            "underperform": ("Abaixo Mercado",  "#EF4444"),
            "sell":         ("Venda",           "#EF4444"),
            "strong_sell":  ("Venda Forte",     "#DC2626"),
        }
        return mapping.get(k, (key.title(), "#71717A"))
    if mean is not None:
        if mean <= 1.5: return ("Compra Forte",   "#22C55E")
        if mean <= 2.5: return ("Compra",          "#84CC16")
        if mean <= 3.5: return ("Neutro/Hold",     "#F59E0B")
        if mean <= 4.5: return ("Abaixo Mercado",  "#EF4444")
        return ("Venda Forte", "#DC2626")
    return ("—", "#71717A")


def _render_analyst_yf(analyst_data: dict) -> None:
    """Renderiza painel de dados de analistas do yfinance."""
    rec_key  = analyst_data.get("recommendation_key")
    rec_mean = analyst_data.get("recommendation_mean")
    n        = analyst_data.get("n_analysts")
    tgt_mean = analyst_data.get("target_mean")
    tgt_high = analyst_data.get("target_high")
    tgt_low  = analyst_data.get("target_low")
    earn     = analyst_data.get("earnings_date")
    ex_div   = analyst_data.get("ex_dividend_date")
    div_rate = analyst_data.get("dividend_rate")
    div_hist = analyst_data.get("dividend_history", [])
    actions  = analyst_data.get("recent_actions", [])

    has_data = any([rec_key, rec_mean, tgt_mean, earn, ex_div, div_rate, actions])
    if not has_data:
        return

    st.markdown("#### 📊 Dados de Analistas (yfinance)")
    col1, col2, col3 = st.columns(3)

    with col1:
        label, cor = _rec_label(rec_key, rec_mean)
        n_str    = f" · {n} analistas" if n else ""
        mean_str = f"Média: {rec_mean:.1f}/5.0" if rec_mean else ""
        st.markdown(
            f"<div style='background:#18181B;border:1px solid #27272A;border-radius:8px;"
            f"padding:14px;text-align:center'>"
            f"<div style='color:#A1A1AA;font-size:10px;text-transform:uppercase;"
            f"letter-spacing:.08em;margin-bottom:6px'>Recomendação</div>"
            f"<div style='font-family:Space Mono;font-size:1.3rem;font-weight:700;"
            f"color:{cor}'>{label}</div>"
            f"<div style='color:#71717A;font-size:11px;margin-top:4px'>"
            f"{mean_str}{n_str}</div></div>",
            unsafe_allow_html=True,
        )

    with col2:
        if tgt_mean:
            tgt_range = f"R$ {tgt_low:.2f} — R$ {tgt_high:.2f}" if tgt_low and tgt_high else ""
            st.markdown(
                f"<div style='background:#18181B;border:1px solid #27272A;border-radius:8px;"
                f"padding:14px;text-align:center'>"
                f"<div style='color:#A1A1AA;font-size:10px;text-transform:uppercase;"
                f"letter-spacing:.08em;margin-bottom:6px'>Preço-alvo médio</div>"
                f"<div style='font-family:Space Mono;font-size:1.3rem;font-weight:700;"
                f"color:#2563EB'>R$ {tgt_mean:.2f}</div>"
                f"<div style='color:#71717A;font-size:11px;margin-top:4px'>{tgt_range}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='background:#18181B;border:1px solid #27272A;border-radius:8px;"
                "padding:14px;text-align:center'>"
                "<div style='color:#3F3F46;font-size:12px'>Preço-alvo<br>não disponível</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    with col3:
        eventos = []
        if earn:    eventos.append(f"📅 Resultado: **{earn}**")
        if ex_div:  eventos.append(f"💰 Ex-dividendo: **{ex_div}**")
        if div_rate: eventos.append(f"R$ {div_rate:.4f}/ação/ano")
        content = "<br>".join(eventos) if eventos else "Nenhum evento próximo"
        st.markdown(
            f"<div style='background:#18181B;border:1px solid #27272A;border-radius:8px;"
            f"padding:14px'>"
            f"<div style='color:#A1A1AA;font-size:10px;text-transform:uppercase;"
            f"letter-spacing:.08em;margin-bottom:8px'>Próximos Eventos</div>"
            f"<div style='color:#FAFAFA;font-size:12px;line-height:1.8'>{content}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if div_hist:
        with st.expander(f"📈 Histórico de dividendos ({len(div_hist)} últimos pagamentos)"):
            cols = st.columns(min(len(div_hist), 4))
            for i, d in enumerate(div_hist[-4:]):
                with cols[i % 4]:
                    st.metric(d.get("date", ""), f"R$ {d.get('value', 0):.4f}")

    if actions:
        with st.expander(f"🏦 Ações recentes de analistas ({len(actions)})"):
            for a in actions:
                action_type = a.get("action", "").lower()
                cor = "#22C55E" if "up" in action_type else "#EF4444" if "down" in action_type else "#71717A"
                st.markdown(
                    f"<div style='display:flex;gap:12px;padding:5px 0;"
                    f"border-bottom:1px solid #1F1F23;align-items:center'>"
                    f"<span style='color:#71717A;font-size:10px;min-width:80px'>{a.get('date','')}</span>"
                    f"<span style='color:#FAFAFA;font-size:12px;min-width:120px'>{html.escape(a.get('firm',''))}</span>"
                    f"<span style='color:{cor};font-family:Space Mono;font-size:11px'>"
                    f"{html.escape(a.get('from_grade',''))} → {html.escape(a.get('to_grade',''))}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


def _render_expandable_card(item: dict, tone: str, key: str) -> None:
    """Card de catalisador/risco que expande ao clicar."""
    imp     = item.get("impacto", "BAIXO")
    fator   = item.get("fator", "")
    fonte   = item.get("fonte", "")
    detalhe = item.get("detalhe", "")
    links   = [l for l in item.get("links", []) if l and l.startswith("http")]

    colors_g = {"ALTO": "#22C55E", "MÉDIO": "#84CC16", "BAIXO": "#71717A"}
    colors_r = {"ALTO": "#EF4444", "MÉDIO": "#F59E0B", "BAIXO": "#71717A"}
    border_g = "rgba(34,197,94,0.2)"
    border_r = "rgba(239,68,68,0.2)"

    color  = (colors_g if tone == "green" else colors_r).get(imp, "#71717A")
    border = border_g if tone == "green" else border_r

    label = f"{'↑' if tone == 'green' else '↓'} {fator}"

    with st.expander(label, expanded=False):
        fonte_html = f"📰 {html.escape(fonte)}" if fonte else ""
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
            f"<span style='background:{border};color:{color};font-size:10px;"
            f"font-family:Space Mono;padding:2px 8px;border-radius:3px'>"
            f"● {html.escape(imp)}</span>"
            f"<span style='color:#71717A;font-size:11px;font-family:Space Mono'>{fonte_html}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if detalhe:
            st.markdown(
                f"<p style='color:#A1A1AA;font-size:13px;line-height:1.6'>{html.escape(detalhe)}</p>",
                unsafe_allow_html=True,
            )
        if links:
            st.markdown("**Referências:**")
            for link in links:
                st.markdown(f"- [{link}]({link})")


def _render_news_item(n: dict) -> None:
    sent   = n.get("sentimento", "NEUTRO")
    titulo = n.get("titulo", "") or "Sem título"
    fonte  = n.get("fonte", "")
    url    = n.get("url", "")
    resumo = n.get("resumo", "")
    color  = {"POSITIVO": "#22C55E", "NEGATIVO": "#EF4444", "NEUTRO": "#71717A"}.get(sent, "#71717A")
    safe_url = url if (url and url.startswith("http")) else ""

    sent_badge = (
        f"<span style='color:{color};font-family:Space Mono;"
        f"font-size:10px;min-width:65px'>{sent}</span>"
    )
    fonte_html = (
        f"<span style='color:#3F3F46;font-size:10px;font-family:Space Mono'>"
        f"📰 {html.escape(fonte)}</span>"
        if fonte else ""
    )

    with st.expander(titulo, expanded=False):
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
            f"{sent_badge}{fonte_html}</div>",
            unsafe_allow_html=True,
        )
        if resumo:
            st.markdown(
                f"<p style='color:#A1A1AA;font-size:13px;line-height:1.6'>"
                f"{html.escape(resumo)}</p>",
                unsafe_allow_html=True,
            )
        if safe_url:
            st.markdown(f"[🔗 Acessar fonte ↗]({safe_url})")


def _render_analysis(ticker: str, nome: str, resultado: dict, setup) -> None:
    """Renderização completa do resultado de IA."""
    import datetime as _dt

    st.session_state[f"ia_result_{ticker}"] = resultado
    st.session_state[f"ia_setup_{ticker}"]  = setup

    # ── Cotação atual ────────────────────────────────────────────────────────
    try:
        from b3analytics.infrastructure.fetcher import get_historico
        from b3analytics.presentation.components import fmt_brl, fmt_pct
        _df_p = get_historico(ticker, "1mo")
        if _df_p is not None and not _df_p.empty:
            _cc_p = next((c for c in ["close", "Close"] if c in _df_p.columns), None)
            if _cc_p:
                _prices = _df_p[_cc_p].dropna()
                if len(_prices) >= 2:
                    _p_atual = float(_prices.iloc[-1])
                    _p_ant   = float(_prices.iloc[-2])
                    _var_dia = (_p_atual - _p_ant) / _p_ant * 100 if _p_ant else 0.0
                    _p_min   = float(_prices.min())
                    _p_max   = float(_prices.max())
                    _cp1, _cp2, _cp3, _cp4 = st.columns(4)
                    _cp1.metric("Preço Atual", fmt_brl(_p_atual), fmt_pct(_var_dia))
                    _cp2.metric("Mín. 1 mês",  fmt_brl(_p_min))
                    _cp3.metric("Máx. 1 mês",  fmt_brl(_p_max))
                    _cp4.metric("Var. Dia",     fmt_pct(_var_dia))
    except Exception:
        logger.warning("Falha ao renderizar cotação resumida na página IA: ticker=%s", ticker)
        pass
    # ── Fim cotação ──────────────────────────────────────────────────────────

    score = resultado.get("macro_score", 0)
    label = resultado.get("macro_label", "NEUTRO")
    align = resultado.get("setup_alinhamento", "SEM_SETUP")
    prov  = resultado.get("_provider", "")

    score_color = "#22C55E" if score > 20 else "#EF4444" if score < -20 else "#F59E0B"
    align_color = {
        "ALINHADO": "#22C55E", "CONFLITO": "#EF4444",
        "NEUTRO": "#F59E0B", "SEM_SETUP": "#71717A",
    }.get(align, "#71717A")
    prov_badge = "💻 Motor IA Local" if prov == "claude_code" else "☁️ API Remota"

    st.markdown(
        f"<div style='background:#18181B;border:1px solid #27272A;border-radius:8px;"
        f"padding:12px 16px;margin:8px 0;display:flex;justify-content:space-between;"
        f"align-items:center;flex-wrap:wrap;gap:12px'>"
        f"<div style='display:flex;align-items:center;gap:10px'>"
        f"<span style='font-family:IBM Plex Mono;font-size:1rem;font-weight:700;"
        f"color:#FAFAFA'>{ticker}</span>"
        f"<span style='color:#71717A;font-size:12px'>{nome}</span>"
        f"<span style='color:#3F3F46;font-size:10px'>{prov_badge}</span>"
        f"</div>"
        f"<div style='display:flex;gap:16px;align-items:center'>"
        f"<div style='text-align:center'>"
        f"<div style='color:#A1A1AA;font-size:9px;text-transform:uppercase;letter-spacing:.08em'>Score</div>"
        f"<div style='font-family:IBM Plex Mono;font-size:1.4rem;font-weight:700;color:{score_color}'>{score:+d}</div>"
        f"</div>"
        f"<div style='text-align:center'>"
        f"<div style='color:#A1A1AA;font-size:9px;text-transform:uppercase;letter-spacing:.08em'>Contexto</div>"
        f"<div style='font-family:IBM Plex Mono;font-size:0.95rem;font-weight:700;color:{score_color}'>{html.escape(label)}</div>"
        f"</div>"
        f"<div style='text-align:center'>"
        f"<div style='color:#A1A1AA;font-size:9px;text-transform:uppercase;letter-spacing:.08em'>vs Setup</div>"
        f"<div style='font-family:IBM Plex Mono;font-size:0.95rem;font-weight:700;color:{align_color}'>{html.escape(align)}</div>"
        f"</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if resultado.get("alinhamento_explicacao"):
        st.markdown(
            f"<div style='color:#71717A;font-size:11px;margin:4px 0 8px 0'>"
            f"{html.escape(resultado['alinhamento_explicacao'])}</div>",
            unsafe_allow_html=True,
        )

    # Contextual nav
    _cn1, _cn2, _ = st.columns([1, 1, 6])
    with _cn1:
        if st.button("📈 Gráfico", key=f"nav_graf_{ticker}", width="stretch"):
            st.query_params["ticker"] = ticker
            st.switch_page("pages/grafico.py")
    with _cn2:
        if st.button("🎯 Setups", key=f"nav_set_{ticker}", width="stretch"):
            st.switch_page("pages/setups.py")

    # Dados de analistas yfinance
    analyst_yf = resultado.get("_analyst_yf", {})
    if analyst_yf:
        _render_analyst_yf(analyst_yf)

    # Catalisadores e Riscos (expansíveis)
    col_c, col_r = st.columns(2)
    with col_c:
        st.markdown("#### ↑ Catalisadores")
        for i, item in enumerate(resultado.get("catalistas", [])):
            _render_expandable_card(item, "green", f"cat_{ticker}_{i}")
    with col_r:
        st.markdown("#### ↓ Riscos")
        for i, item in enumerate(resultado.get("riscos", [])):
            _render_expandable_card(item, "red", f"risk_{ticker}_{i}")

    # Consenso de analistas (IA)
    consenso = resultado.get("consenso_analistas", {})
    if consenso and consenso.get("visao_geral"):
        st.markdown("#### 🏦 Consenso de Analistas")
        st.markdown(
            f"<div style='background:#18181B;border:1px solid #27272A;"
            f"border-radius:8px;padding:16px 20px'>"
            f"<p style='color:#A1A1AA;font-size:14px;margin:0'>"
            f"{html.escape(consenso.get('visao_geral', ''))}</p></div>",
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            fav = consenso.get("casas_favoraveis", [])
            if fav:
                st.markdown(
                    f"<span style='color:#22C55E;font-size:12px'>✅ Favoráveis: </span>"
                    f"<span style='color:#A1A1AA;font-size:12px'>{html.escape(', '.join(fav))}</span>",
                    unsafe_allow_html=True,
                )
        with col2:
            con = consenso.get("casas_contrarias", [])
            if con:
                st.markdown(
                    f"<span style='color:#EF4444;font-size:12px'>❌ Contrárias: </span>"
                    f"<span style='color:#A1A1AA;font-size:12px'>{html.escape(', '.join(con))}</span>",
                    unsafe_allow_html=True,
                )
        preco_ia = consenso.get("preco_alvo_estimado")
        if preco_ia:
            st.markdown(
                f"<span style='color:#2563EB;font-family:Space Mono;font-size:13px'>"
                f"🎯 Preço-alvo estimado: R$ {preco_ia:.2f}</span>",
                unsafe_allow_html=True,
            )
        persp = consenso.get("perspectiva_ano", "")
        if persp:
            st.info(persp, icon="📅")

    # Perspectiva longo prazo
    lp = resultado.get("perspectiva_longo_prazo", "")
    if lp:
        st.markdown("#### 🔭 Perspectiva de Longo Prazo")
        st.markdown(
            f"<div style='background:#18181B;border:1px solid #27272A;"
            f"border-left:3px solid #2563EB;border-radius:8px;"
            f"padding:14px 18px;color:#A1A1AA;font-size:14px'>{html.escape(lp)}</div>",
            unsafe_allow_html=True,
        )

    # Próximos dividendos e resultados (IA)
    col_div, col_earn = st.columns(2)
    with col_div:
        div_ia = resultado.get("proximos_dividendos", {})
        if div_ia and div_ia.get("previsao"):
            st.markdown("#### 💰 Dividendos")
            st.markdown(
                f"<div style='background:#18181B;border:1px solid rgba(34,197,94,0.2);"
                f"border-radius:8px;padding:12px 16px'>"
                f"<div style='color:#22C55E;font-size:13px'>{html.escape(div_ia.get('previsao', ''))}</div>"
                f"<div style='color:#3F3F46;font-size:11px;margin-top:4px'>"
                f"{html.escape(div_ia.get('base', ''))}</div></div>",
                unsafe_allow_html=True,
            )
    with col_earn:
        earn_ia = resultado.get("proximos_resultados", {})
        if earn_ia and earn_ia.get("data_estimada"):
            st.markdown("#### 📋 Próximo Resultado")
            st.markdown(
                f"<div style='background:#18181B;border:1px solid rgba(37,99,235,0.2);"
                f"border-radius:8px;padding:12px 16px'>"
                f"<div style='color:#2563EB;font-family:Space Mono;font-size:13px'>"
                f"📅 {html.escape(earn_ia.get('data_estimada', ''))}</div>"
                f"<div style='color:#A1A1AA;font-size:12px;margin-top:4px'>"
                f"{html.escape(earn_ia.get('expectativa', ''))}</div>"
                f"<div style='color:#3F3F46;font-size:11px;margin-top:3px'>"
                f"{html.escape(earn_ia.get('fonte', ''))}</div></div>",
                unsafe_allow_html=True,
            )

    # Ativos correlacionados
    correlacoes = resultado.get("ativos_correlacionados", [])
    if correlacoes:
        st.markdown("#### 🔗 Ativos Correlacionados")
        cols = st.columns(min(len(correlacoes), 3))
        for i, corr in enumerate(correlacoes[:3]):
            tipo = corr.get("correlacao_tipo", "NEUTRA")
            cor  = "#22C55E" if tipo == "POSITIVA" else "#EF4444" if tipo == "NEGATIVA" else "#71717A"
            icon = "↑↑" if tipo == "POSITIVA" else "↑↓" if tipo == "NEGATIVA" else "→"
            corr_ticker = corr.get("ticker", "")
            with cols[i]:
                st.markdown(
                    f"<div style='background:#18181B;border:1px solid #27272A;"
                    f"border-radius:8px;padding:12px 14px'>"
                    f"<div style='font-family:Space Mono;font-weight:700;color:#FAFAFA'>"
                    f"{html.escape(corr_ticker)}</div>"
                    f"<div style='color:{cor};font-size:11px;margin:3px 0'>{icon} {tipo}</div>"
                    f"<div style='color:#71717A;font-size:11px'>{html.escape(corr.get('relacao', ''))}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if corr_ticker and corr_ticker in ACOES:
                    _bc1, _bc2 = st.columns(2)
                    with _bc1:
                        if st.button("📈 Gráfico", key=f"corr_graf_{ticker}_{i}", width="stretch"):
                            st.query_params["ticker"] = corr_ticker
                            st.switch_page("pages/grafico.py")
                    with _bc2:
                        if st.button("🧠 IA", key=f"corr_ia_{ticker}_{i}", width="stretch"):
                            st.session_state["ia_ticker"] = corr_ticker
                            st.rerun()

    # Notícias
    noticias = resultado.get("noticias", [])
    if noticias:
        st.markdown("#### 📰 Notícias")
        for n in noticias:
            _render_news_item(n)

    # Pareceres
    st.divider()
    col_pm, col_pi = st.columns(2)
    with col_pm:
        st.markdown("**Parecer macro**")
        st.info(resultado.get("parecer_macro", "—"))
    with col_pi:
        st.markdown("**Parecer integrado**")
        parecer = resultado.get("parecer_integrado", "—")
        if score > 20:     st.success(parecer)
        elif score < -20:  st.error(parecer)
        else:              st.warning(parecer)

    # Rodapé de fontes
    _fontes = sorted({
        f for f in (
            [i.get("fonte", "") for i in resultado.get("catalistas", [])]
            + [i.get("fonte", "") for i in resultado.get("riscos", [])]
            + [n.get("fonte", "") for n in resultado.get("noticias", [])]
            + [resultado.get("consenso_analistas", {}).get("fonte", "")]
        ) if f
    })
    if _fontes:
        st.markdown(
            f"<div style='background:#09090B;border:1px solid #27272A;"
            f"border-radius:6px;padding:8px 14px;margin-top:8px'>"
            f"<span style='color:#3F3F46;font-size:10px'>📰 Fontes: </span>"
            f"<span style='color:#71717A;font-size:10px;font-family:Space Mono'>"
            f"{html.escape(' · '.join(_fontes))}</span></div>",
            unsafe_allow_html=True,
        )

    cached_at = resultado.get("cached_at", _time.time())
    data_str  = _dt.datetime.fromtimestamp(cached_at).strftime("%d/%m/%Y %H:%M")
    st.caption(
        f"Gerado em {data_str} via {prov_badge}. "
        "Dados públicos — não constitui recomendação de investimento."
    )
    with st.expander("Ver JSON completo"):
        st.json(resultado)


# ── Pré-carregar modelos (antes das tabs, para ambas poderem usar) ─────────────
_provider_page  = get_active_provider()
_api_key_global = get_api_key(_provider_page)
_models_raw     = (
    fetch_available_models(_api_key_global, _provider_page)
    if _api_key_global else []
)
_model_options  = get_model_options(_models_raw, _provider_page)

## Inteligência Artificial

st.title("🧠 Inteligência Artificial")

tab_config, tab_analise = st.tabs(["⚙️ Configuração", "🔍 Análise"])

# ── TAB 1 — CONFIGURAÇÃO ──────────────────────────────────────────────────────
with tab_config:
    _cc_available = is_local_agent_available()
    _provider_cur = get_active_provider()

    # Auto-selecionar motor local se disponível e não há chave de API configurada.
    if _cc_available and _provider_cur == "anthropic_api" and not get_api_key(_provider_cur):
        save_active_provider("claude_code")
        _provider_cur = "claude_code"

    @st.cache_data(ttl=300, show_spinner=False)
    def _cc_info_cached():
        return get_local_agent_info()

    def _prov_label(k: str) -> str:
        return AI_PROVIDERS.get(k, {}).get("label", k)

    # ── Compact 3-column row: Provider | Preset | Status ──────────────────────
    def _handle_provider_change() -> None:
        selected = st.session_state.get("prov_selectbox")
        if selected in AI_PROVIDERS:
            save_active_provider(selected)
            st.session_state["_prov_selectbox_saved"] = selected
            st.session_state.pop("modelo_sel_exp", None)
            st.cache_data.clear()

    saved_provider_state = st.session_state.get("_prov_selectbox_saved")
    widget_provider_state = st.session_state.get("prov_selectbox")
    if widget_provider_state not in AI_PROVIDERS or saved_provider_state != _provider_cur:
        st.session_state["prov_selectbox"] = _provider_cur
        st.session_state["_prov_selectbox_saved"] = _provider_cur

    col_prov, col_preset, col_status = st.columns([2, 2, 3])
    with col_prov:
        prov_options = list(AI_PROVIDERS.keys())
        prov_sel = st.selectbox(
            "Provider",
            options=prov_options,
            format_func=_prov_label,
            key="prov_selectbox",
            on_change=_handle_provider_change,
        )
        if prov_sel != _provider_cur:
            _handle_provider_change()
            st.rerun()

    with col_preset:
        preset_options = list(AI_PRESETS.keys())
        preset_cur_c   = get_preset(_provider_cur)
        preset_idx_c   = preset_options.index(preset_cur_c) if preset_cur_c in preset_options else 1
        preset_sel_c = st.selectbox(
            "Nível",
            options=preset_options,
            format_func=lambda k: f"{AI_PRESETS[k]['icon']} {AI_PRESETS[k]['label']}",
            index=preset_idx_c,
            key=f"preset_sel_c_{_provider_cur}",
        )
        if preset_sel_c != preset_cur_c:
            save_preset(preset_sel_c, _provider_cur)
            st.rerun()

    with col_status:
        _p_color = "#22C55E" if _provider_cur == "claude_code" else "#2563EB"
        if _provider_cur == "claude_code":
            _ok_s   = _cc_available
            _stat_s = "✓ Detectado" if _ok_s else "⚠ Não encontrado"
        else:
            _ok_s   = is_configured(_provider_cur)
            _stat_s = "✓ Configurado" if _ok_s else "⚠ Sem chave"
        _stat_color = "#22C55E" if _ok_s else "#EF4444"
        st.markdown(
            f"<div style='padding-top:4px'>"
            f"<span style='color:{_p_color};font-size:11px;font-family:IBM Plex Mono,monospace'>"
            f"● Provider ativo: {_prov_label(_provider_cur)}</span>"
            f"<br><span style='color:{_stat_color};font-size:11px'>{_stat_s}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Preset config info
    cfg_preset = AI_PRESETS[preset_sel_c]
    st.markdown(
        f"<div style='background:#09090B;border:1px solid #27272A;border-radius:5px;"
        f"padding:6px 12px;margin:6px 0;display:flex;gap:20px'>"
        f"<span style='color:#71717A;font-size:11px'>Buscas: "
        f"<span style='font-family:IBM Plex Mono;color:#FAFAFA'>máx {cfg_preset['max_uses']}</span></span>"
        f"<span style='color:#71717A;font-size:11px'>Tokens: "
        f"<span style='font-family:IBM Plex Mono;color:#FAFAFA'>até {cfg_preset['max_tokens']:,}</span></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Provider-specific configuration ──────────────────────────────────────
    if AI_PROVIDERS[_provider_cur]["requires_key"]:
        # ── API Key expander ───────────────────────────────────────────────────
        configured = is_configured(_provider_cur)
        env_var = AI_PROVIDERS[_provider_cur].get("env_var", "API_KEY")
        with st.expander("🔑 API Key", expanded=not configured):
            st.caption(f"Use `{env_var}` ou salve em `{get_config_path()}` — nunca commitada.")
            cor = "#22C55E" if configured else "#EF4444"
            st.markdown(
                f"<span style='color:{cor};font-family:IBM Plex Mono;font-size:11px'>"
                f"{'✓ Configurado' if configured else '✗ Não configurado'}</span>",
                unsafe_allow_html=True,
            )
            with st.form("form_key"):
                nova_key = st.text_input(
                    "API Key",
                    type="password",
                    placeholder=env_var,
                    value="••••••••" if configured else "",
                )
                c1, c2, c3 = st.columns([2, 2, 2])
                salvar  = c1.form_submit_button("💾 Salvar",  width="stretch", type="primary")
                deletar = c2.form_submit_button("🗑️ Remover", width="stretch")
                testar  = c3.form_submit_button("🧪 Testar",  width="stretch")

            if salvar:
                key = nova_key.strip()
                if (
                    _provider_cur == "anthropic_api"
                    and key
                    and key != "••••••••"
                    and not key.startswith("sk-ant")
                ):
                    st.error("Chave Anthropic inválida — deve começar com `sk-ant`.")
                elif key and key != "••••••••" and len(key) > 10:
                    save_api_key(key, _provider_cur)
                    st.cache_data.clear()
                    st.success("✅ Chave salva.")
                    st.rerun()
                elif key == "••••••••":
                    st.info("Chave não alterada.")
                else:
                    st.error("Chave inválida.")

            if deletar:
                delete_api_key(_provider_cur)
                st.cache_data.clear()
                st.warning("Chave removida.")
                st.rerun()

            if testar:
                key_test = (
                    nova_key.strip()
                    if nova_key.strip() not in ("", "••••••••")
                    else _api_key_global
                )
                if not key_test:
                    st.error("Nenhuma chave para testar.")
                else:
                    modelo_test = get_model(_provider_cur)
                    with st.spinner("Testando..."):
                        ok, msg = test_api_key(key_test, modelo_test, _provider_cur)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

        # ── Modelo expander ────────────────────────────────────────────────────
        with st.expander("🤖 Modelo (API Remota)", expanded=False):
            if _api_key_global:
                n_models = len(_models_raw)
                st.caption(f"{n_models} modelos disponíveis." if n_models else "Usando lista padrão.")
            else:
                st.caption("Configure a API Key para ver os modelos disponíveis.")

            modelo_atual = get_model(_provider_cur)
            if modelo_atual not in _model_options:
                modelo_atual = list(_model_options.keys())[0]

            modelo_sel = st.selectbox(
                "Modelo ativo",
                options=list(_model_options.keys()),
                format_func=lambda m: _model_options[m],
                index=list(_model_options.keys()).index(modelo_atual),
                help="Cache de 1 hora.",
                key=f"modelo_sel_exp_{_provider_cur}",
            )

            if modelo_sel != get_model(_provider_cur):
                save_model(modelo_sel, _provider_cur)
                st.success(f"Modelo: **{_model_options[modelo_sel]}**")

            selected_raw = next((m for m in _models_raw if m["id"] == modelo_sel), None)
            if selected_raw:
                st.markdown(
                    f"<span style='color:#71717A;font-size:11px'>ID: "
                    f"<span style='font-family:IBM Plex Mono;color:#FAFAFA'>{modelo_sel}</span></span>",
                    unsafe_allow_html=True,
                )
            if _api_key_global:
                if st.button("🔄 Atualizar lista de modelos", key="btn_refresh_models"):
                    st.cache_data.clear()
                    st.rerun()

    else:
        # ── Motor IA Local active ──────────────────────────────────────────────
        if _cc_available:
            _cc_info = _cc_info_cached()
            ver_txt  = _cc_info.get("version", "")
            mod_txt  = _cc_info.get("model", "")
            st.markdown(
                "<div style='background:#09090B;border:1px solid #22C55E33;"
                "border-radius:6px;padding:8px 12px;margin-bottom:6px'>"
                "<span style='color:#22C55E;font-size:11px;font-family:IBM Plex Mono'>✓ Motor IA Local</span>"
                + (f"<span style='color:#71717A;font-size:11px'> · v{ver_txt}</span>" if ver_txt else "")
                + (f"<span style='color:#71717A;font-size:11px'> · {mod_txt}</span>" if mod_txt else "")
                + "</div>",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if ver_txt:
                    st.metric("Versão instalada", ver_txt)
            with c2:
                if mod_txt:
                    st.metric("Modelo local", mod_txt)
            if st.button("🧪 Testar Motor IA Local", key="btn_test_cc"):
                with st.spinner("Testando..."):
                    ok, msg = test_local_agent_connection()
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
        else:
            st.warning("Motor IA local não encontrado. Instale o motor para usar esta função.")

    # ── Fontes de pesquisa expander ────────────────────────────────────────────
    with st.expander("🌐 Fontes de pesquisa", expanded=False):
        _sources_enabled = get_sources_enabled()
        new_enabled = st.toggle("Usar fontes prioritárias", value=_sources_enabled, key="toggle_sources")
        if new_enabled != _sources_enabled:
            save_sources_enabled(new_enabled)
            st.rerun()
        if new_enabled:
            current_sources = get_all_sources()
            sources_text = st.text_area(
                "Fontes (uma por linha)",
                value="\n".join(current_sources),
                height=100,
                help="Ex: infomoney.com, valor.com.br, investing.com/br",
                key="sources_text",
            )
            if st.button("💾 Salvar fontes", key="btn_save_sources"):
                new_sources = [s.strip() for s in sources_text.split("\n") if s.strip()]
                save_sources(new_sources)
                st.success(f"{len(new_sources)} fonte(s) salva(s).")

    # ── Cache expander ─────────────────────────────────────────────────────────
    with st.expander("💾 Cache de análises", expanded=False):
        ttl_label_atual = get_ttl_label()
        ttl_sel = st.selectbox(
            "Validade do cache",
            options=list(TTL_OPTIONS.keys()),
            index=list(TTL_OPTIONS.keys()).index(ttl_label_atual)
                   if ttl_label_atual in TTL_OPTIONS else 2,
            help="Análises salvas são reutilizadas durante este período.",
            key="ttl_sel_exp",
        )
        if ttl_sel != ttl_label_atual:
            save_ttl(ttl_sel)
            st.success(f"Validade atualizada: **{ttl_sel}**")

        _ttl_now = TTL_OPTIONS[ttl_sel]
        stats    = cache_stats(_ttl_now)
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("Total em cache",  stats["total"])
        col_s2.metric("Válidos",         stats["valid"])
        col_s3.metric("Expirados",       stats["expired"])

        if stats["total"] > 0:
            items_cache = list_cached(_ttl_now)
            with st.expander(f"Ver {stats['total']} ativo(s) em cache"):
                for item in items_cache:
                    score = item.get("macro_score")
                    clr   = "#22C55E" if (score or 0) > 20 else "#EF4444" if (score or 0) < -20 else "#F59E0B"
                    exp_txt = " · expirado" if item["expired"] else ""
                    st.markdown(
                        f"<span style='font-family:IBM Plex Mono;font-size:12px'>"
                        f"{item['ticker']}</span>"
                        f"<span style='color:#71717A;font-size:11px'> · {item['age_minutes']} min{exp_txt}</span>"
                        + (f" · <span style='color:{clr};font-size:11px'>score {score:+d}</span>" if score is not None else ""),
                        unsafe_allow_html=True,
                    )

            col_cl1, _ = st.columns([2, 3])
            with col_cl1:
                if st.button("🗑️ Limpar todo o cache", width="stretch", key="btn_clear_cache"):
                    n = invalidate_all()
                    st.success(f"{n} entrada(s) removida(s).")
                    st.rerun()


# ── TAB 2 — ANÁLISE ───────────────────────────────────────────────────────────
with tab_analise:
    _provider_ativo = get_active_provider()
    _requires_key   = AI_PROVIDERS[_provider_ativo]["requires_key"]
    _api_key_ativo  = get_api_key(_provider_ativo)
    if _requires_key and not _api_key_ativo:
        st.warning("Configure sua API Key na aba ⚙️ Configuração.")
        st.info("Ou mude para o **Motor IA Local** (sem API Key) na aba ⚙️.")
        st.stop()

    pre_ticker = st.session_state.pop("ia_ticker", None)
    opcoes = dict(
        sorted(
            {f"{t} — {n}": t for t, n in ACOES.items() if t != "^BVSP"}.items(),
            key=lambda item: item[0].split(" — ")[1].lower(),
        )
    )
    default    = next(
        (k for k, v in opcoes.items() if v == pre_ticker),
        list(opcoes.keys())[0],
    )

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        sel = st.selectbox(
            "Ativo",
            list(opcoes.keys()),
            index=list(opcoes.keys()).index(default),
            help="Digite para filtrar por ticker ou nome da empresa.",
        )
        ticker = opcoes[sel]
        nome   = ACOES[ticker]
        setor  = next((s for s, ts in GRUPOS.items() if ticker in ts), "Geral")
    with c2:
        periodo_map = {
            "1 mês":   "1mo",
            "3 meses": "3mo",
            "6 meses": "6mo",
            "1 ano":   "1y",
        }
        periodo_label = st.selectbox(
            "Período",
            list(periodo_map.keys()),
            index=1,
            help="Mínimo de 1 mês para análise técnica. 3 meses recomendado.",
        )
        periodo = periodo_map[periodo_label]
    with c3:
        st.write("")
        st.write("")
        rodar = st.button("🧠 Analisar", width="stretch", type="primary")

    modelo_ativo  = get_model(_provider_ativo)
    preset_ativo  = get_preset(_provider_ativo)
    pcfg          = AI_PRESETS.get(preset_ativo, AI_PRESETS["padrão"])
    _prov_lbl_a   = AI_PROVIDERS[_provider_ativo]["label"]
    _prov_color_a = "#22C55E" if _provider_ativo == "claude_code" else "#2563EB"
    st.markdown(
        f"<span style='color:{_prov_color_a};font-size:11px;font-family:Space Mono'>"
        f"● {_prov_lbl_a}</span>",
        unsafe_allow_html=True,
    )
    if _requires_key:
        st.caption(
            f"Setor: **{setor}** · Modelo: {_model_options.get(modelo_ativo, modelo_ativo)} · "
            f"{pcfg['icon']} {pcfg['label']} "
            f"({pcfg['max_uses']} busca{'s' if pcfg['max_uses'] > 1 else ''} · "
            f"até {pcfg['max_tokens']:,} tokens)"
        )
    else:
        st.caption(f"Setor: **{setor}** · Motor IA local (sem custo de API)")

    disk_cached = get_cached(ticker, ttl=get_ttl())
    if disk_cached and not rodar:
        age_min = int((_time.time() - disk_cached.get("cached_at", 0)) / 60)
        st.info(f"Exibindo análise do cache ({age_min} min atrás). Clique em **Analisar** para atualizar.")
        setup_cached = st.session_state.get(f"ia_setup_{ticker}")
        _render_analysis(ticker, nome, disk_cached, setup_cached)
    elif rodar:
        from b3analytics.infrastructure.ai_analyst import _analyze_via_local_agent
        from b3analytics.infrastructure.fetcher import get_analyst_data as _get_analyst_data

        params = st.session_state.get("indicator_params", dict(INDICATOR_DEFAULTS))
        prog   = st.progress(0, "Iniciando análise paralela...")

        with ThreadPoolExecutor(max_workers=3) as ex:
            f_dados    = ex.submit(_fetch_one, ticker, periodo)
            f_macro    = ex.submit(get_macro_context)
            f_analyst  = ex.submit(_get_analyst_data, ticker)
            prog.progress(25, "Buscando dados técnicos, macro e analistas em paralelo...")
            _, df      = f_dados.result()
            macro      = f_macro.result()
            analyst_data = f_analyst.result()

        prog.progress(50, "Processando dados...")

        setup       = None
        sem_tecnico = False

        if df is None or len(df) < 15:
            sem_tecnico = True
            prog.progress(55, "Poucos dados técnicos — continuando análise macro...")
            st.info(
                f"⚠️ Período **{periodo_label}** retornou poucos candles para análise técnica. "
                "A análise de IA prosseguirá com foco em **notícias, macro e consenso de analistas**.",
                icon="📰",
            )
        else:
            prog.progress(55, "Calculando setup técnico...")
            setup = find_setup(df, ticker, capital=1_000, risk_pct=0.02, params=params)

        msg_prog = (
            "Motor IA local analisando notícias e macro..."
            if _provider_ativo == "claude_code"
            else "Chamando API com busca de notícias..."
        )
        prog.progress(65, msg_prog)

        try:
            if _provider_ativo == "claude_code":
                resultado = _analyze_via_local_agent(
                    ticker, nome, setor, setup, macro,
                    analyst_data=analyst_data,
                )
                resultado["_provider"] = "claude_code"
            else:
                resultado = analyze(
                    ticker, nome, setor, setup, _api_key_ativo,
                    model=modelo_ativo, macro_preloaded=macro, preset=preset_ativo,
                    analyst_data=analyst_data, provider=_provider_ativo,
                )
                resultado["_provider"] = _provider_ativo
            resultado["_analyst_yf"] = analyst_data
            save_cache(ticker, resultado)
            prog.progress(100, "Concluído!")
            prog.empty()
        except Exception as e:
            logger.warning("Erro ao executar análise de IA: ticker=%s provider=%s", ticker, _provider_ativo)
            prog.empty()
            err = str(e)
            if "401" in err:
                st.error("API Key inválida. Reconfigure na aba ⚙️ Configuração.")
            elif "529" in err or "overloaded" in err.lower():
                st.error("API sobrecarregada. Tente em alguns instantes.")
            elif "JSON" in err or "json" in err:
                st.error("Resposta da IA inválida. Tente novamente.")
            else:
                st.error("Erro interno. Tente novamente.")
            st.stop()

        _render_analysis(ticker, nome, resultado, setup)
