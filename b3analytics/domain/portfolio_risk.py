from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd

from b3analytics.domain.portfolio import PortfolioSnapshot


@dataclass(frozen=True)
class PortfolioRiskLimits:
    max_asset_pct: float = 30.0
    max_group_pct: float = 45.0


@dataclass(frozen=True)
class AssetConcentration:
    ticker: str
    current_value: float
    weight_pct: float
    limit_pct: float
    status: str


@dataclass(frozen=True)
class GroupConcentration:
    group: str
    tickers: tuple[str, ...]
    current_value: float
    weight_pct: float
    limit_pct: float
    status: str


@dataclass(frozen=True)
class PortfolioRiskResult:
    total_priced_value: float
    asset_concentrations: list[AssetConcentration]
    group_concentrations: list[GroupConcentration]
    missing_price_tickers: list[str]
    insufficient_history_tickers: list[str]
    volatility_by_ticker_pct: dict[str, float]
    portfolio_volatility_pct: float | None
    max_drawdown_pct: float | None
    correlation: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def has_market_history(self) -> bool:
        return self.portfolio_volatility_pct is not None or self.max_drawdown_pct is not None


def calculate_portfolio_risk(
    snapshot: PortfolioSnapshot,
    current_prices: Mapping[str, object] | None = None,
    histories: Mapping[str, pd.DataFrame] | None = None,
    groups: Mapping[str, list[str]] | None = None,
    limits: PortfolioRiskLimits | None = None,
) -> PortfolioRiskResult:
    prices = current_prices or {}
    price_by_ticker: dict[str, float] = {}
    missing_price_tickers: list[str] = []

    for position in snapshot.positions:
        current_price = _extract_current_price(prices.get(position.ticker))
        if current_price is None:
            missing_price_tickers.append(position.ticker)
            continue
        price_by_ticker[position.ticker] = current_price

    values_by_ticker = {
        position.ticker: position.quantity * price_by_ticker[position.ticker]
        for position in snapshot.positions
        if position.ticker in price_by_ticker
    }
    total_priced_value = sum(values_by_ticker.values())
    active_limits = limits or PortfolioRiskLimits()

    asset_concentrations = _calculate_asset_concentrations(
        values_by_ticker,
        total_priced_value,
        active_limits,
    )
    group_concentrations = _calculate_group_concentrations(
        values_by_ticker,
        total_priced_value,
        groups or {},
        active_limits,
    )
    history_result = _calculate_market_history(
        snapshot,
        set(values_by_ticker),
        histories or {},
    )

    return PortfolioRiskResult(
        total_priced_value=total_priced_value,
        asset_concentrations=asset_concentrations,
        group_concentrations=group_concentrations,
        missing_price_tickers=sorted(missing_price_tickers),
        insufficient_history_tickers=history_result["insufficient_history_tickers"],
        volatility_by_ticker_pct=history_result["volatility_by_ticker_pct"],
        portfolio_volatility_pct=history_result["portfolio_volatility_pct"],
        max_drawdown_pct=history_result["max_drawdown_pct"],
        correlation=history_result["correlation"],
    )


def _calculate_asset_concentrations(
    values_by_ticker: Mapping[str, float],
    total_priced_value: float,
    limits: PortfolioRiskLimits,
) -> list[AssetConcentration]:
    if total_priced_value <= 0:
        return []

    items = []
    for ticker, current_value in values_by_ticker.items():
        weight_pct = current_value / total_priced_value * 100
        items.append(
            AssetConcentration(
                ticker=ticker,
                current_value=current_value,
                weight_pct=weight_pct,
                limit_pct=limits.max_asset_pct,
                status="acima do limite" if weight_pct > limits.max_asset_pct else "dentro do limite",
            )
        )
    return sorted(items, key=lambda item: item.weight_pct, reverse=True)


def _calculate_group_concentrations(
    values_by_ticker: Mapping[str, float],
    total_priced_value: float,
    groups: Mapping[str, list[str]],
    limits: PortfolioRiskLimits,
) -> list[GroupConcentration]:
    if total_priced_value <= 0:
        return []

    group_rows: list[GroupConcentration] = []
    for group, tickers in groups.items():
        group_tickers = tuple(ticker for ticker in tickers if ticker in values_by_ticker)
        if not group_tickers:
            continue
        current_value = sum(values_by_ticker[ticker] for ticker in group_tickers)
        weight_pct = current_value / total_priced_value * 100
        group_rows.append(
            GroupConcentration(
                group=group,
                tickers=group_tickers,
                current_value=current_value,
                weight_pct=weight_pct,
                limit_pct=limits.max_group_pct,
                status="acima do limite" if weight_pct > limits.max_group_pct else "dentro do limite",
            )
        )
    return sorted(group_rows, key=lambda item: item.weight_pct, reverse=True)


def _calculate_market_history(
    snapshot: PortfolioSnapshot,
    priced_tickers: set[str],
    histories: Mapping[str, pd.DataFrame],
) -> dict[str, object]:
    returns_by_ticker: dict[str, pd.Series] = {}
    close_by_ticker: dict[str, pd.Series] = {}
    insufficient_history_tickers: list[str] = []

    for position in snapshot.positions:
        if position.ticker not in priced_tickers:
            continue
        closes = _close_prices(histories.get(position.ticker))
        daily_returns = closes.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        if len(daily_returns) < 2:
            insufficient_history_tickers.append(position.ticker)
            continue
        returns_by_ticker[position.ticker] = daily_returns
        close_by_ticker[position.ticker] = closes

    volatility_by_ticker_pct = {
        ticker: float(returns.std() * np.sqrt(252) * 100)
        for ticker, returns in returns_by_ticker.items()
    }
    portfolio_values = _portfolio_history_value(snapshot, close_by_ticker)
    portfolio_returns = portfolio_values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    portfolio_volatility_pct = (
        float(portfolio_returns.std() * np.sqrt(252) * 100)
        if len(portfolio_returns) >= 2
        else None
    )
    max_drawdown_pct = _max_drawdown_pct(portfolio_values)
    correlation = _correlation_matrix(returns_by_ticker)

    return {
        "insufficient_history_tickers": sorted(insufficient_history_tickers),
        "volatility_by_ticker_pct": volatility_by_ticker_pct,
        "portfolio_volatility_pct": portfolio_volatility_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "correlation": correlation,
    }


def _portfolio_history_value(
    snapshot: PortfolioSnapshot,
    close_by_ticker: Mapping[str, pd.Series],
) -> pd.Series:
    weighted_closes = []
    quantity_by_ticker = {position.ticker: position.quantity for position in snapshot.positions}
    for ticker, closes in close_by_ticker.items():
        weighted_closes.append(closes * quantity_by_ticker[ticker])
    if not weighted_closes:
        return pd.Series(dtype=float)
    return pd.concat(weighted_closes, axis=1).dropna().sum(axis=1)


def _correlation_matrix(returns_by_ticker: Mapping[str, pd.Series]) -> pd.DataFrame:
    if len(returns_by_ticker) < 2:
        return pd.DataFrame()
    aligned = pd.DataFrame(returns_by_ticker).dropna()
    if len(aligned) < 2:
        return pd.DataFrame()
    return aligned.corr()


def _max_drawdown_pct(values: pd.Series) -> float | None:
    clean_values = values.dropna()
    if len(clean_values) < 2:
        return None
    cumulative_max = clean_values.cummax()
    drawdown = clean_values / cumulative_max - 1
    return float(drawdown.min() * 100)


def _close_prices(df: pd.DataFrame | None) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    close_col = next((column for column in ("close", "Close") if column in df.columns), None)
    if close_col is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[close_col], errors="coerce").dropna()


def _extract_current_price(raw_price: object) -> float | None:
    if isinstance(raw_price, Mapping):
        raw_price = raw_price.get("preco")
    if raw_price in (None, ""):
        return None
    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None
