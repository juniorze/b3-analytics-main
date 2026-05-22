from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


SOURCE_YFINANCE = "yfinance"

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "dados_indisponiveis"
STATUS_EMPTY_HISTORY = "historico_vazio"
STATUS_INSUFFICIENT_HISTORY = "historico_insuficiente"
STATUS_MISSING_QUOTE = "cotacao_ausente"
STATUS_PROVIDER_UNAVAILABLE = "fonte_externa_indisponivel"
STATUS_CONTROLLED_ERROR = "erro_controlado"

ERROR_UNAVAILABLE = "dados_indisponiveis"
ERROR_EMPTY_HISTORY = "historico_vazio"
ERROR_INSUFFICIENT_HISTORY = "historico_insuficiente"
ERROR_MISSING_QUOTE = "cotacao_ausente"
ERROR_PROVIDER_UNAVAILABLE = "fonte_externa_indisponivel"
ERROR_TIMEOUT = "timeout"
ERROR_CONTROLLED = "erro_controlado"


@dataclass(frozen=True)
class DataProviderResult:
    source: str
    status: str
    data: Any = None
    error_type: str | None = None
    message: str = ""
    is_stale: bool = False
    delay_minutes: int | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


def _controlled_error_type(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text or "timed out" in text:
        return ERROR_TIMEOUT
    if "connection" in name or "connection" in text or "network" in text:
        return ERROR_PROVIDER_UNAVAILABLE
    return ERROR_CONTROLLED


def _normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    rename = {}
    for col in df.columns:
        lc = str(col).lower()
        if lc == "open":
            rename[col] = "Open"
        elif lc == "high":
            rename[col] = "High"
        elif lc == "low":
            rename[col] = "Low"
        elif lc in ("close", "adj close"):
            rename[col] = "Close"
        elif lc == "volume":
            rename[col] = "Volume"
    return df.rename(columns=rename) if rename else df


def history_result(
    *,
    source: str,
    ticker: str,
    period: str,
    df: pd.DataFrame | None,
    min_rows: int = 2,
    context: str = "data_provider.history",
) -> DataProviderResult:
    if df is None:
        logger.warning(
            "Dados indisponiveis: ticker=%s periodo=%s fonte=%s erro=%s contexto=%s",
            ticker,
            period,
            source,
            ERROR_UNAVAILABLE,
            context,
        )
        return DataProviderResult(
            source=source,
            status=STATUS_UNAVAILABLE,
            data=None,
            error_type=ERROR_UNAVAILABLE,
            message="Dados indisponiveis na fonte externa.",
        )
    if df.empty:
        logger.warning(
            "Historico vazio: ticker=%s periodo=%s fonte=%s erro=%s contexto=%s",
            ticker,
            period,
            source,
            ERROR_EMPTY_HISTORY,
            context,
        )
        return DataProviderResult(
            source=source,
            status=STATUS_EMPTY_HISTORY,
            data=df,
            error_type=ERROR_EMPTY_HISTORY,
            message="Historico vazio para o ativo e periodo informados.",
        )
    if len(df) < min_rows:
        logger.warning(
            "Historico insuficiente: ticker=%s periodo=%s fonte=%s erro=%s contexto=%s",
            ticker,
            period,
            source,
            ERROR_INSUFFICIENT_HISTORY,
            context,
        )
        return DataProviderResult(
            source=source,
            status=STATUS_INSUFFICIENT_HISTORY,
            data=df,
            error_type=ERROR_INSUFFICIENT_HISTORY,
            message="Historico insuficiente para calculo.",
        )
    return DataProviderResult(source=source, status=STATUS_OK, data=_normalize_history(df))


def controlled_error_result(
    *,
    source: str,
    ticker: str,
    operation: str,
    exc: Exception,
    period: str | None = None,
    context: str = "data_provider",
) -> DataProviderResult:
    error_type = _controlled_error_type(exc)
    status = (
        STATUS_PROVIDER_UNAVAILABLE
        if error_type in (ERROR_PROVIDER_UNAVAILABLE, ERROR_TIMEOUT)
        else STATUS_CONTROLLED_ERROR
    )
    logger.warning(
        "Falha controlada no provedor: ticker=%s periodo=%s fonte=%s operacao=%s erro=%s contexto=%s",
        ticker,
        period,
        source,
        operation,
        error_type,
        context,
    )
    return DataProviderResult(
        source=source,
        status=status,
        data=None,
        error_type=error_type,
        message="Falha controlada ao consultar a fonte externa.",
    )


class YFinanceProvider:
    source = SOURCE_YFINANCE

    def get_history(self, ticker: str, period: str) -> DataProviderResult:
        try:
            df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        except Exception as exc:
            return controlled_error_result(
                source=self.source,
                ticker=ticker,
                period=period,
                operation="history",
                exc=exc,
                context="YFinanceProvider.get_history",
            )
        return history_result(
            source=self.source,
            ticker=ticker,
            period=period,
            df=df,
            context="YFinanceProvider.get_history",
        )

    def get_info(self, ticker: str) -> DataProviderResult:
        try:
            info = yf.Ticker(ticker).info or {}
        except Exception as exc:
            return controlled_error_result(
                source=self.source,
                ticker=ticker,
                operation="info",
                exc=exc,
                context="YFinanceProvider.get_info",
            )
        if not info:
            logger.warning(
                "Fundamentos indisponiveis: ticker=%s fonte=%s erro=%s contexto=%s",
                ticker,
                self.source,
                ERROR_UNAVAILABLE,
                "YFinanceProvider.get_info",
            )
            return DataProviderResult(
                source=self.source,
                status=STATUS_UNAVAILABLE,
                data={},
                error_type=ERROR_UNAVAILABLE,
                message="Fundamentos indisponiveis na fonte externa.",
            )
        return DataProviderResult(source=self.source, status=STATUS_OK, data=info)


# Espaço reservado para provedores futuros sem integrar APIs externas nesta fase:
# Alpha Vantage, EODHD, B3 oficial e Cedro/Market Data Cloud podem implementar
# os mesmos metodos e retornar DataProviderResult.
_DEFAULT_PROVIDER = YFinanceProvider()


def get_default_provider() -> YFinanceProvider:
    return _DEFAULT_PROVIDER
