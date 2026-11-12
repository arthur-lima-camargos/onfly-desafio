"""Testes ponta a ponta: códigos de saída do CLI.

Contrato do README: 0 sucesso, 2 entrada/argumento inválido, 1 erro inesperado.
"""

import json

import pytest
from cli_support import VALID_ROW, row, run_cli_args, run_cli_rows, write_inputs
from helpers import PROJECT_ROOT

# --- 0: sucesso -------------------------------------------------------------------------------


def test_success_exits_0_with_summary_on_stdout_and_report_written(tmp_path):
    process, output_path = run_cli_rows(tmp_path, [VALID_ROW])

    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "Reservas: 1 | Confirmadas: 1 | Noites: 1 | Total BRL: 100.00"
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["total_amount_brl"] == "100.00"


def test_output_directory_is_created(tmp_path):
    input_path, rates_path = write_inputs(tmp_path, [VALID_ROW])
    output_path = tmp_path / "novo" / "dir" / "report.json"

    process = run_cli_args(["--input", str(input_path), "--rates", str(rates_path), "--output", str(output_path)])

    assert process.returncode == 0, process.stderr
    assert output_path.is_file()


def test_top_defaults_to_5(tmp_path):
    rows = [row(reservation_id=f"R-{index}", hotel_id=f"H{index:02d}") for index in range(1, 8)]

    process, output_path = run_cli_rows(tmp_path, rows)

    assert process.returncode == 0, process.stderr
    assert len(json.loads(output_path.read_text(encoding="utf-8"))["top_hotels"]) == 5


def test_zero_night_stay_is_valid_and_average_is_zero(tmp_path):
    """Day use (check-out = check-in): sem noites, a média é "0.00" e o valor é faturado."""
    process, output_path = run_cli_rows(tmp_path, [row(checkout_date="2025-01-10")])

    assert process.returncode == 0, process.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))["summary"]
    assert (summary["total_room_nights"], summary["total_amount_brl"], summary["average_nightly_rate_brl"]) == (
        0,
        "100.00",
        "0.00",
    )


# --- 2: argumento inválido --------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(["--top", "0"], id="top-zero"),
        pytest.param(["--top", "-1"], id="top-negativo"),
        pytest.param(["--top", "abc"], id="top-nao-inteiro"),
        pytest.param(["--top", "1.5"], id="top-decimal"),
        pytest.param(["--formato", "csv"], id="argumento-desconhecido"),
    ],
)
def test_invalid_argument_exits_2(tmp_path, extra):
    process, output_path = run_cli_rows(tmp_path, [VALID_ROW], extra=extra)

    assert process.returncode == 2
    assert not output_path.exists()


@pytest.mark.parametrize("missing", ["--input", "--rates"])
def test_missing_required_argument_exits_2(tmp_path, missing):
    input_path, rates_path = write_inputs(tmp_path, [VALID_ROW])
    args = {"--input": str(input_path), "--rates": str(rates_path)}
    del args[missing]

    process = run_cli_args([item for pair in args.items() for item in pair])

    assert process.returncode == 2
    assert missing in process.stderr


# --- 2: entrada inválida ----------------------------------------------------------------------


@pytest.mark.parametrize("which", ["--input", "--rates"])
def test_missing_file_exits_2(tmp_path, which):
    input_path, rates_path = write_inputs(tmp_path, [VALID_ROW])
    paths = {"--input": str(input_path), "--rates": str(rates_path)}
    paths[which] = str(tmp_path / "nao_existe.csv")

    process = run_cli_args([item for pair in paths.items() for item in pair])

    assert process.returncode == 2
    assert "não encontrad" in process.stderr


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        pytest.param([row(status="PENDING")], "status desconhecido", id="status-desconhecido"),
        pytest.param([row(status="confirmed")], "status desconhecido", id="status-minusculo"),
        pytest.param([row(currency="GBP")], "moeda sem taxa de câmbio: GBP", id="moeda-sem-taxa"),
        pytest.param([row(currency="GBP", status="CANCELLED")], "GBP", id="moeda-sem-taxa-em-cancelada"),
        pytest.param([row(rooms="0")], "rooms deve ser maior ou igual a 1", id="zero-quartos"),
        pytest.param([row(checkout_date="2025-01-05")], "anterior a checkin_date", id="checkout-antes"),
        pytest.param([row(amount="-100.00")], "amount negativo", id="valor-negativo"),
        pytest.param([row(amount="NaN")], "amount não é um número finito", id="valor-nan"),
        pytest.param([row(checkin_date="20250110")], "fora do formato YYYY-MM-DD", id="data-sem-hifen"),
        pytest.param([row(hotel_id="")], "campos obrigatórios vazios: hotel_id", id="hotel-vazio"),
        pytest.param([VALID_ROW.rsplit(",", 1)[0]], "linha 2 malformada", id="linha-curta"),
    ],
)
def test_invalid_reservation_exits_2_with_reason_and_no_report(tmp_path, rows, message):
    process, output_path = run_cli_rows(tmp_path, rows)

    assert process.returncode == 2
    assert message in process.stderr
    assert "Traceback" not in process.stderr
    assert process.stdout == ""
    assert not output_path.exists()


def test_invalid_line_is_reported_by_number(tmp_path):
    process, _ = run_cli_rows(tmp_path, [VALID_ROW, row(reservation_id="R-2"), row(reservation_id="R-3", rooms="x")])

    assert process.returncode == 2
    assert "linha 4 inválida" in process.stderr


@pytest.mark.parametrize(
    ("rates", "message"),
    [
        pytest.param("currency,rate_to_brl\nBRL,1\nBRL,2\n", "moeda BRL repetida", id="moeda-repetida"),
        pytest.param("currency,rate_to_brl\nBRL,NaN\n", "taxa não finita", id="taxa-nan"),
        pytest.param("moeda,taxa\nBRL,1\n", "colunas obrigatórias ausentes", id="cabecalho-errado"),
    ],
)
def test_invalid_rate_table_exits_2(tmp_path, rates, message):
    process, _ = run_cli_rows(tmp_path, [VALID_ROW], rates=rates)

    assert process.returncode == 2
    assert message in process.stderr


# --- 1: erro inesperado -----------------------------------------------------------------------


def test_unwritable_output_exits_1(tmp_path):
    """Falha ao gravar o relatório não é culpa da entrada: erro inesperado."""
    input_path, rates_path = write_inputs(tmp_path, [VALID_ROW])
    output_is_a_directory = tmp_path / "saida"
    output_is_a_directory.mkdir()

    process = run_cli_args(
        ["--input", str(input_path), "--rates", str(rates_path), "--output", str(output_is_a_directory)]
    )

    assert process.returncode == 1
    assert process.stdout == ""


# --- 0 com aviso: suspeito, mas calculável ----------------------------------------------------


@pytest.mark.parametrize(
    ("rows", "warning"),
    [
        pytest.param([row(), row(amount="50.00")], "reservation_id repetido", id="id-duplicado"),
        pytest.param(
            [row(), row(reservation_id="R-2", hotel_name="Outro")], "hotel_id com nomes diferentes", id="nome-hotel"
        ),
        pytest.param(
            [row(), row(reservation_id="R-2", company_id="EMP-002")], "mais de uma empresa", id="varias-empresas"
        ),
    ],
)
def test_suspicious_input_warns_on_stderr_and_still_writes_the_report(tmp_path, rows, warning):
    process, output_path = run_cli_rows(tmp_path, rows)

    assert process.returncode == 0, process.stderr
    assert "WARNING" in process.stderr
    assert warning in process.stderr
    assert process.stdout.startswith("Reservas: 2 |")
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(report) == {"report_version", "generated_at", "summary", "by_month", "top_hotels"}


def test_real_dataset_runs_without_warnings(tmp_path):
    process = run_cli_args(
        [
            "--input",
            str(PROJECT_ROOT / "data" / "reservas_hoteis.csv"),
            "--rates",
            str(PROJECT_ROOT / "data" / "taxas_cambio.csv"),
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert process.returncode == 0, process.stderr
    assert "WARNING" not in process.stderr
