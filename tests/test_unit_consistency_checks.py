"""Testes unitários: inconsistências suspeitas que viram aviso, não erro.

Princípio: rejeitar (exit 2) o que torna o relatório impossível; avisar o que é suspeito mas
calculável, sem mudar o relatório.
"""

import pytest
from helpers import BASE, PROJECT_ROOT

from onfly_report.models import RawRow
from onfly_report.repositories.csv_reservation_repository import CsvReservationRepository
from onfly_report.services.consistency_checks import find_inconsistencies
from onfly_report.services.row_parser import RowParser


def reservations(*rows: dict[str, str]):
    parser = RowParser()
    return [parser.parse(RawRow(line_number=index + 2, values={**BASE, **row})) for index, row in enumerate(rows)]


def test_consistent_file_has_no_warnings():
    rows = reservations(
        {"reservation_id": "R-1", "hotel_id": "H01", "hotel_name": "Hotel A"},
        {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Hotel A"},
        {"reservation_id": "R-3", "hotel_id": "H02", "hotel_name": "Hotel B"},
    )

    assert find_inconsistencies(rows) == []


def test_real_dataset_has_no_warnings():
    """Os dados fornecidos são consistentes (README); o relatório real não deve gerar avisos."""
    parser = RowParser()
    raw_rows = CsvReservationRepository(PROJECT_ROOT / "data" / "reservas_hoteis.csv").read()

    assert find_inconsistencies([parser.parse(raw) for raw in raw_rows]) == []


def test_empty_file_has_no_warnings():
    assert find_inconsistencies([]) == []


# --- reservation_id repetido ------------------------------------------------------------------


def test_duplicated_reservation_id_is_reported_with_lines():
    rows = reservations({"reservation_id": "R-1"}, {"reservation_id": "R-2"}, {"reservation_id": "R-1"})

    assert find_inconsistencies(rows) == ["reservation_id repetido, possível cobrança em dobro: R-1 (linhas 2, 4)"]


def test_every_duplicated_id_is_listed():
    rows = reservations(*({"reservation_id": reservation_id} for reservation_id in ["R-1", "R-2", "R-1", "R-2", "R-2"]))

    assert find_inconsistencies(rows) == [
        "reservation_id repetido, possível cobrança em dobro: R-1 (linhas 2, 4); R-2 (linhas 3, 5, 6)"
    ]


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_duplicated_id_counts_regardless_of_status(status):
    """A mesma reserva como CONFIRMED e como cancelada também é suspeita."""
    rows = reservations({"reservation_id": "R-1"}, {"reservation_id": "R-1", "status": status})

    assert "R-1 (linhas 2, 3)" in find_inconsistencies(rows)[0]


# --- hotel_id com nomes diferentes ------------------------------------------------------------


def test_divergent_hotel_names_are_reported_with_lines():
    rows = reservations(
        {"reservation_id": "R-1", "hotel_name": "Hotel A"},
        {"reservation_id": "R-2", "hotel_name": "Hotel B"},
        {"reservation_id": "R-3", "hotel_name": "Hotel A"},
    )

    assert find_inconsistencies(rows) == [
        "hotel_id com nomes diferentes, o relatório usa o primeiro: H01 ('Hotel A' linhas 2, 4, 'Hotel B' linhas 3)"
    ]


def test_same_name_for_different_hotels_is_not_a_warning():
    """Redes têm hotéis com o mesmo nome em cidades diferentes; o que identifica é o hotel_id."""
    rows = reservations(
        {"reservation_id": "R-1", "hotel_id": "H01", "hotel_name": "Hotel Centro"},
        {"reservation_id": "R-2", "hotel_id": "H02", "hotel_name": "Hotel Centro"},
    )

    assert find_inconsistencies(rows) == []


# --- várias empresas --------------------------------------------------------------------------


def test_multiple_companies_are_reported():
    rows = reservations(
        {"reservation_id": "R-1", "company_id": "EMP-002"},
        {"reservation_id": "R-2", "company_id": "EMP-001"},
        {"reservation_id": "R-3", "company_id": "EMP-002"},
    )

    assert find_inconsistencies(rows) == ["o arquivo tem mais de uma empresa: EMP-001, EMP-002"]


def test_empty_company_is_not_counted_as_another_company():
    """company_id fora do relatório pode vir vazio; vazio não é uma segunda empresa."""
    rows = reservations({"reservation_id": "R-1", "company_id": "EMP-001"}, {"reservation_id": "R-2", "company_id": ""})

    assert find_inconsistencies(rows) == []


# --- várias inconsistências -------------------------------------------------------------------


def test_one_message_per_kind_in_fixed_order():
    rows = reservations(
        {"reservation_id": "R-1", "hotel_name": "Hotel A", "company_id": "EMP-001"},
        {"reservation_id": "R-1", "hotel_name": "Hotel B", "company_id": "EMP-002"},
    )

    messages = find_inconsistencies(rows)

    assert [message.split(":")[0] for message in messages] == [
        "reservation_id repetido, possível cobrança em dobro",
        "hotel_id com nomes diferentes, o relatório usa o primeiro",
        "o arquivo tem mais de uma empresa",
    ]
