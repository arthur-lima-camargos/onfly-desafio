"""Agregação das reservas nos números exatos do relatório."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from ..models import Reservation, ReservationStatus
from .currency_converter import convert_to_brl
from .status_policy import is_billable
from .stay_calculator import calculate_room_nights


@dataclass
class Totals:
    """Acumulado de um grupo de reservas faturáveis: o arquivo todo, um mês ou um hotel."""

    reservations: int = 0
    room_nights: int = 0
    amount_brl: Decimal = Decimal("0")

    def add(self, room_nights: int, amount_brl: Decimal) -> None:
        self.reservations += 1
        self.room_nights += room_nights
        self.amount_brl += amount_brl

    @property
    def average_nightly_rate_brl(self) -> Decimal:
        """Valor total dividido pelas noites; sem noites, zero (README)."""
        return self.amount_brl / self.room_nights if self.room_nights else Decimal("0")


@dataclass(frozen=True)
class ReportData:
    """Números do relatório antes de qualquer arredondamento, ordenação ou formatação."""

    total_reservations: int
    status_counts: Mapping[ReservationStatus, int]
    billable: Totals
    by_month: Mapping[str, Totals]
    by_hotel: Mapping[str, Totals]
    hotel_names: Mapping[str, str]


def aggregate(reservations: Sequence[Reservation], rates: dict[str, Decimal]) -> ReportData:
    """Conta todas as reservas por status e soma noites e valor em BRL só das faturáveis.

    A reserva entra inteira no mês do check-in, mesmo quando a estadia cruza a virada do mês.
    """
    billable = Totals()
    by_month: defaultdict[str, Totals] = defaultdict(Totals)
    by_hotel: defaultdict[str, Totals] = defaultdict(Totals)
    hotel_names: dict[str, str] = {}

    for reservation in reservations:
        # Primeiro nome lido por hotel, na ordem do arquivo; nomes divergentes viram aviso.
        hotel_names.setdefault(reservation.hotel_id, reservation.hotel_name)
        if not is_billable(reservation.status):
            continue

        room_nights = calculate_room_nights(reservation.checkin, reservation.checkout, reservation.rooms)
        amount_brl = convert_to_brl(reservation.amount, reservation.currency, rates)
        month = reservation.checkin.strftime("%Y-%m")
        for totals in (billable, by_month[month], by_hotel[reservation.hotel_id]):
            totals.add(room_nights, amount_brl)

    return ReportData(
        total_reservations=len(reservations),
        status_counts=Counter(reservation.status for reservation in reservations),
        billable=billable,
        by_month=dict(by_month),
        by_hotel=dict(by_hotel),
        hotel_names=hotel_names,
    )
