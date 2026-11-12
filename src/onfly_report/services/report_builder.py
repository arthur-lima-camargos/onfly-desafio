"""Construção do relatório consolidado."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from ..models import ReservationStatus
from ..repositories.protocols import RateSource, ReservationSource
from .consistency_checks import find_inconsistencies
from .currency_converter import convert_to_brl, ensure_rates_available
from .hotel_ranking import rank_hotels
from .row_parser import RowParser
from .status_policy import is_billable
from .stay_calculator import calculate_room_nights

MONEY_QUANTUM = Decimal("0.01")
FIXED_OFFSET = timezone(timedelta(hours=-3))

logger = logging.getLogger(__name__)


def format_money(value: Decimal) -> str:
    """Serializa dinheiro com duas casas, arredondamento half-up."""
    return str(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


class ReportBuilder:
    """Orquestra leitura, conversão e agregação."""

    def __init__(
        self,
        reservation_repository: ReservationSource,
        rate_repository: RateSource,
        top_n: int = 5,
        now: datetime | None = None,
    ) -> None:
        self._reservation_repository = reservation_repository
        self._rate_repository = rate_repository
        self._top_n = top_n
        self._now = now

    def build(self) -> dict:
        parser = RowParser()
        reservations = [parser.parse(raw) for raw in self._reservation_repository.read()]
        rates = self._rate_repository.read()
        ensure_rates_available(reservations, rates)
        for message in find_inconsistencies(reservations):
            logger.warning(message)

        # Primeiro nome lido por hotel, na ordem do arquivo; nomes divergentes já foram avisados.
        hotel_names: dict[str, str] = {}
        for reservation in reservations:
            hotel_names.setdefault(reservation.hotel_id, reservation.hotel_name)

        status_counts = Counter(reservation.status for reservation in reservations)

        confirmed = [row for row in reservations if is_billable(row.status)]

        monthly: dict[str, dict] = defaultdict(
            lambda: {"reservations": 0, "room_nights": 0, "amount": Decimal("0")}
        )
        hotels: dict[str, dict] = defaultdict(lambda: {"room_nights": 0, "amount": Decimal("0")})

        total_nights = 0
        total_amount = Decimal("0")

        for row in confirmed:
            room_nights = calculate_room_nights(row.checkin, row.checkout, row.rooms)
            amount_brl = convert_to_brl(row.amount, row.currency, rates)

            total_nights += room_nights
            total_amount += amount_brl

            month_key = row.checkin.strftime("%Y-%m")
            monthly[month_key]["reservations"] += 1
            monthly[month_key]["room_nights"] += room_nights
            monthly[month_key]["amount"] += amount_brl

            hotels[row.hotel_id]["room_nights"] += room_nights
            hotels[row.hotel_id]["amount"] += amount_brl

        average_nightly_rate = (
            total_amount / Decimal(total_nights) if total_nights > 0 else Decimal("0")
        )

        by_month = [
            {
                "month": month,
                "reservations": data["reservations"],
                "room_nights": data["room_nights"],
                "total_brl": format_money(data["amount"]),
            }
            for month, data in sorted(monthly.items())
        ]

        ranked_hotel_ids = rank_hotels(
            {hotel_id: data["amount"] for hotel_id, data in hotels.items()}, self._top_n
        )
        top_hotels = [
            {
                "hotel_id": hotel_id,
                "hotel_name": hotel_names[hotel_id],
                "room_nights": hotels[hotel_id]["room_nights"],
                "total_brl": format_money(hotels[hotel_id]["amount"]),
            }
            for hotel_id in ranked_hotel_ids
        ]

        now = self._now or datetime.now(FIXED_OFFSET)

        return {
            "report_version": "1.0",
            "generated_at": now.isoformat(timespec="seconds"),
            "summary": {
                "total_reservations": len(reservations),
                "confirmed_reservations": status_counts[ReservationStatus.CONFIRMED],
                "cancelled_reservations": status_counts[ReservationStatus.CANCELLED],
                "no_show_reservations": status_counts[ReservationStatus.NO_SHOW],
                "total_room_nights": total_nights,
                "total_amount_brl": format_money(total_amount),
                "average_nightly_rate_brl": format_money(average_nightly_rate),
            },
            "by_month": by_month,
            "top_hotels": top_hotels,
        }
