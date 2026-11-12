"""Testes ponta a ponta: top_hotels no relatório."""

from helpers import run_cli


def test_hotel_total_is_the_sum_of_its_reservations(tmp_path):
    """O ranking compara a soma por hotel, não a maior reserva isolada."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "600.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "600.00"},
            {"reservation_id": "R-3", "hotel_id": "H02", "hotel_name": "Hotel B", "amount": "1000.00"},
        ],
    )

    assert report["top_hotels"] == [
        {"hotel_id": "H01", "hotel_name": "Hotel A", "room_nights": 2, "total_brl": "1200.00"},
        {"hotel_id": "H02", "hotel_name": "Hotel B", "room_nights": 1, "total_brl": "1000.00"},
    ]


def test_tie_across_currencies_is_broken_by_hotel_id(tmp_path):
    """USD 100 vira BRL 542: empate exato com o hotel em BRL, decidido por hotel_id."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H02", "currency": "USD", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "currency": "BRL", "amount": "542.00"},
        ],
    )

    assert [(hotel["hotel_id"], hotel["total_brl"]) for hotel in report["top_hotels"]] == [
        ("H01", "542.00"),
        ("H02", "542.00"),
    ]


def test_ranking_uses_exact_totals_not_serialized_ones(tmp_path):
    """Decisão: ordenar pelo valor exato. USD 0.01 = BRL 0.0542 > BRL 0.05, embora os dois saiam "0.05".

    Garante que o ReportBuilder entrega o total exato ao ranking, não o valor já arredondado.
    """
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "currency": "BRL", "amount": "0.05"},
            {"reservation_id": "R-2", "hotel_id": "H02", "currency": "USD", "amount": "0.01"},
        ],
    )

    assert [(hotel["hotel_id"], hotel["total_brl"]) for hotel in report["top_hotels"]] == [
        ("H02", "0.05"),
        ("H01", "0.05"),
    ]


def test_non_billable_amount_does_not_change_the_order(tmp_path):
    """O NO_SHOW de R$ 5.000 do H02 não pode puxá-lo para cima: só o confirmado conta na ordem."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "amount": "50.00"},
            {"reservation_id": "R-3", "hotel_id": "H02", "status": "NO_SHOW", "amount": "5000.00"},
        ],
    )

    assert [(hotel["hotel_id"], hotel["total_brl"]) for hotel in report["top_hotels"]] == [
        ("H01", "100.00"),
        ("H02", "50.00"),
    ]


def test_top_larger_than_hotel_count_returns_all_hotels(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "amount": "200.00"},
        ],
        top=10,
    )

    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H02", "H01"]


def test_top_one_keeps_only_the_highest(tmp_path):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "amount": "200.00"},
            {"reservation_id": "R-3", "hotel_id": "H03", "amount": "150.00"},
        ],
        top=1,
    )

    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H02"]
