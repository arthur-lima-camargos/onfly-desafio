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


def test_utf8_bom_is_ignored(tmp_path):
    """Exportações do Excel começam com BOM; sem tratar, a 1ª coluna viraria '\\ufeffreservation_id'."""
    path = tmp_path / "reservas.csv"
    write_csv(path, [{}])
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    rows = CsvReservationRepository(path).read()

    assert rows[0].values["reservation_id"] == "R-1"


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("R-2,P,EMP,H01,Hotel,SP,BR,2025-01-10,2025-01-11,1,CONFIRMED,BRL,100.00", id="coluna-faltando"),
        pytest.param(
            "R-2,P,EMP,H01,Hotel,SP,BR,2025-01-10,2025-01-11,1,CONFIRMED,BRL,100.00,PIX,x,EXTRA",
            id="coluna-sobrando",
        ),
        pytest.param(
            "R-2,P,EMP,H09,Hotel Lisboa, Centro,Lisboa,PT,2025-01-10,2025-01-11,1,CONFIRMED,BRL,100.00,PIX,x",
            id="virgula-no-nome-sem-aspas",
        ),
    ],
)
def test_malformed_line_is_rejected_with_its_number(tmp_path, line):
    """Linha com número de colunas diferente do cabeçalho indica CSV corrompido."""
    path = tmp_path / "reservas.csv"
    write_csv(path, [{}])
    path.write_text(path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")

    with pytest.raises(InputFileError, match="linha 3 malformada"):
        CsvReservationRepository(path).read()


def test_invalid_utf8_is_an_input_error(tmp_path):
    """Arquivo em outra codificação é entrada inválida (exit 2), não erro inesperado."""
    path = tmp_path / "reservas.csv"
    write_csv(path, [{"hotel_name": "Hotel São Paulo"}])
    path.write_bytes(path.read_text(encoding="utf-8").encode("latin-1"))

    with pytest.raises(InputFileError, match="falha ao ler"):
        CsvReservationRepository(path).read()
