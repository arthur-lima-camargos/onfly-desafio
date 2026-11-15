"""Serialização do relatório no formato do contrato (README, "Contrato do CLI").

Os TypedDict descrevem o JSON documentado: o mypy acusa chave faltando, sobrando ou com tipo
errado. É aqui, e só aqui, que o dinheiro é arredondado.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

from ..models import ReservationStatus
from .aggregation import ReportData

REPORT_VERSION = "1.0"
MONEY_QUANTUM = Decimal("0.01")
FIXED_OFFSET = timezone(timedelta(hours=-3))


class SummaryJson(TypedDict):
    total_reservations: int
    confirmed_reservations: int
    cancelled_reservations: int
    no_show_reservations: int
    total_room_nights: int
    total_amount_brl: str
    average_nightly_rate_brl: str


class MonthJson(TypedDict):
    month: str
    reservations: int
    room_nights: int
    total_brl: str


class HotelJson(TypedDict):
    hotel_id: str
    hotel_name: str
    room_nights: int
    total_brl: str


class ReportJson(TypedDict):
    report_version: str
    generated_at: str
    summary: SummaryJson
    by_month: list[MonthJson]
    top_hotels: list[HotelJson]


def format_money(value: Decimal) -> str:
    """Serializa dinheiro com duas casas, arredondamento half-up."""
    return str(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def format_generated_at(moment: datetime) -> str:
    """Converte o instante para o offset fixo -03:00 do contrato, com precisão de segundos.

    Um datetime sem fuso é lido como hora local da máquina, a regra do astimezone.
    """
    return moment.astimezone(FIXED_OFFSET).isoformat(timespec="seconds")


def serialize(data: ReportData, top_hotel_ids: Sequence[str], generated_at: datetime) -> ReportJson:
    """Monta o JSON: meses em ordem crescente e hotéis na ordem recebida do ranking."""
    return {
        "report_version": REPORT_VERSION,
        "generated_at": format_generated_at(generated_at),
        "summary": {
            "total_reservations": data.total_reservations,
            "confirmed_reservations": data.status_counts.get(ReservationStatus.CONFIRMED, 0),
            "cancelled_reservations": data.status_counts.get(ReservationStatus.CANCELLED, 0),
            "no_show_reservations": data.status_counts.get(ReservationStatus.NO_SHOW, 0),
            "total_room_nights": data.billable.room_nights,
            "total_amount_brl": format_money(data.billable.amount_brl),
            "average_nightly_rate_brl": format_money(data.billable.average_nightly_rate_brl),
        },
        "by_month": [
            {
                "month": month,
                "reservations": totals.reservations,
                "room_nights": totals.room_nights,
                "total_brl": format_money(totals.amount_brl),
            }
            for month, totals in sorted(data.by_month.items())
        ],
        "top_hotels": [
            {
                "hotel_id": hotel_id,
                "hotel_name": data.hotel_names[hotel_id],
                "room_nights": data.by_hotel[hotel_id].room_nights,
                "total_brl": format_money(data.by_hotel[hotel_id].amount_brl),
            }
            for hotel_id in top_hotel_ids
        ],
    }
