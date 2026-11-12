"""Testes unitários: ranking de hotéis.

Regra: total_brl decrescente; empate por hotel_id ascendente; no máximo top_n itens.
Decisão: a ordem usa o total exato (Decimal), não o valor arredondado da serialização.
"""

from decimal import Decimal
from itertools import permutations

import pytest

from onfly_report.services.hotel_ranking import rank_hotels


def totals(**amounts: str) -> dict[str, Decimal]:
    return {hotel_id: Decimal(amount) for hotel_id, amount in amounts.items()}


# --- Ordem ------------------------------------------------------------------------------------


def test_highest_total_comes_first():
    assert rank_hotels(totals(H01="100.00", H02="300.00", H03="200.00"), top_n=3) == ["H02", "H03", "H01"]


def test_tie_is_broken_by_hotel_id_ascending():
    assert rank_hotels(totals(H03="500.00", H01="500.00", H02="500.00"), top_n=3) == ["H01", "H02", "H03"]


def test_tie_break_only_applies_among_equal_totals():
    """O hotel_id não passa na frente de um total maior."""
    ranking = rank_hotels(totals(H01="100.00", H02="900.00", H03="900.00", H04="50.00"), top_n=4)

    assert ranking == ["H02", "H03", "H01", "H04"]


def test_two_digit_hotel_ids_tie_in_string_order():
    """hotel_id é texto; com zero à esquerda (como no dataset) a ordem textual é a numérica."""
    assert rank_hotels(totals(H10="1.00", H09="1.00"), top_n=2) == ["H09", "H10"]


def test_result_does_not_depend_on_insertion_order():
    """O CSV pode vir em qualquer ordem; o ranking precisa ser determinístico."""
    amounts = [("H01", "100.00"), ("H02", "300.00"), ("H03", "300.00"), ("H04", "200.00")]

    rankings = {tuple(rank_hotels(totals(**dict(order)), top_n=4)) for order in permutations(amounts)}

    assert rankings == {("H02", "H03", "H04", "H01")}


# --- Exatidão (decisão: ordenar pelo valor exato) ----------------------------------------------


def test_sub_cent_difference_wins_over_hotel_id():
    """100.004 e 100.001 serializam como "100.00", mas o maior exato vem primeiro."""
    assert rank_hotels(totals(H01="100.001", H02="100.004"), top_n=2) == ["H02", "H01"]


def test_exact_tie_after_conversion_uses_hotel_id():
    """USD 100 * 5.42 e BRL 542 são o mesmo valor exato: empate de verdade, decidido por hotel_id."""
    ranking = rank_hotels(
        {"H02": Decimal("100.00") * Decimal("5.420000"), "H01": Decimal("542.00")},
        top_n=2,
    )

    assert ranking == ["H01", "H02"]


# --- Limite top_n -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("top_n", "expected"),
    [
        pytest.param(1, ["H03"], id="top-1"),
        pytest.param(2, ["H03", "H02"], id="top-menor-que-total-de-hoteis"),
        pytest.param(3, ["H03", "H02", "H01"], id="top-igual-ao-total-de-hoteis"),
        pytest.param(5, ["H03", "H02", "H01"], id="top-maior-que-total-de-hoteis-devolve-todos"),
    ],
)
def test_returns_at_most_top_n_hotels(top_n, expected):
    assert rank_hotels(totals(H01="100.00", H02="200.00", H03="300.00"), top_n=top_n) == expected


def test_tie_at_the_cut_lets_the_lowest_hotel_id_in():
    """Três hotéis empatados disputam a última vaga: entra o menor hotel_id, não o primeiro lido.

    Cortar antes de desempatar (ordenar só por valor, cortar e depois reordenar) deixaria H03 entrar.
    """
    ranking = rank_hotels(totals(H04="900.00", H03="500.00", H01="500.00", H02="500.00"), top_n=2)

    assert ranking == ["H04", "H01"]


def test_cut_happens_after_sorting():
    """O maior hotel entra no top mesmo se aparecer por último."""
    assert rank_hotels(totals(H01="1.00", H02="2.00", H03="3.00", H04="999.00"), top_n=1) == ["H04"]


def test_no_hotels_returns_empty_list():
    assert rank_hotels({}, top_n=5) == []


# --- Efeitos colaterais -----------------------------------------------------------------------


def test_does_not_mutate_input():
    original = totals(H01="100.00", H02="300.00")
    received = dict(original)

    rank_hotels(received, top_n=1)

    assert received == original
