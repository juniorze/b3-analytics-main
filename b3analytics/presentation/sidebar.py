from datetime import datetime, timedelta, timezone

import streamlit as st

from b3analytics.config.assets import get_grupos
from b3analytics.config.settings import CAPITAL_DEFAULT, DATA_DELAY_MINUTES, RISK_PCT_DEFAULT
from b3analytics.infrastructure.ai_config import (
    AI_PROVIDERS,
    get_active_provider,
    is_configured,
    is_local_agent_available,
)


def render_sidebar_extras(show_trading: bool = False) -> None:
    GRUPOS = get_grupos()
    BRT = timezone(timedelta(hours=-3))
    agora = datetime.now(BRT)

    hora = agora.hour * 60 + agora.minute
    aberto = (10 * 60 <= hora <= 17 * 60 + 30) and agora.weekday() < 5
    cor    = "#22C55E" if aberto else "#EF4444"
    label  = "ABERTO"  if aberto else "FECHADO"

    st.sidebar.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;padding:10px 0'>"
        f"<div style='width:8px;height:8px;border-radius:50%;background:{cor}'></div>"
        f"<span style='font-family:Space Mono;font-size:12px;color:{cor}'>{label}</span>"
        f"<span style='color:#71717A;font-size:11px'>{agora.strftime('%H:%M')} BRT</span>"
        f"</div>"
        f"<div style='color:#3F3F46;font-size:10px'>delay ~{DATA_DELAY_MINUTES}min</div>",
        unsafe_allow_html=True,
    )

    st.sidebar.divider()

    if show_trading:
        capital = st.sidebar.number_input(
            "Capital por operação (R$)",
            min_value=100, max_value=500_000,
            value=int(st.session_state.get("capital", CAPITAL_DEFAULT)),
            step=100, format="%d",
        )
        risco_pct_pct = st.sidebar.slider(
            "Risco/op (%)", 0.5, 5.0,
            value=float(st.session_state.get("risco_pct_pct", RISK_PCT_DEFAULT * 100)),
            step=0.5, format="%.1f%%",
        )
        st.session_state["capital"]       = capital
        st.session_state["capital_op"]    = capital
        st.session_state["risk_pct"]      = risco_pct_pct / 100
        st.session_state["risco_pct"]     = risco_pct_pct / 100
        st.session_state["risco_pct_pct"] = risco_pct_pct
    else:
        if "capital" not in st.session_state:
            st.session_state["capital"]       = CAPITAL_DEFAULT
            st.session_state["capital_op"]    = CAPITAL_DEFAULT
            st.session_state["risk_pct"]      = RISK_PCT_DEFAULT
            st.session_state["risco_pct"]     = RISK_PCT_DEFAULT
            st.session_state["risco_pct_pct"] = RISK_PCT_DEFAULT * 100

    st.sidebar.divider()

    selected_groups = st.sidebar.multiselect(
        "Grupos",
        options=list(GRUPOS.keys()),
        default=st.session_state.get("selected_groups", []),
        placeholder="Todos os grupos",
    )
    st.session_state["selected_groups"] = selected_groups

    st.sidebar.divider()
    _render_indicator_summary()
    _render_ai_status()
    st.sidebar.caption(
        "Dados para fins informativos. Não constitui recomendação de investimento."
    )


def _render_indicator_summary() -> None:
    p = st.session_state.get("indicator_params", {})
    if not p:
        return
    st.sidebar.markdown(
        f"<div style='color:#3F3F46;font-size:10px;padding:4px 0'>"
        f"RSI {p.get('rsi_period', 14)} · "
        f"EMA {p.get('ema_fast', 9)}/{p.get('ema_slow', 21)} · "
        f"MACD {p.get('macd_fast', 12)}/{p.get('macd_slow', 26)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_ai_status() -> None:
    _provider = get_active_provider()
    if _provider == "claude_code":
        _available = is_local_agent_available()
        color = "#22C55E" if _available else "#EF4444"
        label = "Motor IA Local ativo" if _available else "Motor IA: não encontrado"
        st.sidebar.markdown(
            f"<div style='color:{color};font-size:10px;font-family:Space Mono;"
            f"padding:4px 0'>◆ {label}</div>",
            unsafe_allow_html=True,
        )
    elif is_configured(_provider):
        label = AI_PROVIDERS.get(_provider, {}).get("label", "API")
        st.sidebar.markdown(
            f"<div style='color:#2563EB;font-size:10px;font-family:Space Mono;"
            f"padding:4px 0'>◆ {label} ativa</div>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            "<div style='color:#3F3F46;font-size:10px;padding:4px 0'>"
            "◆ IA não configurada</div>",
            unsafe_allow_html=True,
        )


render_sidebar = render_sidebar_extras
