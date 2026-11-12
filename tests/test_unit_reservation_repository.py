"""Testes unitários: leitura do CSV de reservas."""

import csv

import pytest
from helpers import BASE, COLUMNS, PROJECT_ROOT

from onfly_report.exceptions import InputFileError
from onfly_report.repositories.csv_reservation_repository import CsvReservationRepository


def write_csv(path, rows, columns=COLUMNS):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**BASE, **row} for row in rows)


def test_reads_every_row_without_truncating(tmp_path):
    """Arquivos com mais de 200 linhas são lidos por inteiro."""
    path = tmp_path / "reservas.csv"
    write_csv(path, [{"reservation_id": f"R-{index}"} for index in range(250)])

    rows = CsvReservationRepository(path).read()

    assert len(rows) == 250
    assert rows[-1].values["reservation_id"] == "R-249"


def test_reads_full_dataset():
    """O dataset fornecido tem 300 reservas."""
    rows = CsvReservationRepository(PROJECT_ROOT / "data" / "reservas_hoteis.csv").read()

    assert len(rows) == 300


def test_empty_file_with_header_returns_no_rows(tmp_path):
    path = tmp_path / "reservas.csv"
    write_csv(path, [])

    assert CsvReservationRepository(path).read() == []


def test_line_number_points_to_physical_line(tmp_path):
    """Campos entre aspas com vírgula não deslocam a numeração (cabeçalho é a linha 1)."""
    path = tmp_path / "reservas.csv"
    write_csv(path, [{"hotel_name": "Hotel Lisboa, Centro"}, {"reservation_id": "R-2"}])

    rows = CsvReservationRepository(path).read()

    assert [row.line_number for row in rows] == [2, 3]
    assert rows[0].values["hotel_name"] == "Hotel Lisboa, Centro"


def test_missing_required_column_raises_input_error(tmp_path):
    path = tmp_path / "reservas.csv"
    write_csv(path, [{}], columns=[column for column in COLUMNS if column != "amount"])

    with pytest.raises(InputFileError, match="amount"):
        CsvReservationRepository(path).read()


def test_missing_file_raises_input_error(tmp_path):
    with pytest.raises(InputFileError, match="não encontrado"):
        CsvReservationRepository(tmp_path / "inexistente.csv").read()
