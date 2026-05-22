from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from b3analytics.config.assets import get_acoes, get_grupos
from b3analytics.domain.engine import find_setup
from b3analytics.domain.indicators import add_all_indicators
from b3analytics.domain.levels import find_key_levels
from b3analytics.infrastructure.fetcher import get_fundamentals, get_historico
from b3analytics.presentation.components import (
    confidence_bar,
    direction_badge,
    fmt_brl,
    fmt_pct,
    render_ai_badge,
    render_fundamentals,
)
from b3analytics.presentation.setup_badges import setup_semaphore_badge
from b3analytics.presentation.theme import COLORS, apply_plotly_template

ACOES  = get_acoes()
GRUPOS = get_grupos()
from b3analytics.config.settings import INDICATOR_DEFAULTS, PERIODOS


def get_params() -> dict:
    return st.session_state.get("indicator_params", dict(INDICATOR_DEFAULTS))

st.markdown('<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA">Análise de Gráfico</h2>', unsafe_allow_html=True)

_qp_ticker = st.query_params.get("ticker", "")
_default_idx = list(ACOES.keys()).index(_qp_ticker) if _qp_ticker in ACOES else 0

col_sel, col_per = st.columns([3, 1])
with col_sel:
    ticker = st.selectbox("Ativo", list(ACOES.keys()), index=_default_idx, format_func=lambda t: f"{t} — {ACOES[t]}")
with col_per:
    periodo = st.select_slider("Período", list(PERIODOS.keys()), value="1 ano")

# Contextual nav bar
_ticker_limpo_nav = ticker.replace(".SA", "")
c_set, c_ia, c_fund, _ = st.columns([1, 1, 2, 4])
with c_set:
    if st.button("🎯 Setups", key="nav_setups", width="stretch"):
        st.switch_page("pages/setups.py")
with c_ia:
    if st.button("🧠 IA", key="nav_ia", width="stretch"):
        st.session_state["ia_ticker"] = ticker
        st.switch_page("pages/ia.py")
with c_fund:
    st.link_button(
        "Fundamentus ↗",
        f"https://www.fundamentus.com.br/detalhes.php?papel={_ticker_limpo_nav}",
        width="stretch",
    )

st.caption("Parâmetros de indicadores configuráveis em ⚙️ Configurações.")

with st.spinner(f"Carregando {ticker}..."):
    df_raw = get_historico(ticker, periodo)

if df_raw is None or df_raw.empty:
    st.error(f"Sem dados para {ticker}.")
    st.stop()

params = get_params()
df = add_all_indicators(df_raw.copy(), params=params)

def _c(keys):
    return next((k for k in keys if k in df.columns), None)

cc  = _c(["close","Close"])
oc  = _c(["open","Open"])
hc  = _c(["high","High"])
lc  = _c(["low","Low"])
vc  = _c(["volume","Volume"])

prices   = df[cc].dropna()
p_atual  = float(prices.iloc[-1])
p_ant    = float(prices.iloc[-2]) if len(prices) >= 2 else p_atual
var_dia  = (p_atual - p_ant) / p_ant * 100
var_per  = (p_atual - float(prices.iloc[0])) / float(prices.iloc[0]) * 100

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Preço Atual",      fmt_brl(p_atual), fmt_pct(var_dia))
m2.metric(f"Retorno ({periodo})", fmt_pct(var_per))
m3.metric(f"Mínima ({periodo})",  fmt_brl(float(prices.min())))
m4.metric(f"Máxima ({periodo})",  fmt_brl(float(prices.max())))
if vc:
    vol_val = df[vc].iloc[-1]
    if pd.notna(vol_val) and vol_val > 0:
        m5.metric("Volume", f"{int(vol_val):,}")
    else:
        m5.metric("Volume", "—")

st.markdown("---")

o1, o2, o3, o4, o5, o6, o7 = st.columns(7)
show_sma20  = o1.checkbox("SMA 20",   True)
show_sma50  = o2.checkbox("SMA 50",   True)
show_sma200 = o3.checkbox("SMA 200",  False)
show_ema9   = o4.checkbox("EMA 9",    False)
show_ema21  = o5.checkbox("EMA 21",   False)
show_bb     = o6.checkbox("Bollinger",False)
show_vwap   = o7.checkbox("VWAP",     False)

p1, p2, p3 = st.columns(3)
show_rsi   = p1.checkbox("RSI (14)", True)
show_macd  = p2.checkbox("MACD",     True)
show_stoch = p3.checkbox("Estocástico", False)

with st.spinner("Calculando setup..."):
    setup = find_setup(df_raw, ticker, st.session_state.get("capital", 10000), st.session_state.get("risk_pct", 0.02), params=params)

levels = find_key_levels(df_raw)

sub_n, sub_h, sub_t = 2, [0.55, 0.10], ["", ""]
if show_rsi:   sub_n+=1; sub_h.append(0.14); sub_t.append("RSI")
if show_macd:  sub_n+=1; sub_h.append(0.14); sub_t.append("MACD")
if show_stoch: sub_n+=1; sub_h.append(0.12); sub_t.append("Estocástico")

fig = make_subplots(rows=sub_n, cols=1, shared_xaxes=True,
                    vertical_spacing=0.025, row_heights=sub_h,
                    subplot_titles=sub_t)

if oc and hc and lc:
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df[oc], high=df[hc], low=df[lc], close=df[cc],
        increasing=dict(line=dict(color=COLORS["success"]), fillcolor=COLORS["success"]),
        decreasing=dict(line=dict(color=COLORS["error"]),   fillcolor=COLORS["error"]),
        name="Preço", showlegend=False,
    ), row=1, col=1)
else:
    fig.add_trace(go.Scatter(x=df.index, y=df[cc], line=dict(color=COLORS["success"], width=1.5), name="Close"), row=1, col=1)

def _add(col, label, color, dash="solid"):
    if col in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=label,
                                 line=dict(color=color, width=1.2, dash=dash), opacity=0.85), row=1, col=1)

if show_sma20:  _add("SMA_20",  "SMA 20",  "#F59E0B")
if show_sma50:  _add("SMA_50",  "SMA 50",  "#FB923C")
if show_sma200: _add("SMA_200", "SMA 200", "#EF4444", "dot")
if show_ema9:   _add("EMA_9",   "EMA 9",   "#60A5FA")
if show_ema21:  _add("EMA_21",  "EMA 21",  "#818CF8")
if show_vwap:   _add("VWAP",    "VWAP",    "#84CC16", "dash")

if show_bb and "BB_upper" in df.columns:
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="BB +2σ",
                             line=dict(color="#A78BFA", width=1, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="BB −2σ",
                             line=dict(color="#A78BFA", width=1, dash="dash"),
                             fill="tonexty", fillcolor="rgba(167,139,250,0.06)"), row=1, col=1)

for lvl in levels["supports"]:
    fig.add_hline(y=lvl["price"], line_dash="dot", line_color="rgba(34,197,94,0.4)",
                  line_width=1, row=1, col=1)
for lvl in levels["resistances"]:
    fig.add_hline(y=lvl["price"], line_dash="dot", line_color="rgba(239,68,68,0.4)",
                  line_width=1, row=1, col=1)

if setup:
    ep = setup["entry"]["price"]
    sp = setup["stop"]["price"]
    t1 = setup["targets"][0]["price"] if setup["targets"] else ep * 1.05

    fig.add_hline(y=ep, line_dash="dash", line_color="#2563EB", line_width=1.5, row=1, col=1,
                  annotation_text=f"Entrada {fmt_brl(ep)}", annotation_position="right")
    fig.add_hline(y=sp, line_dash="dash", line_color="#EF4444", line_width=1.5, row=1, col=1,
                  annotation_text=f"Stop {fmt_brl(sp)}", annotation_position="right")
    for t_obj in setup["targets"]:
        opacity = 1.0 - (t_obj["n"] - 1) * 0.25
        fig.add_hline(y=t_obj["price"], line_dash="dash",
                      line_color=f"rgba(34,197,94,{opacity:.1f})", line_width=1.2, row=1, col=1,
                      annotation_text=f"A{t_obj['n']} {fmt_brl(t_obj['price'])}", annotation_position="right")
    fig.add_hrect(y0=sp, y1=ep, fillcolor="rgba(239,68,68,0.07)", line_width=0, row=1, col=1)
    fig.add_hrect(y0=ep, y1=t1, fillcolor="rgba(34,197,94,0.07)", line_width=0, row=1, col=1)

if vc:
    closes = df[cc].values
    vol_colors = [COLORS["success"] if i == 0 or closes[i] >= closes[i-1] else COLORS["error"]
                  for i in range(len(closes))]
    fig.add_trace(go.Bar(x=df.index, y=df[vc], marker_color=vol_colors,
                         opacity=0.45, name="Volume", showlegend=False), row=2, col=1)

cur = 3
if show_rsi and "RSI_14" in df.columns:
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI",
                             line=dict(color="#A78BFA", width=1.4)), row=cur, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color=COLORS["error"],   opacity=0.5, row=cur, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color=COLORS["success"], opacity=0.5, row=cur, col=1)
    fig.update_yaxes(range=[0, 100], row=cur, col=1)
    cur += 1

if show_macd and "MACD" in df.columns:
    hist = df["MACD_hist"].fillna(0)
    hcolors = [COLORS["success"] if v >= 0 else COLORS["error"] for v in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, marker_color=hcolors, opacity=0.7,
                         name="Hist", showlegend=False), row=cur, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"],        name="MACD",
                             line=dict(color="#60A5FA", width=1.2)), row=cur, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal",
                             line=dict(color="#FB923C", width=1.2)), row=cur, col=1)
    cur += 1

if show_stoch and "Stoch_K" in df.columns:
    fig.add_trace(go.Scatter(x=df.index, y=df["Stoch_K"], name="%K",
                             line=dict(color="#34D399", width=1.2)), row=cur, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["Stoch_D"], name="%D",
                             line=dict(color="#FB923C", width=1.2, dash="dot")), row=cur, col=1)
    fig.add_hline(y=80, line_dash="dash", line_color=COLORS["error"],   opacity=0.4, row=cur, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color=COLORS["success"], opacity=0.4, row=cur, col=1)
    fig.update_yaxes(range=[0, 100], row=cur, col=1)

fig = apply_plotly_template(fig, height=680)
fig.update_layout(
    dragmode="pan",
    uirevision=f"{ticker}_{periodo}",
)
fig.update_xaxes(fixedrange=False)
fig.update_yaxes(fixedrange=False)
st.plotly_chart(
    fig,
    width="stretch",
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "toImageButtonOptions": {"format": "png", "filename": f"{ticker}_grafico"},
    },
)

col_s, col_f = st.columns([1, 1])

with col_s:
    st.markdown("### Setup")
    if setup:
        ep    = setup["entry"]["price"]
        sp    = setup["stop"]["price"]
        conf  = setup["confidence"]
        stype = setup["type"]
        sz    = setup["sizing"]
        type_lbl = {"PULLBACK":"Pullback","ROMPIMENTO":"Rompimento","REVERSAO":"Reversão","CRUZAMENTO":"Cruzamento"}.get(stype, stype)
        st.markdown(
            f'<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">'
            f'{direction_badge(setup["direction"])} '
            f'<span style="color:#A1A1AA;font-size:0.8rem">{type_lbl}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="margin-bottom:8px">{setup_semaphore_badge(setup)}</div>',
            unsafe_allow_html=True,
        )
        confidence_bar(conf, setup["direction"])

        data = [
            ("ENTRADA", fmt_brl(ep), "#2563EB"),
            ("STOP",    fmt_brl(sp), "#EF4444"),
        ]
        for t_obj in setup["targets"]:
            data.append((f"ALVO {t_obj['n']}", f"{fmt_brl(t_obj['price'])} (R/R {t_obj['rr']:.1f}x)", "#22C55E"))

        for label, val, color in data:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #27272A">'
                f'<span style="color:#A1A1AA;font-size:0.75rem;font-family:\'Space Mono\',monospace">{label}</span>'
                f'<span style="color:{color};font-size:0.82rem;font-family:\'Space Mono\',monospace">{val}</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div style="margin-top:8px;font-size:0.75rem;color:#A1A1AA">'
            f'Qtd: <span style="color:#FAFAFA;font-family:\'Space Mono\',monospace">{sz.get("quantity","—")}</span> ações &nbsp;|&nbsp;'
            f'Alocado: <span style="color:#FAFAFA;font-family:\'Space Mono\',monospace">{fmt_brl(sz.get("allocated",0))}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div style="color:#71717A;font-size:0.85rem">Nenhum setup identificado para este ativo/período.</div>',
                    unsafe_allow_html=True)

with col_f:
    st.markdown("### Fundamentalistas")
    with st.spinner("Buscando..."):
        fund = get_fundamentals(ticker)
    render_fundamentals(fund)
    ticker_limpo = ticker.replace(".SA", "")
    st.markdown(f"[📊 Ver no Fundamentus ↗](https://www.fundamentus.com.br/detalhes.php?papel={ticker_limpo})")

    nome_graf  = ACOES.get(ticker, ticker)
    setor_graf = next((s for s, ts in GRUPOS.items() if ticker in ts), "Geral")
    st.markdown("### Análise IA")
    render_ai_badge(ticker, nome_graf, setor_graf, setup, compact=False)

st.divider()
csv = df_raw.to_csv().encode("utf-8")
st.download_button("⬇ Baixar dados (CSV)", csv, f"{ticker.replace('^','')}_{periodo}.csv", "text/csv")
