"""Conversão de valores para BRL."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from ..exceptions import InputFileError
from ..models import Reservation


def convert_to_brl(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Converte um valor na moeda informada para BRL usando a taxa da tabela."""
    return amount * rates[currency]


def ensure_rates_available(reservations: Iterable[Reservation], rates: dict[str, Decimal]) -> None:
    """Falha antes de agregar se alguma reserva, de qualquer status, usa moeda sem taxa.

    O README garante taxa para todas as moedas do dataset; uma ausente indica arquivo inconsistente.
    """
    missing: dict[str, list[int]] = defaultdict(list)
    for reservation in reservations:
        if reservation.currency not in rates:
            missing[reservation.currency].append(reservation.line_number)

    if missing:
        details = "; ".join(
            f"{currency} (linhas {', '.join(map(str, lines))})" for currency, lines in sorted(missing.items())
        )
        raise InputFileError(f"moeda sem taxa de câmbio: {details}")
