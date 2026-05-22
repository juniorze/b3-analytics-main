from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from b3analytics.domain.portfolio import (
    PortfolioSnapshot,
    Transaction,
    TransactionInput,
    calculate_portfolio,
    normalize_transaction,
)


def get_default_db_path() -> Path:
    return Path.home() / ".b3analytics" / "portfolio.sqlite3"


class PortfolioStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('BUY', 'SELL')),
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    price REAL NOT NULL CHECK(price > 0),
                    fees REAL NOT NULL DEFAULT 0 CHECK(fees >= 0),
                    broker TEXT,
                    asset_class TEXT NOT NULL DEFAULT 'ACAO',
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_transaction(self, transaction: TransactionInput | dict) -> Transaction:
        return self.add_transactions([transaction])[0]

    def add_transactions(self, transactions: Iterable[TransactionInput | dict]) -> list[Transaction]:
        normalized = [normalize_transaction(item) for item in transactions]
        existing = self.list_transactions()

        running: list[TransactionInput | Transaction] = [*existing]
        for transaction in normalized:
            calculate_portfolio([*running, transaction])
            running.append(transaction)

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        inserted: list[Transaction] = []
        with self._connect() as conn:
            try:
                for transaction in normalized:
                    cursor = conn.execute(
                        """
                        INSERT INTO transactions (
                            date, ticker, type, quantity, price, fees,
                            broker, asset_class, notes, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            transaction.date,
                            transaction.ticker,
                            transaction.type,
                            transaction.quantity,
                            transaction.price,
                            transaction.fees,
                            transaction.broker,
                            transaction.asset_class,
                            transaction.notes,
                            created_at,
                        ),
                    )
                    inserted.append(
                        Transaction(
                            **transaction.__dict__,
                            id=int(cursor.lastrowid),
                            created_at=created_at,
                        )
                    )
            except Exception:
                conn.rollback()
                raise
        return inserted

    def list_transactions(self) -> list[Transaction]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, date, ticker, type, quantity, price, fees,
                    broker, asset_class, notes, created_at
                FROM transactions
                ORDER BY date ASC, id ASC
                """
            ).fetchall()

        return [
            Transaction(
                id=int(row["id"]),
                date=str(row["date"]),
                ticker=str(row["ticker"]),
                type=str(row["type"]),
                quantity=float(row["quantity"]),
                price=float(row["price"]),
                fees=float(row["fees"]),
                broker=row["broker"],
                asset_class=str(row["asset_class"]),
                notes=row["notes"],
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def get_snapshot(self) -> PortfolioSnapshot:
        return calculate_portfolio(self.list_transactions())

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
