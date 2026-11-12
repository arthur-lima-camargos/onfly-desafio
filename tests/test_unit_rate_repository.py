"""Testes unitários: leitura da tabela de câmbio."""

from decimal import Decimal

import pytest
from helpers import PROJECT_ROOT

from onfly_report.exceptions import InputFileError
from onfly_report.repositories.csv_rate_repository import CsvRateRepository


def read_rates(tmp_path, content: str, encoding: str = "utf-8") -> dict[str, Decimal]:
    path = tmp_path / "rates.csv"
    path.write_bytes(content.encode(encoding))
    return CsvRateRepository(path).read()


def test_reads_the_real_rate_table():
    rates = CsvRateRepository(PROJECT_ROOT / "data" / "taxas_cambio.csv").read()

    assert rates == {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}


def test_currency_is_normalized_to_uppercase(tmp_path):
    assert read_rates(tmp_path, "currency,rate_to_brl\n usd ,5.42\n") == {"USD": Decimal("5.42")}


def test_rate_keeps_every_decimal_place(tmp_path):
    assert read_rates(tmp_path, "currency,rate_to_brl\nUSD,5.420001\n")["USD"] == Decimal("5.420001")


def test_utf8_bom_is_ignored(tmp_path):
    """Exportações do Excel começam com BOM; sem tratar, o cabeçalho viraria '\\ufeffcurrency'."""
    assert read_rates(tmp_path, "currency,rate_to_brl\nBRL,1\n", encoding="utf-8-sig") == {"BRL": Decimal("1")}


@pytest.mark.parametrize(
    ("content", "match"),
    [
        pytest.param("currency,rate_to_brl\nUSD,5.42\nusd,6.00\n", "moeda USD repetida", id="moeda-repetida"),
        pytest.param("currency,rate_to_brl\nUSD,NaN\n", "taxa não finita", id="nan"),
        pytest.param("currency,rate_to_brl\nUSD,Infinity\n", "taxa não finita", id="infinito"),
        pytest.param("currency,rate_to_brl\nUSD,0\n", "taxa não positiva", id="zero"),
        pytest.param("currency,rate_to_brl\nUSD,-5.42\n", "taxa não positiva", id="negativa"),
        pytest.param("currency,rate_to_brl\nUSD,cinco\n", "taxa inválida", id="nao-numerica"),
        pytest.param("currency,rate_to_brl\nUSD,\n", "linha de câmbio incompleta", id="taxa-vazia"),
        pytest.param("currency,rate_to_brl\nUSD\n", "linha 2 malformada", id="coluna-faltando"),
        pytest.param("currency,rate_to_brl\nUSD,5.42,extra\n", "linha 2 malformada", id="coluna-sobrando"),
        pytest.param("currency\nUSD\n", "colunas obrigatórias ausentes", id="sem-coluna-de-taxa"),
        pytest.param("currency,rate_to_brl\n", "tabela de câmbio vazia", id="so-cabecalho"),
    ],
)
def test_invalid_rate_table_is_rejected(tmp_path, content, match):
    with pytest.raises(InputFileError, match=match):
        read_rates(tmp_path, content)


def test_invalid_utf8_is_an_input_error(tmp_path):
    """Arquivo em outra codificação é entrada inválida (exit 2), não erro inesperado."""
    with pytest.raises(InputFileError, match="falha ao ler"):
        read_rates(tmp_path, "currency,rate_to_brl\nÇ,1\n", encoding="latin-1")


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(InputFileError, match="tabela de câmbio não encontrada"):
        CsvRateRepository(tmp_path / "nao_existe.csv").read()
