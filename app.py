import streamlit as st

from b3analytics.presentation.theme import inject_theme

st.set_page_config(
    page_title="BOLSA.BR",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

visao_geral   = st.Page("pages/visao_geral.py",   title="Visão Geral",   icon="📊", default=True)
grafico       = st.Page("pages/grafico.py",       title="Gráfico",       icon="📈", url_path="grafico")
setups        = st.Page("pages/setups.py",        title="Setups",        icon="🎯")
backtesting   = st.Page("pages/backtesting.py",   title="Backtesting",   icon="📉")
comparacao    = st.Page("pages/comparacao.py",    title="Comparação",    icon="🔀")
carteira      = st.Page("pages/carteira.py",      title="Carteira",      icon="💼")
ia            = st.Page("pages/ia.py",            title="IA",            icon="🧠")
configuracoes = st.Page("pages/configuracoes.py", title="Configurações", icon="⚙️")

pg = st.navigation(
    [visao_geral, grafico, setups, backtesting, comparacao, carteira, ia, configuracoes],
    position="sidebar",
)

from b3analytics.presentation.sidebar import render_sidebar_extras

_TRADING_PAGES = {"Setups", "Backtesting"}
render_sidebar_extras(show_trading=pg.title in _TRADING_PAGES)

pg.run()
