"""Testes unitários: conversão e validação de uma linha de reserva.

Entradas que tornam o relatório impossível viram InputFileError (exit 2), com o número da linha.
"""

from datetime import date
from decimal import Decimal

import pytest
from helpers import BASE

from onfly_report.exceptions import InputFileError
from onfly_report.models import RawRow, ReservationStatus
from onfly_report.services.row_parser import REQUIRED_FIELDS, RowParser


def parse(line_number: int = 2, /, **overrides: str):
    return RowParser().parse(RawRow(line_number=line_number, values={**BASE, **overrides}))


def assert_rejected(match: str, **overrides: str) -> None:
    with pytest.raises(InputFileError, match=match):
        parse(**overrides)


# --- Linha válida -----------------------------------------------------------------------------


def test_valid_row_is_converted_to_domain_types():
    reservation = parse(7)

    assert reservation.checkin == date(2025, 1, 10)
    assert reservation.checkout == date(2025, 1, 11)
    assert reservation.rooms == 1
    assert reservation.status is ReservationStatus.CONFIRMED
    assert reservation.currency == "BRL"
    assert reservation.amount == Decimal("100.00")
    assert reservation.line_number == 7


def test_surrounding_spaces_are_removed():
    reservation = parse(status=" CONFIRMED ", hotel_id=" H01 ", amount=" 100.00 ", rooms=" 2 ")

    assert (reservation.status, reservation.hotel_id, reservation.amount, reservation.rooms) == (
        ReservationStatus.CONFIRMED,
        "H01",
        Decimal("100.00"),
        2,
    )


def test_columns_outside_the_report_may_be_empty():
    """O README diz que as demais colunas não afetam os totais; vazias não bloqueiam o relatório."""
    reservation = parse(traveler_name="", company_id="", city="", country="", payment_method="", booked_at="")

    assert reservation.traveler_name == ""


# --- Campos obrigatórios ----------------------------------------------------------------------


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_empty_required_field_is_rejected(field):
    assert_rejected(f"campos obrigatórios vazios: {field}", **{field: "   "})


def test_error_message_has_the_line_number():
    with pytest.raises(InputFileError, match=r"^linha 42 inválida"):
        parse(42, status="PENDING")


# --- Status -----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["CONFIRMED", "CANCELLED", "NO_SHOW"])
def test_documented_statuses_are_accepted(status):
    assert parse(status=status).status == status


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("PENDING", id="desconhecido"),
        pytest.param("confirmed", id="minusculas-nao-sao-corrigidas"),
        pytest.param("Confirmed", id="capitalizado"),
        pytest.param("NO SHOW", id="espaco-no-lugar-do-underscore"),
    ],
)
def test_unknown_status_is_rejected(status):
    assert_rejected("status desconhecido", status=status)


# --- Moeda ------------------------------------------------------------------------------------


@pytest.mark.parametrize("currency", ["usd", "Usd", " usd "])
def test_currency_is_normalized_to_uppercase(currency):
    """Mesma normalização que o CsvRateRepository aplica na tabela de câmbio."""
    assert parse(currency=currency).currency == "USD"


# --- Datas ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("20250110", id="iso-basico-sem-hifen"),
        pytest.param("2025-W02-5", id="semana-iso"),
        pytest.param("2025-1-10", id="mes-sem-zero"),
        pytest.param("10/01/2025", id="formato-brasileiro"),
        pytest.param("2025-01-10T00:00:00", id="com-horario"),
        pytest.param("+2025-01-10", id="com-sinal"),
    ],
)
def test_dates_must_be_yyyy_mm_dd(value):
    assert_rejected("checkin_date fora do formato YYYY-MM-DD", checkin_date=value)


@pytest.mark.parametrize("value", ["2025-02-30", "2025-13-01", "2025-00-10", "2025-04-31"])
def test_impossible_calendar_dates_are_rejected(value):
    assert_rejected("checkin_date não é uma data válida", checkin_date=value)


def test_checkout_before_checkin_is_rejected():
    assert_rejected("checkout_date 2025-01-05 é anterior a checkin_date 2025-01-10", checkout_date="2025-01-05")


def test_checkout_equal_to_checkin_is_accepted_with_zero_nights():
    """Day use: o README prevê "sem noites" (média "0.00"), então 0 noites é válido."""
    reservation = parse(checkin_date="2025-01-10", checkout_date="2025-01-10")

    assert reservation.checkin == reservation.checkout


# --- Quartos ----------------------------------------------------------------------------------


@pytest.mark.parametrize("rooms", ["0", "-1"])
def test_rooms_below_one_are_rejected(rooms):
    assert_rejected("rooms deve ser maior ou igual a 1", rooms=rooms)


@pytest.mark.parametrize("rooms", ["1.5", "dois", "1e2"])
def test_non_integer_rooms_are_rejected(rooms):
    assert_rejected("rooms não é um inteiro", rooms=rooms)


# --- Valor ------------------------------------------------------------------------------------


@pytest.mark.parametrize("amount", ["0.00", "0", "0.125", "1234.5"])
def test_valid_amounts_are_kept_exact(amount):
    """Zero (cortesia) é aceito e mais de 2 casas não é cortado: arredondar é só na serialização."""
    assert parse(amount=amount).amount == Decimal(amount)


@pytest.mark.parametrize("amount", ["NaN", "nan", "sNaN", "Infinity", "-Infinity", "inf"])
def test_non_finite_amount_is_rejected(amount):
    assert_rejected("amount não é um número finito", amount=amount)


def test_negative_amount_is_rejected():
    assert_rejected("amount negativo", amount="-100.00")


@pytest.mark.parametrize("amount", ["R$ 100,00", "100,00", "abc"])
def test_non_numeric_amount_is_rejected(amount):
    assert_rejected("amount não é um número", amount=amount)
