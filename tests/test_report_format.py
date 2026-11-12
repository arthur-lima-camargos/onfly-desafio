"""Teste de contrato: formato do relatório JSON (README, "Contrato do CLI").

Nomes, tipos e formato de cada campo; nada a mais, nada a menos.
"""

import json
import re
from datetime import datetime, timedelta

import pytest
from cli_support import row, run_cli_rows
from helpers import run_cli

MONEY = re.compile(r"[0-9]+\.[0-9]{2}")
MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")

SUMMARY_TYPES = {
    "total_reservations": int,
    "confirmed_reservations": int,
    "cancelled_reservations": int,
    "no_show_reservations": int,
    "total_room_nights": int,
    "total_amount_brl": str,
    "average_nightly_rate_brl": str,
}
BY_MONTH_TYPES = {"month": str, "reservations": int, "room_nights": int, "total_brl": str}
TOP_HOTEL_TYPES = {"hotel_id": str, "hotel_name": str, "room_nights": int, "total_brl": str}

ROWS = [
    {"reservation_id": "R-1", "hotel_id": "H01", "currency": "USD", "amount": "123.45"},
    {"reservation_id": "R-2", "hotel_id": "H02", "checkin_date": "2025-02-27", "checkout_date": "2025-03-02"},
    {"reservation_id": "R-3", "status": "CANCELLED"},
    {"reservation_id": "R-4", "status": "NO_SHOW"},
]


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    return run_cli(tmp_path_factory.mktemp("formato"), ROWS)


def assert_fields(item: dict, expected_types: dict) -> None:
    assert set(item) == set(expected_types)
    for field, expected_type in expected_types.items():
        assert type(item[field]) is expected_type, field


# --- Estrutura --------------------------------------------------------------------------------


def test_top_level_has_exactly_the_documented_keys(report):
    assert set(report) == {"report_version", "generated_at", "summary", "by_month", "top_hotels"}


def test_report_version_is_always_1_0(report):
    assert report["report_version"] == "1.0"


def test_summary_fields_and_types(report):
    """Contagens são int (bool não conta como int); dinheiro é str."""
    assert_fields(report["summary"], SUMMARY_TYPES)


def test_by_month_items_fields_and_types(report):
    assert report["by_month"]
    for item in report["by_month"]:
        assert_fields(item, BY_MONTH_TYPES)


def test_top_hotels_items_fields_and_types(report):
    assert report["top_hotels"]
    for item in report["top_hotels"]:
        assert_fields(item, TOP_HOTEL_TYPES)


# --- Formatos ---------------------------------------------------------------------------------


def test_every_money_field_has_exactly_two_decimals_and_no_thousands_separator(report):
    money = [report["summary"]["total_amount_brl"], report["summary"]["average_nightly_rate_brl"]]
    money += [item["total_brl"] for item in report["by_month"] + report["top_hotels"]]

    for value in money:
        assert MONEY.fullmatch(value), value


def test_large_amount_has_no_thousands_separator(tmp_path):
    report = run_cli(tmp_path, [{"amount": "1234567.5"}])

    assert report["summary"]["total_amount_brl"] == "1234567.50"


def test_month_is_yyyy_mm(report):
    for item in report["by_month"]:
        assert MONTH.fullmatch(item["month"]), item["month"]


def test_generated_at_is_iso_with_fixed_minus_three_offset(report):
    generated_at = datetime.fromisoformat(report["generated_at"])

    assert report["generated_at"].endswith("-03:00")
    assert generated_at.utcoffset() == timedelta(hours=-3)


# --- Arredondamento (só na serialização, half-up) ---------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        pytest.param("0.125", "0.13", id="half-up-sobe-onde-half-even-desceria"),
        pytest.param("0.135", "0.14", id="half-up-sobe"),
        pytest.param("0.124", "0.12", id="abaixo-da-metade-desce"),
        pytest.param("10", "10.00", id="inteiro-ganha-duas-casas"),
    ],
)
def test_serialization_rounds_half_up(tmp_path, amount, expected):
    assert run_cli(tmp_path, [{"amount": amount}])["summary"]["total_amount_brl"] == expected


def test_values_are_summed_exactly_and_rounded_once(tmp_path):
    """Duas reservas de 0.005: soma exata 0.010 -> "0.01"; arredondar cada uma antes daria "0.02"."""
    report = run_cli(
        tmp_path, [{"reservation_id": "R-1", "amount": "0.005"}, {"reservation_id": "R-2", "amount": "0.005"}]
    )

    assert report["summary"]["total_amount_brl"] == "0.01"


# --- Codificação ------------------------------------------------------------------------------


def test_hotel_name_with_comma_and_accent_is_kept_literally_in_the_file(tmp_path):
    """O JSON é UTF-8 com o acento literal (ensure_ascii=False), e a vírgula do CSV não quebra o nome."""
    process, output_path = run_cli_rows(tmp_path, [row(hotel_name='"Hotel Madrid, Gran Vía"')])

    assert process.returncode == 0, process.stderr
    raw = output_path.read_text(encoding="utf-8")
    assert '"hotel_name": "Hotel Madrid, Gran Vía"' in raw
    assert json.loads(raw)["top_hotels"][0]["hotel_name"] == "Hotel Madrid, Gran Vía"
