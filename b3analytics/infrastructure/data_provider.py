from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)


SOURCE_YFINANCE = "yfinance"
SOURCE_ALPHA_VANTAGE = "alpha_vantage"

STATUS_OK = "OK"
STATUS_MISSING_API_KEY = "MISSING_API_KEY"
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_EMPTY = "EMPTY"
STATUS_ERROR = "ERROR"
STATUS_UNAVAILABLE = STATUS_ERROR
STATUS_EMPTY_HISTORY = STATUS_EMPTY
STATUS_INSUFFICIENT_HISTORY = STATUS_EMPTY
STATUS_MISSING_QUOTE = STATUS_EMPTY
STATUS_PROVIDER_UNAVAILABLE = STATUS_ERROR
STATUS_CONTROLLED_ERROR = STATUS_ERROR

ERROR_UNAVAILABLE = "dados_indisponiveis"
ERROR_EMPTY_HISTORY = "historico_vazio"
ERROR_INSUFFICIENT_HISTORY = "historico_insuficiente"
ERROR_MISSING_QUOTE = "cotacao_ausente"
ERROR_PROVIDER_UNAVAILABLE = "fonte_externa_indisponivel"
ERROR_MISSING_API_KEY = "api_key_ausente"
ERROR_RATE_LIMITED = "limite_requisicoes"
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


class AlphaVantageProvider:
    source = SOURCE_ALPHA_VANTAGE
    endpoint = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, timeout: int = 15) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def _api_key(self) -> str | None:
        return self.api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")

    def get_history(self, ticker: str, period: str) -> DataProviderResult:
        api_key = self._api_key()
        if not api_key:
            logger.warning(
                "Alpha Vantage sem chave configurada: ticker=%s periodo=%s fonte=%s erro=%s",
                ticker,
                period,
                self.source,
                ERROR_MISSING_API_KEY,
            )
            return DataProviderResult(
                source=self.source,
                status=STATUS_MISSING_API_KEY,
                data=None,
                error_type=ERROR_MISSING_API_KEY,
                message="Alpha Vantage nao configurado: defina ALPHA_VANTAGE_API_KEY.",
            )

        try:
            response = requests.get(
                self.endpoint,
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": _alpha_vantage_symbol(ticker),
                    "outputsize": "full",
                    "apikey": api_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return controlled_error_result(
                source=self.source,
                ticker=ticker,
                period=period,
                operation="history",
                exc=exc,
                context="AlphaVantageProvider.get_history",
            )

        if _alpha_vantage_rate_limit_message(payload):
            logger.warning(
                "Alpha Vantage limitado: ticker=%s periodo=%s fonte=%s erro=%s",
                ticker,
                period,
                self.source,
                ERROR_RATE_LIMITED,
            )
            return DataProviderResult(
                source=self.source,
                status=STATUS_RATE_LIMITED,
                data=None,
                error_type=ERROR_RATE_LIMITED,
                message="Limite de requisicoes do Alpha Vantage atingido.",
            )

        if payload.get("Error Message"):
            logger.warning(
                "Alpha Vantage retornou erro: ticker=%s periodo=%s fonte=%s erro=%s",
                ticker,
                period,
                self.source,
                ERROR_CONTROLLED,
            )
            return DataProviderResult(
                source=self.source,
                status=STATUS_ERROR,
                data=None,
                error_type=ERROR_CONTROLLED,
                message="Alpha Vantage nao retornou dados para o ticker informado.",
            )

        df = _alpha_vantage_daily_dataframe(payload, period)
        return history_result(
            source=self.source,
            ticker=ticker,
            period=period,
            df=df,
            context="AlphaVantageProvider.get_history",
        )


class FallbackDataProvider:
    def __init__(
        self,
        primary: YFinanceProvider | None = None,
        fallback: AlphaVantageProvider | None = None,
    ) -> None:
        self.primary = primary or YFinanceProvider()
        self.fallback = fallback or AlphaVantageProvider()
        self.source = self.primary.source

    def get_history(self, ticker: str, period: str) -> DataProviderResult:
        primary_result = self.primary.get_history(ticker, period)
        if primary_result.ok:
            return primary_result

        fallback_result = self.fallback.get_history(ticker, period)
        logger.warning(
            "Fallback de dados executado: ticker=%s periodo=%s fonte=%s status=%s erro=%s",
            ticker,
            period,
            fallback_result.source,
            fallback_result.status,
            fallback_result.error_type,
        )
        return fallback_result if fallback_result.ok else primary_result

    def get_primary_history(self, ticker: str, period: str) -> DataProviderResult:
        return self.primary.get_history(ticker, period)

    def get_info(self, ticker: str) -> DataProviderResult:
        return self.primary.get_info(ticker)


def _alpha_vantage_symbol(ticker: str) -> str:
    if ticker.endswith(".SA"):
        return f"{ticker[:-3]}.SAO"
    return ticker


def _alpha_vantage_rate_limit_message(payload: dict) -> str | None:
    for key in ("Note", "Information"):
        value = str(payload.get(key, ""))
        lowered = value.lower()
        if "rate limit" in lowered or "frequency" in lowered or "standard api call" in lowered:
            return value
    return None


def _alpha_vantage_daily_dataframe(payload: dict, period: str) -> pd.DataFrame:
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        return pd.DataFrame()

    rows: list[dict[str, float]] = []
    index: list[pd.Timestamp] = []
    for date, values in series.items():
        try:
            index.append(pd.Timestamp(date))
            rows.append(
                {
                    "Open": float(values["1. open"]),
                    "High": float(values["2. high"]),
                    "Low": float(values["3. low"]),
                    "Close": float(values["4. close"]),
                    "Volume": float(values["5. volume"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, index=pd.DatetimeIndex(index)).sort_index()
    cutoff = _period_cutoff(period, df.index.max())
    return df.loc[df.index >= cutoff] if cutoff is not None else df


def _period_cutoff(period: str, end: pd.Timestamp) -> pd.Timestamp | None:
    if period == "max":
        return None
    if period.endswith("mo"):
        return end - pd.DateOffset(months=int(period[:-2]))
    if period.endswith("y"):
        return end - pd.DateOffset(years=int(period[:-1]))
    if period.endswith("d"):
        return end - pd.Timedelta(days=int(period[:-1]))
    return None


_DEFAULT_PROVIDER = FallbackDataProvider()


def get_default_provider() -> FallbackDataProvider:
    return _DEFAULT_PROVIDER
