from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from b3analytics.config.assets import get_acoes
from b3analytics.domain.indicators import calcular_correlacao, calcular_retorno_normalizado
from b3analytics.infrastructure.fetcher import get_historico
from b3analytics.presentation.components import fmt_pct
from b3analytics.presentation.theme import COLORS, apply_plotly_template

ACOES = get_acoes()
from b3analytics.config.settings import PERIODOS

st.markdown('<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA">Comparação de Ativos</h2>', unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
with c1:
    selecionados = st.multiselect(
        "Selecione até 6 ativos",
        list(ACOES.keys()),
        default=["PETR4.SA", "VALE3.SA", "WEGE3.SA", "^BVSP"],
        format_func=lambda t: f"{t} — {ACOES[t]}",
        max_selections=6,
    )
with c2:
    periodo = st.select_slider("Período", list(PERIODOS.keys()), value="1 ano")

if len(selecionados) < 2:
    st.info("Selecione pelo menos 2 ativos.")
    st.stop()

with st.spinner("Carregando dados..."):
    dfs = {}
    for t in selecionados:
        df = get_historico(t, periodo)
        if df is not None and not df.empty:
            dfs[t] = df

if len(dfs) < 2:
    st.error("Dados insuficientes.")
    st.stop()

PALETTE = ["#2563EB","#22C55E","#F59E0B","#EF4444","#A78BFA","#34D399"]

st.markdown("### Retorno Acumulado — base 100")
fig = go.Figure()
for i, (t, df) in enumerate(dfs.items()):
    ret = calcular_retorno_normalizado(df)
    fig.add_trace(go.Scatter(
        x=df.index, y=100 + ret,
        name=f"{t} — {ACOES.get(t, t)}",
        line=dict(color=PALETTE[i % len(PALETTE)], width=2),
    ))
fig.add_hline(y=100, line_dash="dash", line_color="#27272A", opacity=0.6)
fig = apply_plotly_template(fig, height=400)
fig.update_layout(yaxis_title="Índice (base 100)")
st.plotly_chart(fig, width="stretch")

st.markdown("### Correlação")
corr = calcular_correlacao(dfs)
if not corr.empty:
    labels = [f"{t}" for t in corr.columns]
    fig_c = go.Figure(go.Heatmap(
        z=corr.values, x=labels, y=labels,
        colorscale=[[0.0, COLORS["error"]], [0.5, "#1F1F23"], [1.0, COLORS["success"]]],
        zmin=-1, zmax=1,
        text=corr.round(2).values, texttemplate="%{text}",
        textfont=dict(size=13, color="white"), showscale=True,
    ))
    fig_c = apply_plotly_template(fig_c, height=320)
    st.plotly_chart(fig_c, width="stretch")

    for i, t1 in enumerate(corr.columns):
        for j, t2 in enumerate(corr.columns):
            if j <= i:
                continue
            v = corr.iloc[i, j]
            if abs(v) > 0.8:
                tipo = "correlacionados" if v > 0 else "inversamente correlacionados"
                st.caption(f"{'🟢' if v > 0 else '🔴'} **{t1}** e **{t2}** são {tipo} ({v:.2f})")

st.markdown("### Métricas")
ibov_df = get_historico("^BVSP", periodo)

rows = []
for t, df in dfs.items():
    cc = next((c for c in ["close","Close"] if c in df.columns), None)
    if not cc:
        continue
    prices   = df[cc].dropna()
    ret_s    = prices.pct_change().dropna()
    ann_vol  = float(ret_s.std() * np.sqrt(252) * 100)
    ytd_ret  = float((prices.iloc[-1] / prices.iloc[0] - 1) * 100)
    max_dd   = float(((prices / prices.cummax()) - 1).min() * 100)

    beta = None
    if ibov_df is not None and not ibov_df.empty:
        ic = next((c for c in ["close","Close"] if c in ibov_df.columns), None)
        if ic:
            ibov_ret = ibov_df[ic].pct_change().dropna()
            combined = pd.concat([ret_s, ibov_ret], axis=1).dropna()
            if len(combined) > 10:
                cov = combined.iloc[:, 0].cov(combined.iloc[:, 1])
                var = combined.iloc[:, 1].var()
                beta = round(cov / var, 2) if var != 0 else None

    rows.append({
        "Ativo":          f"{t}",
        "Retorno Período": fmt_pct(ytd_ret),
        "Vol. Anualizada": f"{ann_vol:.1f}%",
        "Max Drawdown":    fmt_pct(max_dd),
        "Beta vs IBOV":    f"{beta:.2f}" if beta is not None else "—",
    })

if rows:
    st.dataframe(pd.DataFrame(rows).set_index("Ativo"), width="stretch")

st.divider()
combined_df = pd.DataFrame()
for t, df in dfs.items():
    cc = next((c for c in ["close","Close"] if c in df.columns), None)
    if cc:
        combined_df[t] = df[cc]
if not combined_df.empty:
    st.download_button("⬇ Baixar CSV", combined_df.to_csv().encode(), f"comparacao_{periodo}.csv", "text/csv")
