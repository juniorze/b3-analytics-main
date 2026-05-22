from __future__ import annotations

import pandas as pd

from b3analytics.infrastructure.data_provider import (
    ERROR_CONTROLLED,
    ERROR_EMPTY_HISTORY,
    ERROR_UNAVAILABLE,
    STATUS_CONTROLLED_ERROR,
    STATUS_EMPTY_HISTORY,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    DataProviderResult,
    YFinanceProvider,
    history_result,
)


def test_history_result_com_dataframe_vazio():
    result = history_result(
        source="teste",
        ticker="VAZIO3.SA",
        period="1y",
        df=pd.DataFrame(),
    )

    assert result.source == "teste"
    assert result.status == STATUS_EMPTY_HISTORY
    assert result.error_type == ERROR_EMPTY_HISTORY
    assert result.data.empty


def test_history_result_com_dados_indisponiveis():
    result = history_result(
        source="teste",
        ticker="INDISP3.SA",
        period="1y",
        df=None,
    )

    assert result.status == STATUS_UNAVAILABLE
    assert result.error_type == ERROR_UNAVAILABLE
    assert result.data is None


def test_yfinance_provider_trata_excecao_controlada(monkeypatch):
    class BrokenTicker:
        def __init__(self, ticker: str):
            self.ticker = ticker

        def history(self, period: str, auto_adjust: bool):
            raise RuntimeError("falha simulada")

    monkeypatch.setattr("b3analytics.infrastructure.data_provider.yf.Ticker", BrokenTicker)

    result = YFinanceProvider().get_history("ERRO3.SA", "1y")

    assert result.status == STATUS_CONTROLLED_ERROR
    assert result.error_type == ERROR_CONTROLLED
    assert result.data is None


def test_yfinance_provider_normaliza_historico(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker: str):
            self.ticker = ticker

        def history(self, period: str, auto_adjust: bool):
            return pd.DataFrame(
                {"open": [10, 11], "close": [11, 12], "volume": [100, 200]},
                index=pd.date_range("2026-01-01", periods=2, freq="B", tz="UTC"),
            )

    monkeypatch.setattr("b3analytics.infrastructure.data_provider.yf.Ticker", FakeTicker)

    result = YFinanceProvider().get_history("OK3.SA", "1y")

    assert result.status == STATUS_OK
    assert list(result.data.columns) == ["Open", "Close", "Volume"]
    assert result.data.index.tz is None


def test_wrappers_preservam_compatibilidade(monkeypatch):
    from b3analytics.infrastructure import fetcher

    history = pd.DataFrame(
        {"Open": [10, 11], "Close": [11, 12], "Volume": [100, 200]},
        index=pd.date_range("2026-01-01", periods=2, freq="B"),
    )

    class FakeProvider:
        def get_history(self, ticker: str, period: str):
            return DataProviderResult(source="teste", status=STATUS_OK, data=history.copy())

    monkeypatch.setattr(fetcher, "get_default_provider", lambda: FakeProvider())
    fetcher.get_historico.clear()
    fetcher.get_historico_titled.clear()
    fetcher.get_precos_atuais.clear()

    lower = fetcher.get_historico("OK3.SA", "1A")
    titled = fetcher.get_historico_titled("OK3.SA", "1A")
    quotes = fetcher.get_precos_atuais(("OK3.SA",))

    assert list(lower.columns) == ["open", "close", "volume"]
    assert list(titled.columns) == ["Open", "Close", "Volume"]
    assert quotes["OK3.SA"]["preco"] == 12
