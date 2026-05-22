from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from b3analytics.config.assets import get_acoes
from b3analytics.domain.backtesting import STRATEGIES, run_backtest
from b3analytics.infrastructure.fetcher import get_historico
from b3analytics.presentation.components import fmt_brl, fmt_pct
from b3analytics.presentation.theme import COLORS, apply_plotly_template

ACOES = get_acoes()
from b3analytics.config.settings import INDICATOR_DEFAULTS


def get_params() -> dict:
    return st.session_state.get("indicator_params", dict(INDICATOR_DEFAULTS))

st.markdown('<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA">Backtesting</h2>', unsafe_allow_html=True)

c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    ticker = st.selectbox("Ativo", list(ACOES.keys()), format_func=lambda t: f"{t} — {ACOES[t]}")
with c2:
    strategy_name = st.selectbox("Estratégia", list(STRATEGIES.keys()))
with c3:
    periodo = st.select_slider("Período", ["6 meses", "1 ano", "2 anos"], value="2 anos")

c4, c5 = st.columns(2)
with c4:
    cash = st.number_input("Capital inicial (R$)", 1_000, 1_000_000, int(st.session_state.get("capital_op", 10000)), step=1_000)
with c5:
    comm = st.slider("Corretagem (%)", 0.0, 1.0, 0.1, 0.05) / 100

if st.button("▶ Rodar Backtest", width="stretch"):
    with st.spinner(f"Rodando {strategy_name} em {ticker}..."):
        df = get_historico(ticker, periodo)
        if df is None or df.empty:
            st.error("Sem dados.")
            st.stop()
        result = run_backtest(df, STRATEGIES[strategy_name], cash=cash, commission=comm, params=get_params())

    if not result:
        st.error("Dados insuficientes (mínimo 50 candles).")
        st.stop()
    if "error" in result:
        st.error(f"Erro: {result['error']}")
        st.stop()

    ret = result["return_pct"]
    bah = result["buyhold_pct"]

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Retorno",    fmt_pct(ret), delta=fmt_pct((ret or 0) - (bah or 0)))
    m2.metric("Buy & Hold", fmt_pct(bah))
    m3.metric("Sharpe",     f"{result['sharpe']:.3f}" if result.get("sharpe") else "—")
    m4.metric("Max DD",     fmt_pct(result.get("max_drawdown")))
    m5.metric("Win Rate",   f"{result['win_rate']:.1f}%" if result.get("win_rate") else "—")
    m6.metric("Trades",     result.get("total_trades", 0))

    st.markdown("---")

    equity = result["equity_curve"]
    bah_c  = result["bah_curve"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity.index, y=equity.values, name=strategy_name,
                             line=dict(color=COLORS["primary"], width=2)))
    fig.add_trace(go.Scatter(x=bah_c.index, y=bah_c.values, name="Buy & Hold",
                             line=dict(color=COLORS["neutral"], width=1.5, dash="dash")))
    fig.add_hline(y=cash, line_dash="dot", line_color="#27272A", opacity=0.7)
    fig = apply_plotly_template(fig, height=360)
    fig.update_layout(
        title=dict(text="Equity Curve vs Buy & Hold", x=0, xanchor="left", font=dict(size=13, color="#FAFAFA")),
        yaxis_tickprefix="R$ ",
        margin=dict(l=0, r=0, t=80, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
    )
    st.plotly_chart(fig, width="stretch")

    trades = result.get("trades")
    if trades is not None and not trades.empty:
        st.markdown("### Histórico de Trades")
        disp = [c for c in ["EntryTime","ExitTime","EntryPrice","ExitPrice","PnL","ReturnPct","Duration"] if c in trades.columns]
        td = trades[disp].copy()

        def _row_style(row):
            pnl = row.get("PnL", 0)
            bg  = "rgba(34,197,94,0.07)" if (pnl or 0) >= 0 else "rgba(239,68,68,0.07)"
            return [f"background-color:{bg}"] * len(row)

        fmt = {}
        if "EntryPrice" in td.columns: fmt["EntryPrice"] = lambda x: fmt_brl(x) if isinstance(x, float) else x
        if "ExitPrice"  in td.columns: fmt["ExitPrice"]  = lambda x: fmt_brl(x) if isinstance(x, float) else x
        if "PnL" in td.columns:        fmt["PnL"]        = lambda x: f"{'+' if (x or 0)>=0 else ''}{x:.2f}" if isinstance(x, float) else x
        if "ReturnPct" in td.columns:  fmt["ReturnPct"]  = lambda x: fmt_pct(x*100) if isinstance(x, float) else x

        st.dataframe(td.style.apply(_row_style, axis=1).format(fmt),
                     width="stretch", height=300)
else:
    st.info("Configure os parâmetros e clique em **▶ Rodar Backtest**.")
