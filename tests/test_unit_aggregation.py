"""Testes unitários: agregação das reservas em números exatos, sem arredondar nem formatar."""

from decimal import Decimal

import pytest
from helpers import BASE

from onfly_report.models import RawRow, Reservation, ReservationStatus
from onfly_report.services.aggregation import ReportData, Totals, aggregate
from onfly_report.services.row_parser import RowParser

RATES = {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}


def reservations(*rows: dict[str, str]) -> list[Reservation]:
    parser = RowParser()
    return [parser.parse(RawRow(line_number=index + 2, values={**BASE, **row})) for index, row in enumerate(rows)]


def aggregated(*rows: dict[str, str]) -> ReportData:
    return aggregate(reservations(*rows), RATES)


# --- Totals -----------------------------------------------------------------------------------


def test_totals_start_at_zero():
    assert Totals() == Totals(reservations=0, room_nights=0, amount_brl=Decimal("0"))


def test_add_counts_one_reservation_and_accumulates_nights_and_amount():
    totals = Totals()

    totals.add(3, Decimal("100.10"))
    totals.add(2, Decimal("0.005"))

    assert totals == Totals(reservations=2, room_nights=5, amount_brl=Decimal("100.105"))


def test_each_totals_has_its_own_accumulator():
    """O padrão Decimal("0") é imutável: somar em um Totals não vaza para outro."""
    first, second = Totals(), Totals()

    first.add(1, Decimal("10"))

    assert second == Totals()


def test_average_is_amount_divided_by_nights_without_rounding():
    totals = Totals(reservations=1, room_nights=3, amount_brl=Decimal("100"))

    assert totals.average_nightly_rate_brl == Decimal("100") / 3
    assert totals.average_nightly_rate_brl != Decimal("33.33")


def test_average_without_nights_is_zero_instead_of_division_by_zero():
    """README: sem noites, a diária média é "0.00"."""
    assert Totals(reservations=1, room_nights=0, amount_brl=Decimal("50")).average_nightly_rate_brl == Decimal("0")


# --- Contagem por status ----------------------------------------------------------------------


def test_every_reservation_counts_in_total_and_in_its_status():
    data = aggregated(
        {"reservation_id": "R-1"},
        {"reservation_id": "R-2"},
        {"reservation_id": "R-3", "status": "CANCELLED"},
        {"reservation_id": "R-4", "status": "NO_SHOW"},
    )

    assert data.total_reservations == 4
    assert data.status_counts == {
        ReservationStatus.CONFIRMED: 2,
        ReservationStatus.CANCELLED: 1,
        ReservationStatus.NO_SHOW: 1,
    }


@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW"])
def test_non_billable_reservation_adds_nothing_to_nights_or_amount(status):
    data = aggregated({"status": status, "amount": "999.00"})

    assert data.billable == Totals()
    assert data.by_month == {}
    assert data.by_hotel == {}


# --- Somas das faturáveis ---------------------------------------------------------------------


def test_billable_totals_use_room_nights_and_amount_converted_to_brl():
    data = aggregated(
        {"reservation_id": "R-1", "checkout_date": "2025-01-13", "rooms": "2", "amount": "100.00", "currency": "USD"},
        {"reservation_id": "R-2", "amount": "50.00"},
    )

    assert data.billable == Totals(reservations=2, room_nights=7, amount_brl=Decimal("592.00"))


def test_amounts_are_kept_exact_beyond_two_decimal_places():
    """USD 0.01 a 5.42 = 0.0542: a agregação não arredonda; isso é da serialização."""
    data = aggregated({"currency": "USD", "amount": "0.01"})

    assert data.billable.amount_brl == Decimal("0.0542")
    assert str(data.billable.amount_brl) == "0.05420000"


def test_reservation_goes_whole_into_the_checkin_month():
    """Estadia de 30/12 a 02/01: as 3 noites e o valor ficam em 2024-12, nada em 2025-01."""
    data = aggregated({"checkin_date": "2024-12-30", "checkout_date": "2025-01-02", "amount": "300.00"})

    assert data.by_month == {"2024-12": Totals(reservations=1, room_nights=3, amount_brl=Decimal("300.00"))}


def test_months_and_hotels_are_accumulated_separately():
    data = aggregated(
        {"reservation_id": "R-1", "hotel_id": "H01", "amount": "100.00"},
        {"reservation_id": "R-2", "hotel_id": "H02", "amount": "40.00"},
        {
            "reservation_id": "R-3",
            "hotel_id": "H01",
            "amount": "10.00",
            "checkin_date": "2025-02-01",
            "checkout_date": "2025-02-03",
        },
    )

    assert data.by_month == {
        "2025-01": Totals(reservations=2, room_nights=2, amount_brl=Decimal("140.00")),
        "2025-02": Totals(reservations=1, room_nights=2, amount_brl=Decimal("10.00")),
    }
    assert data.by_hotel == {
        "H01": Totals(reservations=2, room_nights=3, amount_brl=Decimal("110.00")),
        "H02": Totals(reservations=1, room_nights=1, amount_brl=Decimal("40.00")),
    }


def test_month_and_hotel_totals_add_up_to_the_billable_total():
    data = aggregated(
        {"reservation_id": "R-1", "hotel_id": "H01", "currency": "USD", "amount": "0.01"},
        {
            "reservation_id": "R-2",
            "hotel_id": "H02",
            "currency": "EUR",
            "amount": "0.01",
            "checkin_date": "2025-03-01",
            "checkout_date": "2025-03-04",
        },
        {"reservation_id": "R-3", "hotel_id": "H03", "status": "CANCELLED"},
    )

    for groups in (data.by_month, data.by_hotel):
        assert sum(totals.reservations for totals in groups.values()) == data.billable.reservations
        assert sum(totals.room_nights for totals in groups.values()) == data.billable.room_nights
        assert sum(totals.amount_brl for totals in groups.values()) == data.billable.amount_brl


def test_zero_night_reservation_counts_as_billable_with_its_amount():
    """Day use: 0 noites, mas a reserva e o valor entram."""
    data = aggregated({"checkout_date": "2025-01-10", "amount": "80.00"})

    assert data.billable == Totals(reservations=1, room_nights=0, amount_brl=Decimal("80.00"))


# --- Nomes de hotel ---------------------------------------------------------------------------


def test_hotel_name_is_the_first_one_in_file_order():
    data = aggregated(
        {"reservation_id": "R-1", "hotel_id": "H01", "hotel_name": "Primeiro"},
        {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Segundo"},
    )

    assert data.hotel_names == {"H01": "Primeiro"}


def test_first_name_counts_even_when_that_reservation_is_not_billable():
    """O nome vem da primeira linha do hotel no arquivo, faturável ou não."""
    data = aggregated(
        {"reservation_id": "R-1", "hotel_id": "H01", "hotel_name": "Da cancelada", "status": "CANCELLED"},
        {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Da confirmada"},
    )

    assert data.hotel_names == {"H01": "Da cancelada"}
    assert list(data.by_hotel) == ["H01"]


def test_hotel_with_only_non_billable_reservations_has_no_totals():
    data = aggregated({"hotel_id": "H09", "status": "NO_SHOW"})

    assert "H09" in data.hotel_names
    assert "H09" not in data.by_hotel


# --- Bordas -----------------------------------------------------------------------------------


def test_empty_file_aggregates_to_zeros():
    data = aggregate([], RATES)

    assert data == ReportData(
        total_reservations=0, status_counts={}, billable=Totals(), by_month={}, by_hotel={}, hotel_names={}
    )


def test_aggregation_does_not_mutate_the_rate_table():
    rates = dict(RATES)

    aggregate(reservations({"currency": "USD"}), rates)

    assert rates == RATES
