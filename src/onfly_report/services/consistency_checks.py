"""Inconsistências suspeitas que não impedem o relatório.

Diferente das validações do RowParser (exit 2), aqui o dado é calculável e o relatório segue o
README; o problema só é sinalizado em log para quem opera a exportação.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from ..models import Reservation


def find_inconsistencies(reservations: Sequence[Reservation]) -> list[str]:
    """Devolve uma mensagem por tipo de inconsistência encontrada, na ordem do arquivo."""
    checks = (duplicated_reservation_ids, divergent_hotel_names, multiple_companies)
    return [message for check in checks if (message := check(reservations))]


def duplicated_reservation_ids(reservations: Sequence[Reservation]) -> str | None:
    lines_by_id: dict[str, list[int]] = defaultdict(list)
    for reservation in reservations:
        lines_by_id[reservation.reservation_id].append(reservation.line_number)

    duplicated = {reservation_id: lines for reservation_id, lines in lines_by_id.items() if len(lines) > 1}
    if not duplicated:
        return None
    details = "; ".join(f"{reservation_id} (linhas {join(lines)})" for reservation_id, lines in duplicated.items())
    return f"reservation_id repetido, possível cobrança em dobro: {details}"


def divergent_hotel_names(reservations: Sequence[Reservation]) -> str | None:
    lines_by_name: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for reservation in reservations:
        lines_by_name[reservation.hotel_id][reservation.hotel_name].append(reservation.line_number)

    divergent = {hotel_id: names for hotel_id, names in lines_by_name.items() if len(names) > 1}
    if not divergent:
        return None
    details = "; ".join(
        f"{hotel_id} ({', '.join(f'{name!r} linhas {join(lines)}' for name, lines in names.items())})"
        for hotel_id, names in divergent.items()
    )
    return f"hotel_id com nomes diferentes, o relatório usa o primeiro: {details}"


def multiple_companies(reservations: Sequence[Reservation]) -> str | None:
    companies = sorted({reservation.company_id for reservation in reservations if reservation.company_id})
    if len(companies) < 2:
        return None
    return f"o arquivo tem mais de uma empresa: {', '.join(companies)}"


def join(lines: list[int]) -> str:
    return ", ".join(map(str, lines))
