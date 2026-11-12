"""Ranking de hotéis por valor faturado."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal


def rank_hotels(totals_brl: Mapping[str, Decimal], top_n: int) -> list[str]:
    """Devolve os hotel_id dos top_n hotéis: total decrescente, empate por hotel_id crescente.

    A ordem usa o total exato, não o serializado: arredondar é só na saída. Hotéis que diferem em
    fração de centavo podem aparecer com o mesmo total_brl e fora da ordem de hotel_id.
    """
    return sorted(totals_brl, key=lambda hotel_id: (-totals_brl[hotel_id], hotel_id))[:top_n]
