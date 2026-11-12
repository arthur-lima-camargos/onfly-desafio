"""Teste de contrato: a amostra de validação bate com o README (seção "Amostra de validação").

Valores transcritos das tabelas entre <!-- AMOSTRA:INICIO --> e <!-- AMOSTRA:FIM -->.
"""

import json

import pytest
from cli_support import run_cli_args
from helpers import PROJECT_ROOT

EXPECTED_SUMMARY = {
    "total_reservations": 12,
    "confirmed_reservations": 9,
    "cancelled_reservations": 2,
    "no_show_reservations": 1,
    "total_room_nights": 28,
    "total_amount_brl": "7566.00",
    "average_nightly_rate_brl": "270.21",
}

EXPECTED_BY_MONTH = [
    {"month": "2025-01", "reservations": 8, "room_nights": 25, "total_brl": "6684.00"},
    {"month": "2025-02", "reservations": 1, "room_nights": 3, "total_brl": "882.00"},
]

EXPECTED_TOP_HOTELS = [
    {"hotel_id": "H01", "hotel_name": "Hotel Aurora Paulista", "room_nights": 3, "total_brl": "1200.00"},
    {"hotel_id": "H02", "hotel_name": "Hotel Mirante", "room_nights": 2, "total_brl": "1084.00"},
    {"hotel_id": "H12", "hotel_name": "Hotel Miami Beach", "room_nights": 1, "total_brl": "1000.00"},
    {"hotel_id": "H10", "hotel_name": "Hotel Madrid, Gran Vía", "room_nights": 4, "total_brl": "900.00"},
    {"hotel_id": "H09", "hotel_name": "Hotel Lisboa, Centro", "room_nights": 3, "total_brl": "882.00"},
]


@pytest.fixture(scope="module")
def sample_report(tmp_path_factory):
    output_path = tmp_path_factory.mktemp("amostra") / "exemplo.json"
    process = run_cli_args(
        [
            "--input",
            str(PROJECT_ROOT / "data" / "exemplo-validacao.csv"),
            "--rates",
            str(PROJECT_ROOT / "data" / "taxas_cambio.csv"),
            "--output",
            str(output_path),
        ]
    )
    assert process.returncode == 0, process.stderr
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_summary_matches_readme(sample_report):
    assert sample_report["summary"] == EXPECTED_SUMMARY


def test_by_month_matches_readme(sample_report):
    assert sample_report["by_month"] == EXPECTED_BY_MONTH


def test_top_hotels_match_readme(sample_report):
    assert sample_report["top_hotels"] == EXPECTED_TOP_HOTELS
