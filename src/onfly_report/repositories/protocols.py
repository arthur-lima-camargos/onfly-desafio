"""Contratos das fontes de dados consumidas pelo ReportBuilder.

As implementações CSV satisfazem estes contratos por estrutura (duck typing verificado pelo type
checker), sem herança. Testes podem usar fontes em memória.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from ..models import RawRow


class ReservationSource(Protocol):
    """Fonte das linhas de reserva, ainda sem conversão de tipos."""

    def read(self) -> list[RawRow]: ...


class RateSource(Protocol):
    """Fonte da tabela moeda -> taxa para BRL."""

    def read(self) -> dict[str, Decimal]: ...
