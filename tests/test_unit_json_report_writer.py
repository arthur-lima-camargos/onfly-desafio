"""Testes unitários: gravação atômica do relatório JSON."""

import json
from pathlib import Path

import pytest

from onfly_report.repositories.json_report_writer import write_report
from onfly_report.services.report_serializer import ReportJson

REPORT: ReportJson = {
    "report_version": "1.0",
    "generated_at": "2025-07-01T10:00:00-03:00",
    "summary": {
        "total_reservations": 1,
        "confirmed_reservations": 1,
        "cancelled_reservations": 0,
        "no_show_reservations": 0,
        "total_room_nights": 4,
        "total_amount_brl": "900.00",
        "average_nightly_rate_brl": "225.00",
    },
    "by_month": [{"month": "2025-01", "reservations": 1, "room_nights": 4, "total_brl": "900.00"}],
    "top_hotels": [
        {"hotel_id": "H10", "hotel_name": "Hotel Madrid, Gran Vía", "room_nights": 4, "total_brl": "900.00"}
    ],
}


def names_in(directory: Path) -> list[str]:
    return sorted(item.name for item in directory.iterdir())


# --- Conteúdo ---------------------------------------------------------------------------------


def test_written_file_is_the_report_as_json(tmp_path):
    output_path = tmp_path / "report.json"

    write_report(REPORT, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == REPORT


def test_file_is_utf8_with_literal_accents_two_space_indent_and_final_newline(tmp_path):
    output_path = tmp_path / "report.json"

    write_report(REPORT, output_path)

    text = output_path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert '"hotel_name": "Hotel Madrid, Gran Vía"' in text
    assert text.startswith('{\n  "report_version": "1.0",\n')
    assert text.endswith("}\n")


def test_missing_parent_directories_are_created(tmp_path):
    output_path = tmp_path / "novo" / "dir" / "report.json"

    write_report(REPORT, output_path)

    assert output_path.is_file()


# --- Atomicidade ------------------------------------------------------------------------------


def test_no_temporary_file_is_left_after_success(tmp_path):
    write_report(REPORT, tmp_path / "report.json")

    assert names_in(tmp_path) == ["report.json"]


def test_previous_report_is_replaced(tmp_path):
    output_path = tmp_path / "report.json"
    output_path.write_text("relatório antigo", encoding="utf-8")

    write_report(REPORT, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == REPORT
    assert names_in(tmp_path) == ["report.json"]


def test_failure_in_the_middle_of_the_write_keeps_the_previous_report_whole(tmp_path, monkeypatch):
    """Simula disco cheio: metade do conteúdo é gravada e a escrita falha.

    Com escrita direta no destino, o relatório anterior teria virado um JSON truncado.
    """
    output_path = tmp_path / "report.json"
    output_path.write_text('{"relatorio": "anterior"}', encoding="utf-8")

    def write_half_and_fail(self: Path, data: str, encoding: str | None = None) -> int:
        with self.open("w", encoding=encoding) as handle:
            handle.write(data[: len(data) // 2])
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "write_text", write_half_and_fail)

    with pytest.raises(OSError, match="No space left on device"):
        write_report(REPORT, output_path)

    monkeypatch.undo()
    assert output_path.read_text(encoding="utf-8") == '{"relatorio": "anterior"}'
    assert names_in(tmp_path) == ["report.json"]


def test_failure_in_the_final_swap_keeps_the_previous_report_and_removes_the_temporary(tmp_path, monkeypatch):
    output_path = tmp_path / "report.json"
    output_path.write_text('{"relatorio": "anterior"}', encoding="utf-8")

    def fail_to_replace(self: Path, target: Path) -> Path:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "replace", fail_to_replace)

    with pytest.raises(PermissionError):
        write_report(REPORT, output_path)

    assert output_path.read_text(encoding="utf-8") == '{"relatorio": "anterior"}'
    assert names_in(tmp_path) == ["report.json"]


def test_failure_without_a_previous_report_leaves_nothing_behind(tmp_path, monkeypatch):
    def fail_to_replace(self: Path, target: Path) -> Path:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "replace", fail_to_replace)

    with pytest.raises(PermissionError):
        write_report(REPORT, tmp_path / "report.json")

    assert names_in(tmp_path) == []


def test_output_that_is_a_directory_fails_without_leaving_a_temporary_file(tmp_path):
    output_is_a_directory = tmp_path / "saida"
    output_is_a_directory.mkdir()

    with pytest.raises(OSError):
        write_report(REPORT, output_is_a_directory)

    assert names_in(tmp_path) == ["saida"]
    assert output_is_a_directory.is_dir()


def test_cleanup_failure_does_not_hide_the_original_error(tmp_path, monkeypatch):
    """Se nem apagar o temporário der certo, o erro que sobe é o da gravação."""

    def fail_to_replace(self: Path, target: Path) -> Path:
        raise PermissionError(13, "falha na troca")

    def fail_to_unlink(self: Path, missing_ok: bool = False) -> None:
        raise OSError(5, "falha na limpeza")

    monkeypatch.setattr(Path, "replace", fail_to_replace)
    monkeypatch.setattr(Path, "unlink", fail_to_unlink)

    with pytest.raises(PermissionError, match="falha na troca"):
        write_report(REPORT, tmp_path / "report.json")
