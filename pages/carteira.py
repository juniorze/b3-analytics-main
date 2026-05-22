from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

import pandas as pd
import streamlit as st

from b3analytics.config.assets import get_grupos
from b3analytics.domain.engine import find_setup
from b3analytics.domain.portfolio import (
    PortfolioDashboardRow,
    PortfolioValidationError,
    calculate_portfolio_dashboard,
    portfolio_dashboard_to_csv,
)
from b3analytics.domain.portfolio_risk import PortfolioRiskLimits, calculate_portfolio_risk
from b3analytics.domain.portfolio_setup import portfolio_technical_reading
from b3analytics.domain.setup_classifier import (
    STATUS_DADOS_INSUFICIENTES,
    STATUS_ERRO_CALCULO,
    classify_setup,
)
from b3analytics.infrastructure.fetcher import get_historico_titled, get_precos_atuais
from b3analytics.infrastructure.portfolio_import import parse_portfolio_csv
from b3analytics.infrastructure.portfolio_store import PortfolioStore, get_default_db_path
from b3analytics.presentation.components import fmt_brl, fmt_pct
from b3analytics.presentation.setup_badges import (
    portfolio_empty_setup_state,
    setup_educational_notice,
    setup_status_label,
)


@st.cache_resource
def _get_store() -> PortfolioStore:
    return PortfolioStore()


def _as_dataframe(items: list[object]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    return pd.DataFrame([asdict(item) for item in items])


def _dashboard_dataframe(rows: list[PortfolioDashboardRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "Ticker",
            "Quantidade",
            "Preco medio",
            "Custo total",
            "Preco atual",
            "Valor atual",
            "P/L nao realizado R$",
            "P/L nao realizado %",
            "P/L realizado R$",
            "Peso %",
            "Status cotacao",
        ])

    return pd.DataFrame(
        [
            {
                "Ticker": row.ticker,
                "Quantidade": row.quantity,
                "Preco medio": row.average_price,
                "Custo total": row.total_cost,
                "Preco atual": row.current_price,
                "Valor atual": row.current_value,
                "P/L nao realizado R$": row.unrealized_pnl,
                "P/L nao realizado %": row.unrealized_pnl_pct,
                "P/L realizado R$": row.realized_pnl,
                "Peso %": row.weight_pct,
                "Status cotacao": row.price_status,
            }
            for row in rows
        ]
    )


def _risk_asset_dataframe(risk_result) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": item.ticker,
                "Valor atual": item.current_value,
                "Exposicao %": item.weight_pct,
                "Limite %": item.limit_pct,
                "Status": item.status,
            }
            for item in risk_result.asset_concentrations
        ]
    )


def _risk_group_dataframe(risk_result) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Grupo": item.group,
                "Ativos": ", ".join(item.tickers),
                "Valor atual": item.current_value,
                "Exposicao %": item.weight_pct,
                "Limite %": item.limit_pct,
                "Status": item.status,
            }
            for item in risk_result.group_concentrations
        ]
    )


def _risk_volatility_dataframe(risk_result) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Ticker": ticker, "Volatilidade anualizada %": volatility}
            for ticker, volatility in sorted(risk_result.volatility_by_ticker_pct.items())
        ]
    )


def _technical_classification(status: str, reason: str, warning: str | None = None) -> dict:
    meta = {
        STATUS_DADOS_INSUFICIENTES: {
            "label": "Dados insuficientes",
            "icon": "○",
            "color": "#71717A",
            "severity": "neutral",
        },
        STATUS_ERRO_CALCULO: {
            "label": "Erro de calculo",
            "icon": "!",
            "color": "#EF4444",
            "severity": "error",
        },
    }[status]
    return {
        "status": status,
        "label": meta["label"],
        "icon": meta["icon"],
        "color": meta["color"],
        "severity": meta["severity"],
        "reasons": [reason],
        "warnings": [warning] if warning else [],
    }


def _portfolio_setup_dataframe(results: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": item["ticker"],
                "Status do semaforo": item["status_label"],
                "Leitura tecnica da posicao": item["reading"],
                "Motivos": " | ".join(item["reasons"]),
                "Avisos": " | ".join(item["warnings"]),
            }
            for item in results
        ]
    )


st.markdown(
    '<h2 style="font-family:\'Space Mono\',monospace;color:#FAFAFA">Carteira</h2>',
    unsafe_allow_html=True,
)
st.info(
    "Controle manual e educacional de carteira. Os dados servem para acompanhamento "
    "local de posicao, exposicao, simulacao e risco; nao constituem orientacao de investimento."
)
st.caption(f"Banco local fora do repositorio: `{get_default_db_path()}`")

store = _get_store()

with st.form("portfolio_manual_transaction", clear_on_submit=True):
    st.markdown("### Lancamento manual")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        operation_date = st.date_input("Data", value=date.today())
    with c2:
        ticker = st.text_input("Ticker", placeholder="PETR4 ou PETR4.SA")
    with c3:
        operation_type = st.selectbox(
            "Tipo",
            ["BUY", "SELL"],
            format_func=lambda value: "Entrada (BUY)" if value == "BUY" else "Saida (SELL)",
        )

    c4, c5, c6 = st.columns([1, 1, 1])
    with c4:
        quantity = st.number_input("Quantidade", min_value=0.0, step=1.0, format="%.6f")
    with c5:
        price = st.number_input("Preco unitario", min_value=0.0, step=0.01, format="%.6f")
    with c6:
        fees = st.number_input("Taxas", min_value=0.0, step=0.01, format="%.2f")

    c7, c8 = st.columns([1, 2])
    with c7:
        broker = st.text_input("Corretora")
    with c8:
        notes = st.text_input("Observacoes")

    submitted = st.form_submit_button("Registrar operacao", width="stretch")

if submitted:
    try:
        store.add_transaction(
            {
                "date": operation_date.isoformat(),
                "ticker": ticker,
                "type": operation_type,
                "quantity": quantity,
                "price": price,
                "fees": fees,
                "broker": broker,
                "asset_class": "ACAO",
                "notes": notes,
            }
        )
    except PortfolioValidationError as exc:
        st.error(str(exc))
    else:
        st.success("Operacao registrada.")
        st.rerun()

st.markdown("### Importacao CSV")
st.caption(
    "Colunas: date,ticker,type,quantity,price,fees,broker,asset_class,notes. "
    "Por seguranca, qualquer erro bloqueia a importacao inteira."
)
uploaded = st.file_uploader("Arquivo CSV", type=["csv"])
if uploaded is not None:
    content = uploaded.getvalue()
    preview = parse_portfolio_csv(content, existing_transactions=store.list_transactions())

    if preview.valid_rows:
        st.markdown("Previa das linhas validas")
        st.dataframe(_as_dataframe(preview.valid_rows), width="stretch", height=240)
    else:
        st.info("Nenhuma linha valida encontrada no CSV.")

    if preview.errors:
        st.warning("Foram encontrados erros no CSV. Corrija o arquivo antes de importar.")
        st.dataframe(
            pd.DataFrame([asdict(error) for error in preview.errors]),
            width="stretch",
            height=180,
        )

    if st.button("Importar CSV validado", disabled=not preview.can_import, width="stretch"):
        store.add_transactions(preview.valid_rows)
        st.success("CSV importado.")
        st.rerun()

transactions = store.list_transactions()
snapshot = store.get_snapshot()
position_tickers = tuple(position.ticker for position in snapshot.positions)
current_quotes = get_precos_atuais(position_tickers) if position_tickers else {}
dashboard = calculate_portfolio_dashboard(snapshot, current_quotes)

st.markdown("### Dashboard da carteira")
card1, card2, card3 = st.columns(3)
with card1:
    st.metric("Patrimonio atual", fmt_brl(dashboard.totals.current_value))
with card2:
    st.metric("Custo total", fmt_brl(dashboard.totals.total_cost))
with card3:
    st.metric(
        "P/L nao realizado",
        fmt_brl(dashboard.totals.unrealized_pnl),
        fmt_pct(dashboard.totals.unrealized_pnl_pct),
    )
card4, card5 = st.columns(2)
with card4:
    st.metric("P/L realizado", fmt_brl(dashboard.totals.realized_pnl))
with card5:
    st.metric("Ativos em carteira", str(dashboard.totals.assets_count))

if dashboard.totals.missing_quotes_count:
    st.warning("Algumas cotacoes nao foram carregadas. Itens afetados exibem dados indisponiveis.")

with st.expander("Risco da carteira", expanded=bool(dashboard.rows)):
    st.caption(
        "Analise local de concentracao, volatilidade, drawdown e correlacao. "
        "Ausencia de dado aparece como dados insuficientes."
    )
    risk_limit_col1, risk_limit_col2 = st.columns(2)
    with risk_limit_col1:
        max_asset_pct = st.number_input(
            "Limite maximo por ativo (%)",
            min_value=1.0,
            max_value=100.0,
            value=30.0,
            step=1.0,
        )
    with risk_limit_col2:
        max_group_pct = st.number_input(
            "Limite maximo por grupo (%)",
            min_value=1.0,
            max_value=100.0,
            value=45.0,
            step=1.0,
        )

    priced_tickers = tuple(
        row.ticker
        for row in dashboard.rows
        if row.current_price is not None and row.current_value is not None
    )
    histories = {ticker: get_historico_titled(ticker, "1 ano") for ticker in priced_tickers}
    risk = calculate_portfolio_risk(
        snapshot,
        current_quotes,
        histories=histories,
        groups=get_grupos(),
        limits=PortfolioRiskLimits(max_asset_pct=max_asset_pct, max_group_pct=max_group_pct),
    )

    if risk.missing_price_tickers:
        st.warning(
            "Ativos sem cotacao atual foram excluidos dos calculos de risco de mercado: "
            + ", ".join(risk.missing_price_tickers)
        )
    if risk.insufficient_history_tickers:
        st.info(
            "Dados insuficientes para historico de risco: "
            + ", ".join(risk.insufficient_history_tickers)
        )

    risk_card1, risk_card2, risk_card3 = st.columns(3)
    with risk_card1:
        st.metric(
            "Volatilidade anualizada",
            (
                fmt_pct(risk.portfolio_volatility_pct)
                if risk.portfolio_volatility_pct is not None
                else "nao calculado"
            ),
        )
    with risk_card2:
        st.metric(
            "Drawdown maximo",
            fmt_pct(risk.max_drawdown_pct) if risk.max_drawdown_pct is not None else "nao calculado",
        )
    with risk_card3:
        st.metric("Ativos com preco", str(len(priced_tickers)))

    st.markdown("#### Concentracao por ativo")
    asset_risk_df = _risk_asset_dataframe(risk)
    if not asset_risk_df.empty:
        st.dataframe(
            asset_risk_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Valor atual": st.column_config.NumberColumn("Valor atual", format="R$ %.2f"),
                "Exposicao %": st.column_config.NumberColumn("Exposicao %", format="%.2f%%"),
                "Limite %": st.column_config.NumberColumn("Limite %", format="%.2f%%"),
            },
        )
    else:
        st.info("Concentracao por ativo nao calculada por falta de cotacoes atuais.")

    st.markdown("#### Concentracao por grupo")
    group_risk_df = _risk_group_dataframe(risk)
    if not group_risk_df.empty:
        st.dataframe(
            group_risk_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Valor atual": st.column_config.NumberColumn("Valor atual", format="R$ %.2f"),
                "Exposicao %": st.column_config.NumberColumn("Exposicao %", format="%.2f%%"),
                "Limite %": st.column_config.NumberColumn("Limite %", format="%.2f%%"),
            },
        )
    else:
        st.info("Concentracao por grupo nao calculada por falta de dados de grupo.")

    st.markdown("#### Volatilidade por ativo")
    volatility_df = _risk_volatility_dataframe(risk)
    if not volatility_df.empty:
        st.dataframe(
            volatility_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Volatilidade anualizada %": st.column_config.NumberColumn(
                    "Volatilidade anualizada %",
                    format="%.2f%%",
                )
            },
        )
    else:
        st.info("Volatilidade por ativo nao calculada por dados insuficientes.")

    st.markdown("#### Correlacao")
    if not risk.correlation.empty:
        st.dataframe(risk.correlation, width="stretch")
    else:
        st.info("Correlacao nao calculada: menos de 2 ativos com historico suficiente.")

st.markdown("### Semáforo técnico da carteira")
st.caption(setup_educational_notice())

last_setup_analysis = st.session_state.get("portfolio_setup_analysis", [])
last_setup_tickers = st.session_state.get("portfolio_setup_analysis_tickers", ())
last_setup_analyzed_at = st.session_state.get("portfolio_setup_analysis_at")

if not position_tickers:
    st.info(portfolio_empty_setup_state())

analysis_col, clear_col = st.columns([2, 1])
with analysis_col:
    run_setup_analysis = st.button(
        "Analisar setups da carteira",
        disabled=not bool(position_tickers),
        width="stretch",
    )
with clear_col:
    clear_setup_analysis = st.button(
        "Limpar analise tecnica da carteira",
        disabled=not bool(last_setup_analysis),
        width="stretch",
    )

if clear_setup_analysis:
    st.session_state.pop("portfolio_setup_analysis", None)
    st.session_state.pop("portfolio_setup_analysis_tickers", None)
    st.session_state.pop("portfolio_setup_analysis_at", None)
    st.rerun()

if run_setup_analysis:
    setup_results = []
    progress = st.progress(0, "Analisando setups da carteira...")
    total_tickers = max(len(position_tickers), 1)

    for index, ticker in enumerate(position_tickers, start=1):
        try:
            history = get_historico_titled(ticker, "1 ano")
            if history.empty:
                classification = _technical_classification(
                    STATUS_DADOS_INSUFICIENTES,
                    "Historico indisponivel para o ativo.",
                    "Fonte de dados pode estar vazia ou atrasada.",
                )
            else:
                setup = find_setup(history, ticker)
                classification = classify_setup(setup)
        except Exception:
            classification = _technical_classification(
                STATUS_ERRO_CALCULO,
                "Falha tratada ao calcular setup tecnico.",
                "Tente novamente mais tarde.",
            )

        setup_results.append(
            {
                "ticker": ticker,
                "status_label": setup_status_label(classification),
                "reading": portfolio_technical_reading(classification),
                "reasons": classification.get("reasons", []),
                "warnings": classification.get("warnings", []),
            }
        )
        progress.progress(index / total_tickers, f"Analisados: {index}/{total_tickers}")

    progress.empty()
    st.session_state["portfolio_setup_analysis"] = setup_results
    st.session_state["portfolio_setup_analysis_tickers"] = position_tickers
    st.session_state["portfolio_setup_analysis_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")

last_setup_analysis = st.session_state.get("portfolio_setup_analysis", [])
last_setup_tickers = st.session_state.get("portfolio_setup_analysis_tickers", ())
last_setup_analyzed_at = st.session_state.get("portfolio_setup_analysis_at")
if last_setup_analysis and tuple(last_setup_tickers) == position_tickers:
    if last_setup_analyzed_at:
        st.caption(f"Ultima analise tecnica: {last_setup_analyzed_at}")
    st.dataframe(
        _portfolio_setup_dataframe(last_setup_analysis),
        width="stretch",
        hide_index=True,
    )
elif last_setup_analysis:
    st.info("A carteira mudou desde a última análise. Execute novamente para atualizar o semáforo.")
else:
    st.info("Clique no botão para calcular a avaliação técnica dos ativos em posição.")

st.markdown("#### Posicao consolidada")
dashboard_df = _dashboard_dataframe(dashboard.rows)
if dashboard.rows:
    st.dataframe(
        dashboard_df,
        width="stretch",
        height=280,
        hide_index=True,
        column_config={
            "Preco medio": st.column_config.NumberColumn("Preco medio", format="R$ %.2f"),
            "Custo total": st.column_config.NumberColumn("Custo total", format="R$ %.2f"),
            "Preco atual": st.column_config.NumberColumn("Preco atual", format="R$ %.2f"),
            "Valor atual": st.column_config.NumberColumn("Valor atual", format="R$ %.2f"),
            "P/L nao realizado R$": st.column_config.NumberColumn(
                "P/L nao realizado R$",
                format="R$ %.2f",
            ),
            "P/L nao realizado %": st.column_config.NumberColumn(
                "P/L nao realizado %",
                format="%.2f%%",
            ),
            "P/L realizado R$": st.column_config.NumberColumn("P/L realizado R$", format="R$ %.2f"),
            "Peso %": st.column_config.NumberColumn("Peso %", format="%.2f%%"),
        },
    )

    chart_df = dashboard_df.copy()
    chart_df["Peso %"] = pd.to_numeric(chart_df["Peso %"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Peso %"])
    chart_df = chart_df[chart_df["Peso %"].between(float("-inf"), float("inf"), inclusive="neither")]
    chart_df = chart_df[chart_df["Peso %"] > 0].set_index("Ticker")[["Peso %"]]
    if not chart_df.empty:
        st.markdown("#### Alocacao por ativo")
        st.bar_chart(chart_df)

    st.download_button(
        "Exportar CSV da carteira consolidada",
        data=portfolio_dashboard_to_csv(dashboard.rows),
        file_name="carteira_consolidada.csv",
        mime="text/csv",
        width="stretch",
    )
else:
    st.info("Carteira vazia. Registre uma operacao manualmente ou importe um CSV.")

st.markdown("### Operacoes")
if transactions:
    st.dataframe(_as_dataframe(transactions), width="stretch", height=300)
else:
    st.info("Carteira vazia. Registre uma operacao manualmente ou importe um CSV.")

st.markdown("### Posicoes abertas")
if snapshot.positions:
    st.dataframe(_as_dataframe(snapshot.positions), width="stretch", height=260)
else:
    st.info("Nenhuma posicao aberta calculada a partir das operacoes.")

st.markdown("### P/L realizado por ticker")
if snapshot.realized_pnl:
    st.dataframe(_as_dataframe(snapshot.realized_pnl), width="stretch", height=220)
else:
    st.info("Nenhum P/L realizado calculado ate o momento.")
