"""Construção do relatório consolidado."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import localcontext

from ..number_format import MONEY_PRECISION
from ..repositories.protocols import RateSource, ReservationSource
from .aggregation import aggregate
from .consistency_checks import find_inconsistencies
from .currency_converter import ensure_rates_available, unbilled_currencies_without_rate
from .hotel_ranking import rank_hotels
from .report_serializer import FIXED_OFFSET, ReportJson, serialize
from .row_parser import RowParser

logger = logging.getLogger(__name__)


class ReportBuilder:
    """Orquestra as etapas: ler, converter tipos, validar, agregar, ordenar e serializar."""

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

    def build(self) -> ReportJson:
        # A precisão vale para toda a conta de dinheiro, da conversão ao quantize da serialização.
        with localcontext(prec=MONEY_PRECISION):
            return self._build()

    def _build(self) -> ReportJson:
        reservations = RowParser().parse_all(self._reservation_repository.read())
        rates = self._rate_repository.read()
        ensure_rates_available(reservations, rates)
        for message in (*find_inconsistencies(reservations), *unbilled_currencies_without_rate(reservations, rates)):
            logger.warning(message)

        data = aggregate(reservations, rates)
        # O ranking usa o total exato de cada hotel, antes do arredondamento da serialização.
        top_hotel_ids = rank_hotels(
            {hotel_id: totals.amount_brl for hotel_id, totals in data.by_hotel.items()}, self._top_n
        )
        return serialize(data, top_hotel_ids, self._now or datetime.now(FIXED_OFFSET))
