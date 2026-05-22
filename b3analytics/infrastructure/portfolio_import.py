from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable

from b3analytics.domain.portfolio import (
    PortfolioValidationError,
    Transaction,
    TransactionInput,
    calculate_portfolio,
    normalize_transaction,
)

CSV_COLUMNS = [
    "date",
    "ticker",
    "type",
    "quantity",
    "price",
    "fees",
    "broker",
    "asset_class",
    "notes",
]


@dataclass(frozen=True)
class CsvImportError:
    line: int | None
    message: str


@dataclass(frozen=True)
class CsvImportPreview:
    valid_rows: list[TransactionInput]
    errors: list[CsvImportError]

    @property
    def can_import(self) -> bool:
        return bool(self.valid_rows) and not self.errors


def parse_portfolio_csv(
    content: str | bytes,
    existing_transactions: Iterable[Transaction | TransactionInput] | None = None,
) -> CsvImportPreview:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(StringIO(text))
    errors: list[CsvImportError] = []
    valid_rows: list[TransactionInput] = []

    if reader.fieldnames is None:
        return CsvImportPreview([], [CsvImportError(None, "CSV vazio ou sem cabecalho.")])

    fieldnames = [field.strip() for field in reader.fieldnames]
    missing = [column for column in CSV_COLUMNS if column not in fieldnames]
    if missing:
        return CsvImportPreview(
            [],
            [CsvImportError(None, f"Colunas obrigatorias ausentes: {', '.join(missing)}.")],
        )

    running: list[Transaction | TransactionInput] = list(existing_transactions or [])
    for line_number, row in enumerate(reader, start=2):
        try:
            normalized = normalize_transaction({column: row.get(column) for column in CSV_COLUMNS})
            calculate_portfolio([*running, normalized])
        except PortfolioValidationError as exc:
            errors.append(CsvImportError(line_number, str(exc)))
            continue

        valid_rows.append(normalized)
        running.append(normalized)

    return CsvImportPreview(valid_rows, errors)
