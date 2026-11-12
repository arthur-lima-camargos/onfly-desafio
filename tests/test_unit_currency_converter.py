"""Testes unitários: conversão de valores para BRL.

Regra: amount_brl = amount * rate_to_brl, em Decimal, sem arredondar (o arredondamento é só na
serialização do relatório).
"""

from decimal import Decimal

import pytest
from helpers import BASE, PROJECT_ROOT

from onfly_report.exceptions import InputFileError
from onfly_report.models import RawRow
from onfly_report.repositories.csv_rate_repository import CsvRateRepository
from onfly_report.services.currency_converter import convert_to_brl, ensure_rates_available
from onfly_report.services.row_parser import RowParser

# Mesmo formato de data/taxas_cambio.csv (6 casas decimais).
RATES = {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}


def brl(amount: str, currency: str = "USD", rates: dict[str, Decimal] = RATES) -> Decimal:
    return convert_to_brl(Decimal(amount), currency, rates)


# --- Direção da conta -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        pytest.param("100.00", "USD", "542.00", id="usd-multiplica-pela-taxa"),
        pytest.param("150.00", "EUR", "882.00", id="eur-multiplica-pela-taxa"),
        pytest.param("200.00", "USD", "1084.00", id="usd-da-amostra-do-readme-hotel-mirante"),
        pytest.param("1200.00", "BRL", "1200.00", id="brl-taxa-1-mantem-o-valor"),
    ],
)
def test_multiplies_amount_by_rate(amount, currency, expected):
    """O valor está na moeda de origem; multiplicar pela taxa leva para BRL (dividir inverte a conta)."""
    assert brl(amount, currency) == Decimal(expected)


def test_rate_below_one_reduces_the_amount():
    """Com taxa < 1 o valor em BRL fica menor; dividir faria o contrário (100 / 0.2 = 500)."""
    assert brl("100.00", "ARS", {"ARS": Decimal("0.200000")}) == Decimal("20.00")


def test_uses_the_rate_of_the_given_currency():
    """Cada moeda usa a própria taxa, mesmo com várias na tabela."""
    assert brl("10.00", "USD") == Decimal("54.20")
    assert brl("10.00", "EUR") == Decimal("58.80")
    assert brl("10.00", "BRL") == Decimal("10.00")


@pytest.mark.parametrize("currency", ["BRL", "USD", "EUR"])
def test_converts_with_the_real_rate_table(currency):
    """As taxas de data/taxas_cambio.csv, lidas pelo repositório, são aplicadas como multiplicador."""
    rates = CsvRateRepository(PROJECT_ROOT / "data" / "taxas_cambio.csv").read()

    assert convert_to_brl(Decimal("100.00"), currency, rates) == Decimal("100.00") * rates[currency]


# --- Exatidão ---------------------------------------------------------------------------------


def test_returns_decimal():
    assert isinstance(brl("100.00"), Decimal)


@pytest.mark.parametrize(
    ("amount", "rate", "expected"),
    [
        pytest.param("0.10", "3", "0.30", id="com-float-daria-0.30000000000000004"),
        pytest.param("1457.41", "5.42", "7899.1622", id="valor-do-dataset-com-float-daria-7899.162200000001"),
        pytest.param("1234.56", "5.880000", "7259.2128", id="taxa-com-6-casas-com-float-daria-7259.212799999999"),
        pytest.param("999999999.99", "5.420000", "5419999999.9458", id="valor-alto-sem-perder-centavos"),
        pytest.param("100.00", "5.123457", "512.3457", id="taxa-com-todas-as-casas-significativas"),
    ],
)
def test_conversion_is_exact_without_float(amount, rate, expected):
    """O resultado é exato: nenhum dígito é perdido ou inventado por passar por float."""
    assert brl(amount, "XXX", {"XXX": Decimal(rate)}) == Decimal(expected)


def test_matches_integer_arithmetic_for_many_amounts():
    """Oráculo independente: centavos * taxa em milionésimos, só com inteiros, para 0.00 a 99.99.

    Qualquer passagem por float diverge desse resultado em parte dos valores.
    """
    rate_millionths = 5_420_000  # 5.420000
    rate = Decimal(rate_millionths).scaleb(-6)

    for cents in range(10_000):
        amount = Decimal(cents).scaleb(-2)
        expected = Decimal(cents * rate_millionths).scaleb(-8)
        assert brl(str(amount), "XXX", {"XXX": rate}) == expected, amount


def test_conversion_does_not_round_cents():
    """Frações de centavo são preservadas; quem arredonda é a serialização, sobre o total."""
    assert brl("0.01") == Decimal("0.0542")


def test_zero_amount_converts_to_zero():
    assert brl("0.00") == Decimal("0")


# --- Propriedades da soma ---------------------------------------------------------------------


def test_sum_of_conversions_is_exact():
    """Somar muitos valores convertidos não acumula erro, como acontece com float."""
    total = sum((brl("0.10", "BRL") for _ in range(10)), Decimal("0"))

    assert total == Decimal("1.00")


def test_converting_the_sum_equals_summing_the_conversions():
    """Converter reserva a reserva e somar dá o mesmo que converter o total (distributividade)."""
    amounts = ["1457.41", "233.79", "0.01", "999.99"]

    total_of_conversions = sum((brl(amount) for amount in amounts), Decimal("0"))
    conversion_of_total = brl(str(sum((Decimal(amount) for amount in amounts), Decimal("0"))))

    assert total_of_conversions == conversion_of_total


def test_conversion_is_proportional_to_amount():
    assert brl("300.00") == 3 * brl("100.00")


# --- Efeitos colaterais -----------------------------------------------------------------------


def test_does_not_mutate_rate_table():
    rates = dict(RATES)

    brl("100.00", "USD", rates)

    assert rates == RATES


# --- Cobertura da tabela de câmbio ------------------------------------------------------------


def reservations(*rows: dict[str, str]):
    parser = RowParser()
    return [parser.parse(RawRow(line_number=index + 2, values={**BASE, **row})) for index, row in enumerate(rows)]


def test_all_currencies_with_rate_pass():
    ensure_rates_available(reservations({"currency": "BRL"}, {"currency": "USD"}, {"currency": "EUR"}), RATES)


def test_currency_without_rate_is_rejected_with_lines():
    rows = reservations({"currency": "BRL"}, {"currency": "GBP"}, {"currency": "JPY"}, {"currency": "GBP"})

    with pytest.raises(InputFileError, match=r"moeda sem taxa de câmbio: GBP \(linhas 3, 5\); JPY \(linhas 4\)"):
        ensure_rates_available(rows, RATES)


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_currency_without_rate_is_rejected_even_when_not_billable(status):
    """Decisão: todas as reservas são checadas; moeda sem taxa indica arquivo inconsistente."""
    with pytest.raises(InputFileError, match="GBP"):
        ensure_rates_available(reservations({"currency": "GBP", "status": status}), RATES)


def test_lowercase_currency_matches_uppercase_rate():
    """O parser normaliza 'usd' para 'USD', igual à tabela de câmbio."""
    ensure_rates_available(reservations({"currency": "usd"}), RATES)
