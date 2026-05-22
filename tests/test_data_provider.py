from __future__ import annotations

import pandas as pd

from b3analytics.infrastructure.data_provider import (
    ERROR_CONTROLLED,
    ERROR_EMPTY_HISTORY,
    ERROR_MISSING_API_KEY,
    ERROR_RATE_LIMITED,
    ERROR_UNAVAILABLE,
    STATUS_CONTROLLED_ERROR,
    STATUS_EMPTY,
    STATUS_EMPTY_HISTORY,
    STATUS_ERROR,
    STATUS_MISSING_API_KEY,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_UNAVAILABLE,
    AlphaVantageProvider,
    DataProviderResult,
    FallbackDataProvider,
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


def test_alpha_vantage_sem_chave_retorna_falha_controlada(monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    result = AlphaVantageProvider().get_history("PETR4.SA", "1y")

    assert result.source == "alpha_vantage"
    assert result.status == STATUS_MISSING_API_KEY
    assert result.error_type == ERROR_MISSING_API_KEY
    assert result.data is None


def test_alpha_vantage_resposta_valida_vira_dataframe_compativel(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "Time Series (Daily)": {
                    "2026-01-02": {
                        "1. open": "10.0",
                        "2. high": "12.0",
                        "3. low": "9.0",
                        "4. close": "11.0",
                        "5. volume": "1000",
                    },
                    "2026-01-05": {
                        "1. open": "11.0",
                        "2. high": "13.0",
                        "3. low": "10.0",
                        "4. close": "12.0",
                        "5. volume": "2000",
                    },
                }
            }

    def fake_get(url, params, timeout):
        assert params["symbol"] == "PETR4.SAO"
        assert params["apikey"] == "teste"
        return FakeResponse()

    monkeypatch.setattr("b3analytics.infrastructure.data_provider.requests.get", fake_get)

    result = AlphaVantageProvider(api_key="teste").get_history("PETR4.SA", "1y")

    assert result.status == STATUS_OK
    assert list(result.data.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result.data.index.tz is None
    assert result.data["Close"].tolist() == [11.0, 12.0]


def test_alpha_vantage_resposta_vazia_vira_empty(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    monkeypatch.setattr(
        "b3analytics.infrastructure.data_provider.requests.get",
        lambda url, params, timeout: FakeResponse(),
    )

    result = AlphaVantageProvider(api_key="teste").get_history("VAZIO3.SA", "1y")

    assert result.status == STATUS_EMPTY
    assert result.error_type == ERROR_EMPTY_HISTORY
    assert result.data.empty


def test_alpha_vantage_rate_limit_vira_rate_limited(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"Note": "Thank you for using Alpha Vantage. Our standard API call frequency is limited."}

    monkeypatch.setattr(
        "b3analytics.infrastructure.data_provider.requests.get",
        lambda url, params, timeout: FakeResponse(),
    )

    result = AlphaVantageProvider(api_key="teste").get_history("PETR4.SA", "1y")

    assert result.status == STATUS_RATE_LIMITED
    assert result.error_type == ERROR_RATE_LIMITED
    assert result.data is None


def test_fallback_nao_quebra_quando_alpha_vantage_falha():
    class EmptyPrimary:
        source = "yfinance"

        def get_history(self, ticker: str, period: str):
            return DataProviderResult(
                source=self.source,
                status=STATUS_EMPTY,
                data=pd.DataFrame(),
                error_type=ERROR_EMPTY_HISTORY,
            )

        def get_info(self, ticker: str):
            return DataProviderResult(source=self.source, status=STATUS_OK, data={})

    class BrokenFallback:
        source = "alpha_vantage"

        def get_history(self, ticker: str, period: str):
            return DataProviderResult(
                source=self.source,
                status=STATUS_ERROR,
                data=None,
                error_type=ERROR_CONTROLLED,
            )

    result = FallbackDataProvider(
        primary=EmptyPrimary(),
        fallback=BrokenFallback(),
    ).get_history("ERRO3.SA", "1y")

    assert result.source == "yfinance"
    assert result.status == STATUS_EMPTY
    assert result.error_type == ERROR_EMPTY_HISTORY


def test_yfinance_continua_principal_e_nao_chama_fallback():
    history = pd.DataFrame(
        {"Open": [10, 11], "Close": [11, 12], "Volume": [100, 200]},
        index=pd.date_range("2026-01-01", periods=2, freq="B"),
    )

    class OkPrimary:
        source = "yfinance"

        def get_history(self, ticker: str, period: str):
            return DataProviderResult(source=self.source, status=STATUS_OK, data=history)

        def get_info(self, ticker: str):
            return DataProviderResult(source=self.source, status=STATUS_OK, data={})

    class FallbackShouldNotRun:
        source = "alpha_vantage"

        def get_history(self, ticker: str, period: str):
            raise AssertionError("fallback nao deveria ser chamado")

    result = FallbackDataProvider(
        primary=OkPrimary(),
        fallback=FallbackShouldNotRun(),
    ).get_history("OK3.SA", "1y")

    assert result.source == "yfinance"
    assert result.status == STATUS_OK
    assert result.data.equals(history)
