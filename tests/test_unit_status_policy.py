"""Testes unitários: política de status (só CONFIRMED é faturável)."""

import pytest

from onfly_report.models import ReservationStatus
from onfly_report.services.status_policy import is_billable


def test_status_enum_has_exactly_the_documented_statuses():
    """O README define três status; um novo status precisa de decisão explícita sobre faturamento."""
    assert {status.value for status in ReservationStatus} == {"CONFIRMED", "CANCELLED", "NO_SHOW"}


def test_confirmed_is_billable():
    assert is_billable(ReservationStatus.CONFIRMED)


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(ReservationStatus.CANCELLED, id="cancelled"),
        pytest.param(ReservationStatus.NO_SHOW, id="no-show-tambem-nao-fatura"),
    ],
)
def test_non_confirmed_statuses_are_not_billable(status):
    assert not is_billable(status)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param("CONFIRMED", True, id="confirmed"),
        pytest.param("CANCELLED", False, id="cancelled"),
        pytest.param("NO_SHOW", False, id="no-show"),
    ],
)
def test_accepts_plain_strings_as_read_from_csv(status, expected):
    """O parser entrega o status como str; a comparação com o enum precisa funcionar igual."""
    assert is_billable(status) is expected


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("PENDING", id="status-desconhecido"),
        pytest.param("", id="vazio"),
    ],
)
def test_only_confirmed_is_billable_not_everything_except_cancelled(status):
    """A regra é uma lista de permissão (só CONFIRMED), não 'tudo menos CANCELLED'."""
    assert not is_billable(status)
