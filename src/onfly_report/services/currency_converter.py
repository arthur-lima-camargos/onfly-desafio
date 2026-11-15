"""Conversão de valores para BRL."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from ..exceptions import InputFileError
from ..models import Reservation
from .status_policy import is_billable


def convert_to_brl(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Converte um valor na moeda informada para BRL usando a taxa da tabela."""
    return amount * rates[currency]


def ensure_rates_available(reservations: Iterable[Reservation], rates: dict[str, Decimal]) -> None:
    """Falha antes de agregar se alguma reserva faturável usa moeda sem taxa.

    Sem a taxa o total não pode ser calculado. Reservas fora dos totais não entram aqui: ver
    unbilled_currencies_without_rate.
    """
    missing = describe_missing_rates((row for row in reservations if is_billable(row.status)), rates)
    if missing:
        raise InputFileError(f"moeda sem taxa de câmbio: {missing}")


def unbilled_currencies_without_rate(reservations: Iterable[Reservation], rates: dict[str, Decimal]) -> list[str]:
    """Aviso para reserva cancelada ou no-show em moeda sem taxa.

    O relatório não converte essas reservas, então ele é calculável; a moeda fora da tabela ainda
    é um sinal de exportação inconsistente para quem opera.
    """
    missing = describe_missing_rates((row for row in reservations if not is_billable(row.status)), rates)
    if not missing:
        return []
    return [f"moeda sem taxa de câmbio em reserva não faturável, fora dos totais: {missing}"]


def describe_missing_rates(reservations: Iterable[Reservation], rates: dict[str, Decimal]) -> str:
    """Moedas sem taxa e as linhas onde aparecem, ex.: "GBP (linhas 3, 5); JPY (linhas 4)"."""
    lines_by_currency: dict[str, list[int]] = defaultdict(list)
    for reservation in reservations:
        if reservation.currency not in rates:
            lines_by_currency[reservation.currency].append(reservation.line_number)

    return "; ".join(
        f"{currency} (linhas {', '.join(map(str, lines))})" for currency, lines in sorted(lines_by_currency.items())
    )
