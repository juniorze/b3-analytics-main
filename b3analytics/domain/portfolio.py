from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Iterable, Mapping


class PortfolioValidationError(ValueError):
    """Erro de validacao de operacoes da carteira."""


@dataclass(frozen=True)
class TransactionInput:
    date: str
    ticker: str
    type: str
    quantity: float
    price: float
    fees: float = 0.0
    broker: str | None = None
    asset_class: str = "ACAO"
    notes: str | None = None


@dataclass(frozen=True)
class Transaction(TransactionInput):
    id: int | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class Position:
    ticker: str
    quantity: float
    average_price: float
    total_cost: float


@dataclass(frozen=True)
class RealizedPnL:
    ticker: str
    realized_pnl: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    positions: list[Position]
    realized_pnl: list[RealizedPnL]


@dataclass(frozen=True)
class PortfolioDashboardRow:
    ticker: str
    quantity: float
    average_price: float
    total_cost: float
    current_price: float | None
    current_value: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    realized_pnl: float
    weight_pct: float | None
    price_status: str


@dataclass(frozen=True)
class PortfolioDashboardTotals:
    current_value: float
    total_cost: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float
    assets_count: int
    missing_quotes_count: int


@dataclass(frozen=True)
class PortfolioDashboard:
    rows: list[PortfolioDashboardRow]
    totals: PortfolioDashboardTotals


PORTFOLIO_EXPORT_COLUMNS = [
    "ticker",
    "quantidade",
    "preco_medio",
    "custo_total",
    "preco_atual",
    "valor_atual",
    "pl_nao_realizado_rs",
    "pl_nao_realizado_pct",
    "pl_realizado_rs",
    "peso_pct",
    "status_cotacao",
]


def normalize_ticker(ticker: object) -> str:
    raw = str(ticker or "").strip().upper()
    if not raw:
        raise PortfolioValidationError("Ticker obrigatorio.")

    if raw.endswith(".SA"):
        raw = raw[:-3]
    elif "." in raw:
        raise PortfolioValidationError("Ticker deve estar sem sufixo ou com sufixo .SA.")

    if not raw.isalnum():
        raise PortfolioValidationError("Ticker deve conter apenas letras e numeros.")
    if len(raw) < 5 or len(raw) > 7:
        raise PortfolioValidationError("Ticker deve ter formato valido para acoes da B3.")

    return f"{raw}.SA"


def normalize_transaction(raw: TransactionInput | Transaction | dict) -> TransactionInput:
    if isinstance(raw, TransactionInput):
        data = {
            "date": raw.date,
            "ticker": raw.ticker,
            "type": raw.type,
            "quantity": raw.quantity,
            "price": raw.price,
            "fees": raw.fees,
            "broker": raw.broker,
            "asset_class": raw.asset_class,
            "notes": raw.notes,
        }
    else:
        data = dict(raw)

    operation_date = str(data.get("date") or "").strip()
    try:
        date.fromisoformat(operation_date)
    except ValueError as exc:
        raise PortfolioValidationError("Data invalida. Use o formato YYYY-MM-DD.") from exc

    operation_type = str(data.get("type") or "").strip().upper()
    if operation_type not in {"BUY", "SELL"}:
        raise PortfolioValidationError("Tipo deve ser BUY ou SELL.")

    quantity = _positive_float(data.get("quantity"), "Quantidade")
    price = _positive_float(data.get("price"), "Preco")
    fees = _non_negative_float(data.get("fees", 0), "Taxas")

    asset_class = str(data.get("asset_class") or "ACAO").strip().upper()
    if asset_class != "ACAO":
        raise PortfolioValidationError("Nesta fase, apenas asset_class ACAO e permitido.")

    return TransactionInput(
        date=operation_date,
        ticker=normalize_ticker(data.get("ticker")),
        type=operation_type,
        quantity=quantity,
        price=price,
        fees=fees,
        broker=_clean_optional_text(data.get("broker")),
        asset_class=asset_class,
        notes=_clean_optional_text(data.get("notes")),
    )


def calculate_portfolio(transactions: Iterable[TransactionInput | Transaction | dict]) -> PortfolioSnapshot:
    state: dict[str, dict[str, float]] = {}
    normalized_transactions = [
        (index, normalize_transaction(item), getattr(item, "id", None))
        for index, item in enumerate(transactions)
    ]

    for _, transaction, _ in sorted(
        normalized_transactions,
        key=lambda item: (item[1].date, item[2] if item[2] is not None else item[0]),
    ):
        ticker_state = state.setdefault(
            transaction.ticker,
            {"quantity": 0.0, "average_price": 0.0, "total_cost": 0.0, "realized_pnl": 0.0},
        )

        if transaction.type == "BUY":
            purchase_cost = transaction.quantity * transaction.price + transaction.fees
            new_quantity = ticker_state["quantity"] + transaction.quantity
            ticker_state["total_cost"] += purchase_cost
            ticker_state["quantity"] = new_quantity
            ticker_state["average_price"] = ticker_state["total_cost"] / new_quantity
            continue

        if transaction.quantity > ticker_state["quantity"] + 1e-9:
            raise PortfolioValidationError(
                f"Operacao SELL de {transaction.ticker} maior que a posicao atual."
            )

        previous_average = ticker_state["average_price"]
        lowered_cost = transaction.quantity * previous_average
        net_sale_value = transaction.quantity * transaction.price - transaction.fees
        ticker_state["realized_pnl"] += net_sale_value - lowered_cost
        ticker_state["quantity"] -= transaction.quantity

        if ticker_state["quantity"] <= 1e-9:
            ticker_state["quantity"] = 0.0
            ticker_state["average_price"] = 0.0
            ticker_state["total_cost"] = 0.0
        else:
            ticker_state["total_cost"] -= lowered_cost
            ticker_state["average_price"] = previous_average

    positions = [
        Position(
            ticker=ticker,
            quantity=values["quantity"],
            average_price=values["average_price"],
            total_cost=values["total_cost"],
        )
        for ticker, values in state.items()
        if values["quantity"] > 1e-9
    ]
    realized = [
        RealizedPnL(ticker=ticker, realized_pnl=values["realized_pnl"])
        for ticker, values in state.items()
        if abs(values["realized_pnl"]) > 1e-9
    ]

    return PortfolioSnapshot(
        positions=sorted(positions, key=lambda item: item.ticker),
        realized_pnl=sorted(realized, key=lambda item: item.ticker),
    )


def calculate_portfolio_dashboard(
    snapshot: PortfolioSnapshot,
    current_prices: Mapping[str, object] | None = None,
) -> PortfolioDashboard:
    prices = current_prices or {}
    realized_by_ticker = {item.ticker: item.realized_pnl for item in snapshot.realized_pnl}

    base_rows: list[PortfolioDashboardRow] = []
    available_market_value = 0.0
    available_cost = 0.0
    total_unrealized = 0.0
    missing_quotes = 0

    for position in snapshot.positions:
        current_price = _extract_current_price(prices.get(position.ticker))
        if current_price is None:
            missing_quotes += 1
            base_rows.append(
                PortfolioDashboardRow(
                    ticker=position.ticker,
                    quantity=position.quantity,
                    average_price=position.average_price,
                    total_cost=position.total_cost,
                    current_price=None,
                    current_value=None,
                    unrealized_pnl=None,
                    unrealized_pnl_pct=None,
                    realized_pnl=realized_by_ticker.get(position.ticker, 0.0),
                    weight_pct=None,
                    price_status="dados indisponiveis",
                )
            )
            continue

        current_value = position.quantity * current_price
        unrealized_pnl = current_value - position.total_cost
        unrealized_pnl_pct = (
            unrealized_pnl / position.total_cost * 100 if position.total_cost > 0 else 0.0
        )
        available_market_value += current_value
        available_cost += position.total_cost
        total_unrealized += unrealized_pnl
        base_rows.append(
            PortfolioDashboardRow(
                ticker=position.ticker,
                quantity=position.quantity,
                average_price=position.average_price,
                total_cost=position.total_cost,
                current_price=current_price,
                current_value=current_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                realized_pnl=realized_by_ticker.get(position.ticker, 0.0),
                weight_pct=None,
                price_status="disponivel",
            )
        )

    rows = [
        PortfolioDashboardRow(
            **{
                **row.__dict__,
                "weight_pct": (
                    row.current_value / available_market_value * 100
                    if row.current_value is not None and available_market_value > 0
                    else None
                ),
            }
        )
        for row in base_rows
    ]

    totals = PortfolioDashboardTotals(
        current_value=available_market_value,
        total_cost=sum(position.total_cost for position in snapshot.positions),
        unrealized_pnl=total_unrealized,
        unrealized_pnl_pct=(total_unrealized / available_cost * 100 if available_cost > 0 else 0.0),
        realized_pnl=sum(item.realized_pnl for item in snapshot.realized_pnl),
        assets_count=len(snapshot.positions),
        missing_quotes_count=missing_quotes,
    )
    return PortfolioDashboard(rows=rows, totals=totals)


def portfolio_dashboard_to_csv(rows: Iterable[PortfolioDashboardRow]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=PORTFOLIO_EXPORT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "ticker": row.ticker,
                "quantidade": row.quantity,
                "preco_medio": row.average_price,
                "custo_total": row.total_cost,
                "preco_atual": row.current_price,
                "valor_atual": row.current_value,
                "pl_nao_realizado_rs": row.unrealized_pnl,
                "pl_nao_realizado_pct": row.unrealized_pnl_pct,
                "pl_realizado_rs": row.realized_pnl,
                "peso_pct": row.weight_pct,
                "status_cotacao": row.price_status,
            }
        )
    return output.getvalue()


def _positive_float(value: object, label: str) -> float:
    number = _to_float(value, label)
    if number <= 0:
        raise PortfolioValidationError(f"{label} deve ser maior que zero.")
    return number


def _non_negative_float(value: object, label: str) -> float:
    number = _to_float(0 if value in (None, "") else value, label)
    if number < 0:
        raise PortfolioValidationError(f"{label} deve ser maior ou igual a zero.")
    return number


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise PortfolioValidationError(f"{label} deve ser numerico.") from exc


def _clean_optional_text(value: object) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


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
