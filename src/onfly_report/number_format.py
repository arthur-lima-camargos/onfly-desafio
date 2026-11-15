"""Formato dos números aceitos nos arquivos de entrada.

Decimal() e int() sozinhos aceitam "1_000.50", "1E+3", "+10" e dígitos Unicode ("２"); uma
exportação com esses valores está corrompida, não é um número a interpretar. Aqui só passam
dígitos ASCII com ponto decimal opcional, em tamanho limitado.
"""

from __future__ import annotations

import re
from decimal import Decimal

# Valor de reserva: até 15 dígitos inteiros e 6 decimais (a escala da tabela de câmbio).
PLAIN_AMOUNT = re.compile(r"[0-9]{1,15}(\.[0-9]{1,6})?")
# Taxa de câmbio: até 9 dígitos inteiros e 12 decimais (moedas com taxa muito pequena).
PLAIN_RATE = re.compile(r"[0-9]{1,9}(\.[0-9]{1,12})?")
# Quantidade de quartos: até 4 dígitos.
PLAIN_ROOMS = re.compile(r"[0-9]{1,4}")

# Precisão da aritmética de dinheiro. Com a entrada limitada acima, valor e taxa têm no máximo 21
# dígitos cada e o produto, 42; 60 dígitos somam 10^18 reservas sem arredondar. A precisão padrão
# do Decimal (28) arredondaria em silêncio e falharia no quantize com valores grandes.
MONEY_PRECISION = 60


def parse_plain_decimal(text: str, pattern: re.Pattern[str]) -> Decimal | None:
    """Devolve o Decimal exato, ou None se o texto estiver fora do formato."""
    return Decimal(text) if pattern.fullmatch(text) else None


def parse_plain_int(text: str, pattern: re.Pattern[str]) -> int | None:
    """Devolve o inteiro, ou None se o texto estiver fora do formato."""
    return int(text) if pattern.fullmatch(text) else None
