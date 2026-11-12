"""Execução do CLI com arquivos e argumentos livres (complementa helpers.run_cli).

helpers.run_cli sempre grava um CSV válido, passa --top e exige exit 0; aqui é possível testar
entradas inválidas, argumentos ausentes, o --top padrão, stdout e stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from helpers import BASE, COLUMNS, SRC_DIR

HEADER = ",".join(COLUMNS)


def row(**overrides: str) -> str:
    """Linha CSV a partir do BASE de helpers, com campos trocados (sem aspas: valores sem vírgula)."""
    values = {**BASE, **overrides}
    return ",".join(values[column] for column in COLUMNS)


VALID_ROW = row()
RATES = "currency,rate_to_brl\nBRL,1.000000\nUSD,5.420000\nEUR,5.880000\n"


def write_inputs(tmp_path: Path, rows: list[str], rates: str = RATES) -> tuple[Path, Path]:
    input_path = tmp_path / "reservas.csv"
    rates_path = tmp_path / "rates.csv"
    input_path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    rates_path.write_text(rates, encoding="utf-8")
    return input_path, rates_path


def run_cli_args(args: list[str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *args],
        cwd=str(SRC_DIR.parent),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def run_cli_rows(tmp_path: Path, rows: list[str], rates: str = RATES, extra: list[str] | None = None):
    input_path, rates_path = write_inputs(tmp_path, rows, rates)
    output_path = tmp_path / "report.json"
    args = ["--input", str(input_path), "--rates", str(rates_path), "--output", str(output_path), *(extra or [])]
    return run_cli_args(args), output_path
