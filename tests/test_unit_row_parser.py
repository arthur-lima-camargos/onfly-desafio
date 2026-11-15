"""Testes unitários: conversão e validação de uma linha de reserva.

Entradas que tornam o relatório impossível viram InputFileError (exit 2), com o número da linha.
"""

from datetime import date
from decimal import Decimal

import pytest
from helpers import BASE

from onfly_report.exceptions import InputFileError
from onfly_report.models import RawRow, ReservationStatus
from onfly_report.services.row_parser import MAX_REPORTED_LINES, REQUIRED_FIELDS, RowParser


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


@pytest.mark.parametrize(("rooms", "expected"), [("1", 1), ("2", 2), ("01", 1), ("9999", 9999)])
def test_plain_integer_rooms_are_accepted(rooms, expected):
    assert parse(rooms=rooms).rooms == expected


@pytest.mark.parametrize("rooms", ["0", "00", "0000"])
def test_zero_rooms_are_rejected(rooms):
    assert_rejected("rooms deve ser maior ou igual a 1", rooms=rooms)


@pytest.mark.parametrize(
    "rooms",
    [
        pytest.param("1_0", id="sublinhado-que-int-leria-como-10"),
        pytest.param("+2", id="sinal-de-mais"),
        pytest.param("-1", id="negativo"),
        pytest.param("２", id="digito-unicode-de-largura-total"),
        pytest.param("٣", id="digito-arabe-indico"),
        pytest.param("1.5", id="fracionario"),
        pytest.param("1.0", id="inteiro-escrito-com-ponto"),
        pytest.param("1e2", id="notacao-cientifica"),
        pytest.param("0x2", id="hexadecimal"),
        pytest.param("1 0", id="espaco-no-meio"),
        pytest.param("dois", id="texto"),
        pytest.param("10000", id="cinco-digitos"),
        pytest.param("9" * 5000, id="inteiro-gigante"),
    ],
)
def test_rooms_outside_the_plain_integer_format_are_rejected(rooms):
    """int() leria vários destes como número; numa exportação, indicam arquivo corrompido."""
    assert_rejected("rooms fora do formato inteiro simples", rooms=rooms)


# --- Valor ------------------------------------------------------------------------------------


AMOUNT_FORMAT_ERROR = "amount fora do formato decimal simples"


@pytest.mark.parametrize(
    "amount",
    ["0.00", "0", "0.125", "1234.5", "007.50", "0.000001", "999999999999999", "999999999999999.999999"],
)
def test_valid_amounts_are_kept_exact(amount):
    """Zero (cortesia) é aceito e mais de 2 casas não é cortado: arredondar é só na serialização."""
    assert parse(amount=amount).amount == Decimal(amount)


@pytest.mark.parametrize("amount", ["NaN", "nan", "sNaN", "Infinity", "-Infinity", "inf"])
def test_non_finite_amount_is_rejected(amount):
    assert_rejected(AMOUNT_FORMAT_ERROR, amount=amount)


@pytest.mark.parametrize("amount", ["-100.00", "-0", "-0.01"])
def test_negative_amount_is_rejected(amount):
    assert_rejected(AMOUNT_FORMAT_ERROR, amount=amount)


@pytest.mark.parametrize("amount", ["R$ 100,00", "100,00", "1.234,56", "abc"])
def test_non_numeric_amount_is_rejected(amount):
    assert_rejected(AMOUNT_FORMAT_ERROR, amount=amount)


@pytest.mark.parametrize(
    "amount",
    [
        pytest.param("1_000.50", id="sublinhado-que-decimal-leria-como-1000.50"),
        pytest.param("1E+3", id="notacao-cientifica-maiuscula"),
        pytest.param("1e3", id="notacao-cientifica-minuscula"),
        pytest.param("+10", id="sinal-de-mais"),
        pytest.param("２", id="digito-unicode-de-largura-total"),
        pytest.param("١٠٠", id="digitos-arabe-indicos"),
        pytest.param(".5", id="sem-parte-inteira"),
        pytest.param("5.", id="ponto-sem-decimais"),
        pytest.param("1.2.3", id="dois-pontos"),
        pytest.param("1 000", id="espaco-no-meio"),
        pytest.param("0x10", id="hexadecimal"),
    ],
)
def test_amount_that_decimal_would_read_but_is_not_plain_is_rejected(amount):
    """Decimal() leria vários destes como número; numa exportação, indicam arquivo corrompido."""
    assert_rejected(AMOUNT_FORMAT_ERROR, amount=amount)


@pytest.mark.parametrize(
    "amount",
    [
        pytest.param("1E+40", id="expoente-enorme"),
        pytest.param("1" * 16, id="16-digitos-inteiros"),
        pytest.param("1" * 30, id="30-digitos-acima-da-precisao-padrao-do-decimal"),
        pytest.param("0.1234567", id="7-casas-decimais"),
    ],
)
def test_amount_beyond_the_size_limits_is_rejected(amount):
    """Antes, estes passavam pelo parser e estouravam no quantize, com traceback e exit 1."""
    assert_rejected(AMOUNT_FORMAT_ERROR, amount=amount)


def test_rejected_amount_message_shows_the_line_and_the_offending_text():
    with pytest.raises(InputFileError, match=r"linha 9 inválida: amount fora do formato.*'1_000\.50'"):
        parse(9, amount="1_000.50")


# --- Arquivo inteiro: todas as linhas inválidas de uma vez ------------------------------------


def parse_all(*rows: dict[str, str]):
    """Linhas numeradas a partir da 2, como no arquivo (a 1 é o cabeçalho)."""
    raw_rows = [RawRow(line_number=index + 2, values={**BASE, **row}) for index, row in enumerate(rows)]
    return RowParser().parse_all(raw_rows)


def invalid_lines_message(*rows: dict[str, str]) -> str:
    with pytest.raises(InputFileError) as error:
        parse_all(*rows)
    return str(error.value)


def test_all_valid_rows_are_converted_in_file_order():
    reservations = parse_all({"reservation_id": "R-1"}, {"reservation_id": "R-2"}, {"reservation_id": "R-3"})

    assert [(row.reservation_id, row.line_number) for row in reservations] == [("R-1", 2), ("R-2", 3), ("R-3", 4)]


def test_empty_file_converts_to_no_reservations():
    assert parse_all() == []


def test_a_single_invalid_line_keeps_the_simple_message():
    message = invalid_lines_message({}, {"rooms": "0"}, {})

    assert message == "linha 3 inválida: rooms deve ser maior ou igual a 1: 0"


def test_every_invalid_line_is_listed_in_file_order_with_its_own_reason():
    message = invalid_lines_message({"rooms": "0"}, {}, {"status": "PENDING"}, {"checkin_date": "10/01/2025"})

    assert message.splitlines() == [
        "3 linhas inválidas:",
        "  linha 2 inválida: rooms deve ser maior ou igual a 1: 0",
        "  linha 4 inválida: status desconhecido: 'PENDING' (esperado: CONFIRMED, CANCELLED, NO_SHOW)",
        "  linha 5 inválida: checkin_date fora do formato YYYY-MM-DD: '10/01/2025'",
    ]


def test_valid_lines_between_invalid_ones_are_not_mentioned():
    message = invalid_lines_message({"rooms": "0"}, {}, {}, {"rooms": "0"})

    assert "linha 3" not in message
    assert "linha 4" not in message


def test_a_line_with_several_problems_is_listed_once_with_the_first_reason():
    """Uma entrada por linha: a contagem do cabeçalho é de linhas, não de campos errados."""
    message = invalid_lines_message({"rooms": "0", "amount": "abc"}, {"status": "PENDING"})

    assert message.splitlines()[0] == "2 linhas inválidas:"
    assert message.count("linha 2 inválida") == 1


def test_list_is_capped_and_the_rest_is_counted():
    message = invalid_lines_message(*[{"rooms": "0"}] * (MAX_REPORTED_LINES + 5))

    lines = message.splitlines()
    assert lines[0] == f"{MAX_REPORTED_LINES + 5} linhas inválidas:"
    assert len(lines) == 1 + MAX_REPORTED_LINES + 1
    assert lines[-2].startswith(f"  linha {MAX_REPORTED_LINES + 1} inválida")
    assert lines[-1] == "  ... e mais 5"


def test_exactly_the_cap_lists_everything_without_a_remainder_line():
    message = invalid_lines_message(*[{"rooms": "0"}] * MAX_REPORTED_LINES)

    lines = message.splitlines()
    assert len(lines) == 1 + MAX_REPORTED_LINES
    assert "e mais" not in message
