"""Testes ponta a ponta: efeito dos status em cada parte do relatório.

README: CANCELLED e NO_SHOW contam em total_reservations e nas contagens por status, mas não
entram em noites, valores, by_month nem top_hotels.
"""

import pytest
from helpers import run_cli


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_non_billable_status_is_counted_but_not_aggregated(tmp_path, status):
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "checkin_date": "2025-01-10", "checkout_date": "2025-01-12"},
            {
                "reservation_id": "R-2",
                "status": status,
                "hotel_id": "H02",
                "checkin_date": "2025-02-10",
                "checkout_date": "2025-02-15",
                "rooms": "3",
                "amount": "5000.00",
            },
        ],
    )

    assert report["summary"]["total_reservations"] == 2
    assert report["summary"]["total_room_nights"] == 2
    assert report["summary"]["total_amount_brl"] == "100.00"
    assert report["summary"]["average_nightly_rate_brl"] == "50.00"
    assert [month["month"] for month in report["by_month"]] == ["2025-01"]
    assert [hotel["hotel_id"] for hotel in report["top_hotels"]] == ["H01"]


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_non_billable_status_is_excluded_inside_shared_hotel_and_month(tmp_path, status):
    """Mesmo hotel e mesmo mês: o grupo existe, mas só a reserva CONFIRMED entra nele.

    Na amostra do README, janeiro tem 11 reservas e by_month mostra 8, só as confirmadas.
    """
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "checkin_date": "2025-01-10", "checkout_date": "2025-01-12"},
            {
                "reservation_id": "R-2",
                "status": status,
                "hotel_id": "H01",
                "checkin_date": "2025-01-20",
                "checkout_date": "2025-01-25",
                "rooms": "2",
                "amount": "3000.00",
            },
        ],
    )

    assert report["by_month"] == [{"month": "2025-01", "reservations": 1, "room_nights": 2, "total_brl": "100.00"}]
    assert report["top_hotels"] == [
        {"hotel_id": "H01", "hotel_name": "Hotel Teste", "room_nights": 2, "total_brl": "100.00"}
    ]


def test_status_counts_add_up_to_total(tmp_path):
    statuses = ["CONFIRMED", "CONFIRMED", "CANCELLED", "NO_SHOW", "NO_SHOW", "NO_SHOW"]
    report = run_cli(
        tmp_path,
        [{"reservation_id": f"R-{index}", "status": status} for index, status in enumerate(statuses)],
    )

    summary = report["summary"]
    assert (summary["confirmed_reservations"], summary["cancelled_reservations"], summary["no_show_reservations"]) == (
        2,
        1,
        3,
    )
    assert summary["total_reservations"] == len(statuses)


def test_report_without_confirmed_reservations_is_all_zero(tmp_path):
    """Sem CONFIRMED não há noites: média "0.00" (sem divisão por zero) e listas vazias."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "status": "CANCELLED"},
            {"reservation_id": "R-2", "status": "NO_SHOW"},
        ],
    )

    assert report["summary"] == {
        "total_reservations": 2,
        "confirmed_reservations": 0,
        "cancelled_reservations": 1,
        "no_show_reservations": 1,
        "total_room_nights": 0,
        "total_amount_brl": "0.00",
        "average_nightly_rate_brl": "0.00",
    }
    assert report["by_month"] == []
    assert report["top_hotels"] == []
