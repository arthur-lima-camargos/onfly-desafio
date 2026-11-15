"""Política de status das reservas."""

from __future__ import annotations

from ..models import ReservationStatus


def is_billable(status: ReservationStatus) -> bool:
    """Indica se a reserva entra nos totais financeiros e de noites: só CONFIRMED é faturável."""
    return status == ReservationStatus.CONFIRMED
