import json
import logging

import streamlit as st

from b3analytics.config.assets import (
    _CRYPTO_DEFAULT,
    add_ativo,
    add_crypto_custom,
    add_grupo,
    get_acoes,
    get_custom_summary,
    get_grupos,
    is_crypto_enabled,
    remove_ativo,
    reset_to_defaults,
    set_crypto_enabled,
)
from b3analytics.config.settings import INDICATOR_DEFAULTS

logger = logging.getLogger(__name__)

st.markdown('<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA">Configurações</h2>', unsafe_allow_html=True)
st.caption("Parâmetros aplicados globalmente em Gráfico, Setups e Backtesting.")

if "indicator_params" not in st.session_state:
    st.session_state["indicator_params"] = dict(INDICATOR_DEFAULTS)

p = st.session_state["indicator_params"]

st.markdown("### Médias Móveis")
c1, c2, c3 = st.columns(3)
with c1:
    p["sma_short"]  = st.number_input("SMA curta",   5,  100, int(p.get("sma_short",  20)), step=5)
    p["ema_fast"]   = st.number_input("EMA rápida",  3,   50, int(p.get("ema_fast",    9)), step=1)
with c2:
    p["sma_medium"] = st.number_input("SMA média",  10,  200, int(p.get("sma_medium", 50)), step=5)
    p["ema_slow"]   = st.number_input("EMA lenta",   5,  100, int(p.get("ema_slow",   21)), step=1)
with c3:
    p["sma_long"]   = st.number_input("SMA longa",  50,  500, int(p.get("sma_long",  200)), step=10)

st.divider()
st.markdown("### RSI")
c1, c2, c3 = st.columns(3)
with c1:
    p["rsi_period"] = st.number_input("Período",  5, 50, int(p.get("rsi_period", 14)), step=1)
with c2:
    p["rsi_ob"]     = st.slider("Sobrecompra",   55, 90, int(p.get("rsi_ob", 70)), step=1)
with c3:
    p["rsi_os"]     = st.slider("Sobrevendido",  10, 45, int(p.get("rsi_os", 30)), step=1)

st.divider()
st.markdown("### MACD")
c1, c2, c3 = st.columns(3)
with c1:
    p["macd_fast"]   = st.number_input("Rápido",  5,  50, int(p.get("macd_fast",   12)), step=1)
with c2:
    p["macd_slow"]   = st.number_input("Lento",  10, 100, int(p.get("macd_slow",   26)), step=1)
with c3:
    p["macd_signal"] = st.number_input("Sinal",   3,  20, int(p.get("macd_signal",  9)), step=1)

st.divider()
st.markdown("### Bollinger Bands")
c1, c2, _ = st.columns(3)
with c1:
    p["bb_period"] = st.number_input("Período", 5, 50, int(p.get("bb_period", 20)), step=1)
with c2:
    p["bb_std"]    = st.slider("Desvios padrão", 1.0, 3.5, float(p.get("bb_std", 2.0)), step=0.5)

st.session_state["indicator_params"] = p

st.divider()
col_reset, col_info = st.columns([1, 3])
with col_reset:
    if st.button("🔄 Restaurar padrões", width="stretch"):
        st.session_state["indicator_params"] = dict(INDICATOR_DEFAULTS)
        st.rerun()
with col_info:
    st.info(
        "Alterações aplicadas imediatamente em Gráfico, Setups e Backtesting. "
        "Volte às outras páginas após ajustar."
    )

with st.expander("Ver parâmetros ativos"):
    st.code(json.dumps(st.session_state["indicator_params"], indent=2))

# ── Editor de ativos ──────────────────────────────────────────────────────────
st.divider()
st.markdown("### Ativos e Grupos")

resumo = get_custom_summary()
_acoes_agora = get_acoes()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ativos padrão",   len(_acoes_agora) - resumo["adicionados"])
c2.metric("Adicionados",     resumo["adicionados"])
c3.metric("Removidos",       resumo["removidos"])
c4.metric("Grupos custom",   resumo["grupos_custom"])

tab_add, tab_rem, tab_grp, tab_cry = st.tabs(
    ["➕ Adicionar", "➖ Remover", "📂 Grupos", "₿ Cripto"]
)

with tab_add:
    st.markdown("**Adicionar ativo (ação, FII, ETF, BDR)**")
    ca1, ca2, ca3 = st.columns([2, 3, 2])
    with ca1:
        novo_ticker = st.text_input("Ticker", placeholder="XPTO3.SA",
                                    key="cfg_add_ticker").upper().strip()
    with ca2:
        novo_nome = st.text_input("Nome", placeholder="Nome da empresa",
                                  key="cfg_add_nome")
    with ca3:
        st.write("")
        if st.button("Adicionar ativo", width="stretch", type="primary"):
            if novo_ticker and novo_nome:
                if not (novo_ticker.endswith(".SA") or "-" in novo_ticker or novo_ticker.startswith("^")):
                    st.error("Formato inválido. Use TICKER.SA para B3 ou TICKER-USD para cripto.")
                else:
                    import yfinance as yf
                    with st.spinner("Validando ticker..."):
                        try:
                            hist = yf.Ticker(novo_ticker).history(period="5d")
                            if len(hist) > 0:
                                add_ativo(novo_ticker, novo_nome)
                                st.success(f"✅ {novo_ticker} adicionado")
                                st.rerun()
                            else:
                                st.error(f"'{novo_ticker}' sem dados no yfinance.")
                        except Exception as e:
                            logger.warning("Erro ao validar ticker no yfinance: ticker=%s", novo_ticker)
                            st.error(f"Erro ao validar: {e}")
            else:
                st.warning("Preencha ticker e nome.")

with tab_rem:
    st.markdown("**Remover ativo da lista**")
    ticker_rem = st.selectbox(
        "Ativo para remover",
        options=sorted(_acoes_agora.keys()),
        format_func=lambda t: f"{t} — {_acoes_agora[t]}",
        key="cfg_rem_ticker",
    )
    cr1, cr2 = st.columns([1, 3])
    with cr1:
        if st.button("Remover", type="secondary", width="stretch"):
            remove_ativo(ticker_rem)
            st.warning(f"'{ticker_rem}' removido.")
            st.rerun()
    with cr2:
        st.caption("O ativo pode ser re-adicionado a qualquer momento via 'Adicionar'.")

with tab_grp:
    st.markdown("**Criar novo grupo personalizado**")
    cg1, cg2 = st.columns([2, 4])
    with cg1:
        nome_grupo = st.text_input("Nome do grupo", placeholder="Meu Portfólio",
                                   key="cfg_grp_nome")
    with cg2:
        tickers_grupo = st.multiselect(
            "Ativos do grupo",
            options=sorted(_acoes_agora.keys()),
            format_func=lambda t: f"{t} — {_acoes_agora.get(t, '')}",
            key="cfg_grp_tickers",
        )
    if st.button("Criar grupo", type="primary"):
        if nome_grupo and tickers_grupo:
            add_grupo(nome_grupo, tickers_grupo)
            st.success(f"Grupo '{nome_grupo}' criado com {len(tickers_grupo)} ativos.")
            st.rerun()
        else:
            st.warning("Preencha o nome e selecione ao menos um ativo.")

    st.divider()
    st.markdown("**Grupos existentes**")
    for nome, tickers in get_grupos().items():
        with st.expander(f"{nome} ({len(tickers)} ativos)"):
            st.write(", ".join(tickers))

with tab_cry:
    cripto_on  = is_crypto_enabled()
    novo_estado = st.toggle(
        "Habilitar criptomoedas",
        value=cripto_on,
        help="Adiciona BTC, ETH, SOL e outras ao sistema via yfinance",
    )
    if novo_estado != cripto_on:
        set_crypto_enabled(novo_estado)
        st.rerun()

    if novo_estado:
        st.markdown("**Criptos padrão incluídas:**")
        for ticker, nome in _CRYPTO_DEFAULT.items():
            st.markdown(f"- `{ticker}` — {nome}")

        st.markdown("**Adicionar cripto personalizada:**")
        cy1, cy2, cy3 = st.columns([2, 3, 2])
        with cy1:
            crypto_ticker = st.text_input("Ticker", placeholder="DOGE-USD",
                                          key="cfg_cry_ticker").upper()
        with cy2:
            crypto_nome = st.text_input("Nome", placeholder="Dogecoin",
                                        key="cfg_cry_nome")
        with cy3:
            st.write("")
            if st.button("Adicionar cripto"):
                if crypto_ticker and crypto_nome and "-USD" in crypto_ticker:
                    add_crypto_custom(crypto_ticker, crypto_nome)
                    st.success(f"✅ {crypto_ticker} adicionado")
                    st.rerun()
                else:
                    st.error("Use formato TICKER-USD (ex: DOGE-USD)")

st.divider()
if st.button("🔄 Restaurar todos os padrões (remove customizações de ativos)",
             type="secondary"):
    reset_to_defaults()
    st.warning("Todas as customizações de ativos foram removidas.")
    st.rerun()
