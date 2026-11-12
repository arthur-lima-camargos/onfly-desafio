"""Testes unitários: cálculo de noites de quarto.

Regra: room_nights = (checkout_date - checkin_date).days * rooms, com diferença não inclusiva.
As datas ficam em ISO nos parâmetros para os casos lerem como o CSV.
"""

from datetime import date

import pytest

from onfly_report.services.stay_calculator import calculate_room_nights


def nights(checkin: str, checkout: str, rooms: int = 1) -> int:
    return calculate_room_nights(date.fromisoformat(checkin), date.fromisoformat(checkout), rooms)


@pytest.mark.parametrize(
    ("checkin", "checkout", "expected"),
    [
        pytest.param("2025-01-10", "2025-01-11", 1, id="uma-noite"),
        pytest.param("2025-01-10", "2025-01-13", 3, id="exemplo-do-readme-10-a-13-sao-3-noites"),
        pytest.param("2025-01-01", "2025-01-31", 30, id="primeiro-ao-ultimo-dia-do-mes"),
    ],
)
def test_nights_within_same_month(checkin, checkout, expected):
    """Dentro do mês a diferença é não inclusiva: o dia do check-out não conta."""
    assert nights(checkin, checkout) == expected


@pytest.mark.parametrize(
    ("checkin", "checkout", "expected"),
    [
        pytest.param("2025-01-30", "2025-02-02", 3, id="janeiro-para-fevereiro"),
        pytest.param("2025-01-31", "2025-02-01", 1, id="ultimo-dia-do-mes-para-dia-1"),
        pytest.param("2025-04-29", "2025-05-02", 3, id="saindo-de-mes-com-30-dias"),
        pytest.param("2025-03-29", "2025-04-02", 4, id="saindo-de-mes-com-31-dias"),
        pytest.param("2025-01-25", "2025-02-05", 11, id="dia-do-checkout-menor-que-dia-do-checkin"),
    ],
)
def test_nights_across_month_boundary(checkin, checkout, expected):
    """Na virada de mês o dia do check-out é menor que o do check-in; subtrair só o dia dá negativo."""
    assert nights(checkin, checkout) == expected


@pytest.mark.parametrize(
    ("checkin", "checkout", "expected"),
    [
        pytest.param("2024-12-31", "2025-01-01", 1, id="reveillon-uma-noite"),
        pytest.param("2024-12-30", "2025-01-02", 3, id="dezembro-para-janeiro-como-no-dataset"),
    ],
)
def test_nights_across_year_boundary(checkin, checkout, expected):
    """O dataset tem reservas que começam em dezembro de 2024 e terminam em 2025."""
    assert nights(checkin, checkout) == expected


@pytest.mark.parametrize(
    ("checkin", "checkout", "expected"),
    [
        pytest.param("2024-02-28", "2024-03-01", 2, id="ano-bissexto-inclui-29-de-fevereiro"),
        pytest.param("2025-02-28", "2025-03-01", 1, id="ano-nao-bissexto"),
        pytest.param("2024-02-29", "2024-03-01", 1, id="checkin-em-29-de-fevereiro"),
    ],
)
def test_nights_in_february(checkin, checkout, expected):
    """Fevereiro muda de tamanho conforme o ano; a conta precisa usar o calendário real."""
    assert nights(checkin, checkout) == expected


@pytest.mark.parametrize(
    ("checkin", "checkout", "expected"),
    [
        pytest.param("2025-03-28", "2025-04-04", 7, id="maior-estadia-do-dataset-7-noites"),
        pytest.param("2025-01-01", "2025-03-01", 59, id="dois-meses-com-mesmo-dia-subtrair-dia-daria-zero"),
        pytest.param("2025-01-01", "2026-01-01", 365, id="ano-inteiro-nao-bissexto"),
        pytest.param("2024-01-01", "2025-01-01", 366, id="ano-inteiro-bissexto"),
    ],
)
def test_nights_spanning_several_months(checkin, checkout, expected):
    """Estadias que cruzam mais de uma virada de mês somam o tamanho real de cada mês."""
    assert nights(checkin, checkout) == expected


@pytest.mark.parametrize(
    ("checkin", "checkout", "rooms", "expected"),
    [
        pytest.param("2025-01-10", "2025-01-13", 2, 6, id="dois-quartos-mesmo-mes"),
        pytest.param("2025-01-10", "2025-01-13", 3, 9, id="tres-quartos-maximo-do-dataset"),
        pytest.param("2025-01-30", "2025-02-02", 2, 6, id="dois-quartos-na-virada-de-mes"),
        pytest.param("2024-12-30", "2025-01-02", 3, 9, id="tres-quartos-na-virada-de-ano"),
    ],
)
def test_nights_are_multiplied_by_rooms(checkin, checkout, rooms, expected):
    """Cada quarto conta suas próprias noites."""
    assert nights(checkin, checkout, rooms) == expected


@pytest.mark.parametrize("rooms", [1, 2, 3])
def test_room_nights_are_proportional_to_rooms(rooms):
    """Dobrar os quartos dobra as noites: a multiplicação é aplicada depois da diferença de datas."""
    assert nights("2025-01-30", "2025-02-02", rooms) == rooms * nights("2025-01-30", "2025-02-02")


def test_returns_int():
    """room_nights é inteiro no relatório; a função não pode devolver timedelta nem float."""
    assert type(nights("2025-01-10", "2025-01-13")) is int
