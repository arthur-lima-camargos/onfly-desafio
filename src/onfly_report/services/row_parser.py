"""Conversão de uma linha do CSV para o modelo de reserva."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from ..exceptions import InputFileError
from ..models import RawRow, Reservation, ReservationStatus
from ..number_format import PLAIN_AMOUNT, PLAIN_ROOMS, parse_plain_decimal, parse_plain_int

CIVIL_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# Campos que entram no relatório; vazios tornam a reserva impossível de agregar.
REQUIRED_FIELDS = (
    "reservation_id",
    "hotel_id",
    "hotel_name",
    "checkin_date",
    "checkout_date",
    "rooms",
    "status",
    "currency",
    "amount",
)


class RowParser:
    """Converte a linha crua em Reservation.

    O arquivo de entrada é consistente; falhas de formato são erro de arquivo, não dado a
    ser descartado.
    """

    def parse(self, raw: RawRow) -> Reservation:
        try:
            return self._parse(raw)
        except ValueError as err:
            raise InputFileError(f"linha {raw.line_number} inválida: {err}") from err

    def _parse(self, raw: RawRow) -> Reservation:
        values = {key: (value or "").strip() for key, value in raw.values.items()}

        empty = [field for field in REQUIRED_FIELDS if not values.get(field)]
        if empty:
            raise ValueError(f"campos obrigatórios vazios: {', '.join(empty)}")

        checkin = parse_civil_date(values["checkin_date"], "checkin_date")
        checkout = parse_civil_date(values["checkout_date"], "checkout_date")
        if checkout < checkin:
            raise ValueError(f"checkout_date {checkout} é anterior a checkin_date {checkin}")

        return Reservation(
            reservation_id=values["reservation_id"],
            traveler_name=values.get("traveler_name", ""),
            company_id=values.get("company_id", ""),
            hotel_id=values["hotel_id"],
            hotel_name=values["hotel_name"],
            city=values.get("city", ""),
            country=values.get("country", ""),
            checkin=checkin,
            checkout=checkout,
            rooms=parse_rooms(values["rooms"]),
            status=parse_status(values["status"]),
            currency=values["currency"].upper(),
            amount=parse_amount(values["amount"]),
            payment_method=values.get("payment_method", ""),
            line_number=raw.line_number,
        )


def parse_civil_date(text: str, field: str) -> date:
    """Aceita só YYYY-MM-DD; date.fromisoformat sozinho aceitaria 20250110 e 2025-W02-5."""
    if not CIVIL_DATE.fullmatch(text):
        raise ValueError(f"{field} fora do formato YYYY-MM-DD: {text!r}")
    try:
        return date.fromisoformat(text)
    except ValueError as err:
        raise ValueError(f"{field} não é uma data válida: {text!r} ({err})") from err


def parse_rooms(text: str) -> int:
    """Aceita só dígitos: int() sozinho leria "1_0" como 10 quartos."""
    rooms = parse_plain_int(text, PLAIN_ROOMS)
    if rooms is None:
        raise ValueError(f"rooms fora do formato inteiro simples (1 a 4 dígitos, sem sinal): {text!r}")
    if rooms < 1:
        raise ValueError(f"rooms deve ser maior ou igual a 1: {rooms}")
    return rooms


def parse_status(text: str) -> ReservationStatus:
    """Compara exatamente com os status do README; caixa diferente é erro, não é corrigida."""
    try:
        return ReservationStatus(text)
    except ValueError:
        expected = ", ".join(ReservationStatus)
        raise ValueError(f"status desconhecido: {text!r} (esperado: {expected})") from None


def parse_amount(text: str) -> Decimal:
    """Um formato só barra valor negativo, NaN, infinito, notação científica e estouro de precisão."""
    amount = parse_plain_decimal(text, PLAIN_AMOUNT)
    if amount is None:
        raise ValueError(
            "amount fora do formato decimal simples "
            f"(até 15 dígitos inteiros e 6 decimais, sem sinal nem expoente): {text!r}"
        )
    return amount
