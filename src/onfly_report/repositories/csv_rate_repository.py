"""Leitura da tabela de câmbio para BRL."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from ..exceptions import InputFileError
from ..number_format import PLAIN_RATE, parse_plain_decimal

REQUIRED_COLUMNS = ("currency", "rate_to_brl")


class CsvRateRepository:
    """Carrega moeda -> taxa para BRL a partir de um CSV."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> dict[str, Decimal]:
        rates: dict[str, Decimal] = {}
        try:
            # utf-8-sig ignora o BOM que o Excel grava no início de exportações em UTF-8.
            with self._path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
                if missing:
                    raise InputFileError(f"colunas obrigatórias ausentes em {self._path}: {', '.join(missing)}")

                for values in reader:
                    if None in values or None in values.values():
                        raise InputFileError(f"linha {reader.line_num} malformada em {self._path}")
                    currency = (values.get("currency") or "").strip().upper()
                    raw_rate = (values.get("rate_to_brl") or "").strip()
                    if not currency or not raw_rate:
                        raise InputFileError(f"linha de câmbio incompleta em {self._path}")
                    rate = parse_plain_decimal(raw_rate, PLAIN_RATE)
                    if rate is None:
                        raise InputFileError(
                            f"taxa fora do formato decimal simples para {currency} em {self._path}: {raw_rate!r}"
                        )
                    if rate == 0:
                        raise InputFileError(f"taxa zero para {currency} em {self._path}")
                    if currency in rates:
                        raise InputFileError(f"moeda {currency} repetida na tabela de câmbio {self._path}")
                    rates[currency] = rate
        except FileNotFoundError as err:
            raise InputFileError(f"tabela de câmbio não encontrada: {self._path}") from err
        except (OSError, csv.Error, UnicodeDecodeError) as err:
            raise InputFileError(f"falha ao ler {self._path}: {err}") from err

        if not rates:
            raise InputFileError(f"tabela de câmbio vazia: {self._path}")
        return rates
