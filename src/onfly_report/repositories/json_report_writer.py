"""Gravação do relatório JSON."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from pathlib import Path


def write_report(report: Mapping[str, object], output_path: Path) -> None:
    """Grava o relatório de forma atômica: fica o arquivo novo inteiro ou o anterior intacto.

    O conteúdo vai para um arquivo temporário no mesmo diretório e só então substitui o destino.
    Escrever direto no destino deixaria um JSON truncado se a gravação falhasse no meio.
    """
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(output_path.name + ".tmp")
    try:
        temporary_path.write_text(payload, encoding="utf-8")
        # No mesmo diretório, a troca é uma operação única do sistema de arquivos.
        temporary_path.replace(output_path)
    except OSError:
        with contextlib.suppress(OSError):
            temporary_path.unlink(missing_ok=True)
        raise
