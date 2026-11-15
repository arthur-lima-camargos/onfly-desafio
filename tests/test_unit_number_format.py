"""Testes unitários: formato dos números de entrada e precisão da aritmética de dinheiro."""

from decimal import Decimal

import pytest

from onfly_report.number_format import (
    MONEY_PRECISION,
    PLAIN_AMOUNT,
    PLAIN_RATE,
    PLAIN_ROOMS,
    parse_plain_decimal,
    parse_plain_int,
)

LARGEST_AMOUNT = "9" * 15 + "." + "9" * 6
LARGEST_RATE = "9" * 9 + "." + "9" * 12

# --- Conversão --------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["0", "100", "100.5", "100.50", "0.000001", LARGEST_AMOUNT])
def test_plain_decimal_is_converted_without_losing_digits(text):
    amount = parse_plain_decimal(text, PLAIN_AMOUNT)

    assert amount == Decimal(text)
    assert str(amount) == text


def test_text_outside_the_format_returns_none_instead_of_raising():
    assert parse_plain_decimal("1E+3", PLAIN_AMOUNT) is None
    assert parse_plain_int("1_0", PLAIN_ROOMS) is None


@pytest.mark.parametrize("text", ["100\n", "\n100", "100 ", " 100", "100\t", ""])
def test_the_whole_text_must_match_including_line_breaks_and_spaces(text):
    """fullmatch, não match com $: "100\\n" não passa. Quem tira os espaços é o parser, antes."""
    assert parse_plain_decimal(text, PLAIN_AMOUNT) is None
    assert parse_plain_int(text, PLAIN_ROOMS) is None


@pytest.mark.parametrize(("text", "expected"), [("1", 1), ("01", 1), ("9999", 9999), ("0", 0)])
def test_plain_int_is_converted(text, expected):
    assert parse_plain_int(text, PLAIN_ROOMS) == expected


# --- Limites de tamanho -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "largest", "one_integer_digit_more", "one_decimal_more"),
    [
        pytest.param(PLAIN_AMOUNT, LARGEST_AMOUNT, "9" + LARGEST_AMOUNT, LARGEST_AMOUNT + "9", id="valor"),
        pytest.param(PLAIN_RATE, LARGEST_RATE, "9" + LARGEST_RATE, LARGEST_RATE + "9", id="taxa"),
    ],
)
def test_size_limits_are_exact(pattern, largest, one_integer_digit_more, one_decimal_more):
    assert parse_plain_decimal(largest, pattern) == Decimal(largest)
    assert parse_plain_decimal(one_integer_digit_more, pattern) is None
    assert parse_plain_decimal(one_decimal_more, pattern) is None


def test_rooms_limit_is_four_digits():
    assert parse_plain_int("9999", PLAIN_ROOMS) == 9999
    assert parse_plain_int("10000", PLAIN_ROOMS) is None


# --- Precisão ---------------------------------------------------------------------------------


def test_precision_covers_the_largest_product_summed_a_quintillion_times():
    """Maior valor x maior taxa, contado em inteiros: os dígitos do produto mais 18 de folga cabem."""
    largest_product = int(LARGEST_AMOUNT.replace(".", "")) * int(LARGEST_RATE.replace(".", ""))

    assert len(str(largest_product)) == 42
    assert len(str(largest_product * 10**18)) <= MONEY_PRECISION


def test_precision_is_above_the_decimal_default_that_would_round_silently():
    assert MONEY_PRECISION > 28
