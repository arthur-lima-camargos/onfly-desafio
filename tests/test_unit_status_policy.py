"""Testes unitários: política de status (só CONFIRMED é faturável)."""

from typing import get_type_hints

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


def test_only_confirmed_is_billable_not_everything_except_cancelled():
    """A regra é uma lista de permissão (só CONFIRMED), não "tudo menos CANCELLED".

    Varre o enum inteiro: um status novo nasce não faturável até alguém decidir o contrário.
    """
    assert {status for status in ReservationStatus if is_billable(status)} == {ReservationStatus.CONFIRMED}


@pytest.mark.parametrize("status", list(ReservationStatus))
def test_result_is_a_plain_bool(status):
    assert type(is_billable(status)) is bool


def test_parameter_is_typed_as_the_status_enum():
    """O parser já entrega ReservationStatus; com o tipo certo, o mypy barra uma str solta."""
    assert get_type_hints(is_billable) == {"status": ReservationStatus, "return": bool}
