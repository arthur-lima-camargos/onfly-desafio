"""Testes unitários: serialização dos números exatos no JSON do contrato.

O ReportData é montado à mão, sem passar pela agregação: o que se testa aqui é só arredondar,
ordenar e nomear os campos.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import get_type_hints

import pytest

from onfly_report.models import ReservationStatus
from onfly_report.services.aggregation import ReportData, Totals
from onfly_report.services.report_serializer import (
    HotelJson,
    MonthJson,
    ReportJson,
    SummaryJson,
    format_generated_at,
    format_money,
    serialize,
)

MINUS_THREE = timezone(timedelta(hours=-3))
NOW = datetime(2025, 7, 1, 10, 0, 0, tzinfo=MINUS_THREE)

DATA = ReportData(
    total_reservations=6,
    status_counts={ReservationStatus.CONFIRMED: 3, ReservationStatus.CANCELLED: 2, ReservationStatus.NO_SHOW: 1},
    billable=Totals(reservations=3, room_nights=3, amount_brl=Decimal("100.005")),
    by_month={
        "2025-02": Totals(reservations=1, room_nights=1, amount_brl=Decimal("0.004")),
        "2024-12": Totals(reservations=2, room_nights=2, amount_brl=Decimal("100.001")),
    },
    by_hotel={
        "H01": Totals(reservations=2, room_nights=2, amount_brl=Decimal("100.001")),
        "H02": Totals(reservations=1, room_nights=1, amount_brl=Decimal("0.004")),
    },
    hotel_names={"H01": "Hotel Um", "H02": "Hotel Dois", "H03": "Hotel só com canceladas"},
)

EMPTY = ReportData(total_reservations=0, status_counts={}, billable=Totals(), by_month={}, by_hotel={}, hotel_names={})


def serialized(data: ReportData = DATA, top_hotel_ids: tuple[str, ...] = ("H01", "H02")) -> ReportJson:
    return serialize(data, top_hotel_ids, NOW)


# --- Dinheiro ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("0", "0.00", id="zero"),
        pytest.param("10", "10.00", id="inteiro-ganha-duas-casas"),
        pytest.param("0.125", "0.13", id="half-up-sobe-onde-half-even-desceria"),
        pytest.param("0.135", "0.14", id="half-up-sobe"),
        pytest.param("0.124", "0.12", id="abaixo-da-metade-desce"),
        pytest.param("0.1249999999", "0.12", id="quase-metade-desce"),
        pytest.param("1234567.5", "1234567.50", id="sem-separador-de-milhar"),
        pytest.param("0.004", "0.00", id="menos-de-meio-centavo-vira-zero"),
    ],
)
def test_money_is_rounded_half_up_to_two_places(value, expected):
    assert format_money(Decimal(value)) == expected


# --- generated_at -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        pytest.param(NOW, "2025-07-01T10:00:00-03:00", id="ja-em-menos-tres"),
        pytest.param(datetime(2025, 7, 1, 13, 0, 0, tzinfo=timezone.utc), "2025-07-01T10:00:00-03:00", id="utc"),
        pytest.param(
            datetime(2025, 7, 1, 22, 0, 0, tzinfo=timezone(timedelta(hours=9))),
            "2025-07-01T10:00:00-03:00",
            id="toquio-mais-nove",
        ),
        pytest.param(
            datetime(2025, 7, 1, 1, 30, 0, tzinfo=timezone.utc), "2025-06-30T22:30:00-03:00", id="utc-muda-o-dia"
        ),
        pytest.param(
            datetime(2025, 7, 1, 10, 0, 0, 999999, tzinfo=MINUS_THREE),
            "2025-07-01T10:00:00-03:00",
            id="microssegundos-sao-cortados",
        ),
    ],
)
def test_generated_at_is_converted_to_the_fixed_minus_three_offset(moment, expected):
    """Antes, um instante em outro fuso saía com o offset dele (ex.: +00:00), fora do contrato."""
    assert format_generated_at(moment) == expected


def test_generated_at_without_timezone_still_comes_out_in_minus_three():
    """Sem fuso, o instante é lido como hora local da máquina; o offset de saída é sempre -03:00."""
    generated_at = datetime.fromisoformat(format_generated_at(datetime(2025, 7, 1, 10, 0, 0)))

    assert generated_at.utcoffset() == timedelta(hours=-3)


# --- Relatório --------------------------------------------------------------------------------


def test_summary_carries_counts_and_rounds_money_only_here():
    assert serialized()["summary"] == {
        "total_reservations": 6,
        "confirmed_reservations": 3,
        "cancelled_reservations": 2,
        "no_show_reservations": 1,
        "total_room_nights": 3,
        "total_amount_brl": "100.01",
        "average_nightly_rate_brl": "33.34",
    }


def test_total_is_rounded_from_the_exact_sum_not_from_the_rounded_parts():
    """Meses: "100.00" + "0.00" = 100.00, mas o total exato 100.005 sai "100.01"."""
    report = serialized()

    assert [month["total_brl"] for month in report["by_month"]] == ["100.00", "0.00"]
    assert report["summary"]["total_amount_brl"] == "100.01"


def test_by_month_is_sorted_ascending_whatever_the_aggregation_order():
    assert serialized()["by_month"] == [
        {"month": "2024-12", "reservations": 2, "room_nights": 2, "total_brl": "100.00"},
        {"month": "2025-02", "reservations": 1, "room_nights": 1, "total_brl": "0.00"},
    ]


def test_top_hotels_follow_the_ranking_order_received():
    """A ordem é decidida pelo ranking; o serializador não reordena."""
    report = serialized(top_hotel_ids=("H02", "H01"))

    assert report["top_hotels"] == [
        {"hotel_id": "H02", "hotel_name": "Hotel Dois", "room_nights": 1, "total_brl": "0.00"},
        {"hotel_id": "H01", "hotel_name": "Hotel Um", "room_nights": 2, "total_brl": "100.00"},
    ]


def test_only_the_ranked_hotels_are_serialized():
    assert [hotel["hotel_id"] for hotel in serialized(top_hotel_ids=("H01",))["top_hotels"]] == ["H01"]


def test_status_missing_from_the_counts_is_serialized_as_zero():
    data = ReportData(
        total_reservations=1,
        status_counts={ReservationStatus.CONFIRMED: 1},
        billable=Totals(reservations=1, room_nights=1, amount_brl=Decimal("10")),
        by_month={},
        by_hotel={},
        hotel_names={},
    )

    summary = serialized(data, top_hotel_ids=())["summary"]

    assert (summary["cancelled_reservations"], summary["no_show_reservations"]) == (0, 0)


def test_empty_data_serializes_to_zeros_and_empty_lists():
    report = serialized(EMPTY, top_hotel_ids=())

    assert report["summary"]["total_amount_brl"] == "0.00"
    assert report["summary"]["average_nightly_rate_brl"] == "0.00"
    assert report["by_month"] == []
    assert report["top_hotels"] == []


def test_keys_come_out_in_the_order_of_the_readme_example():
    """A ordem das chaves não é contrato do JSON, mas manter a do README facilita comparar à mão."""
    report = json.loads(json.dumps(serialized()))

    assert list(report) == ["report_version", "generated_at", "summary", "by_month", "top_hotels"]
    assert list(report["summary"]) == [
        "total_reservations",
        "confirmed_reservations",
        "cancelled_reservations",
        "no_show_reservations",
        "total_room_nights",
        "total_amount_brl",
        "average_nightly_rate_brl",
    ]


def test_report_version_and_generated_at():
    report = serialized()

    assert report["report_version"] == "1.0"
    assert report["generated_at"] == "2025-07-01T10:00:00-03:00"


# --- TypedDict: o contrato que o mypy verifica -------------------------------------------------


@pytest.mark.parametrize(
    ("typed_dict", "documented"),
    [
        pytest.param(
            ReportJson,
            {
                "report_version": str,
                "generated_at": str,
                "summary": SummaryJson,
                "by_month": list[MonthJson],
                "top_hotels": list[HotelJson],
            },
            id="relatorio",
        ),
        pytest.param(
            SummaryJson,
            {
                "total_reservations": int,
                "confirmed_reservations": int,
                "cancelled_reservations": int,
                "no_show_reservations": int,
                "total_room_nights": int,
                "total_amount_brl": str,
                "average_nightly_rate_brl": str,
            },
            id="summary",
        ),
        pytest.param(MonthJson, {"month": str, "reservations": int, "room_nights": int, "total_brl": str}, id="mes"),
        pytest.param(HotelJson, {"hotel_id": str, "hotel_name": str, "room_nights": int, "total_brl": str}, id="hotel"),
    ],
)
def test_typed_dicts_declare_exactly_the_documented_fields_and_types(typed_dict, documented):
    """Dinheiro é str e contagem é int no README; um campo a mais ou a menos no tipo quebra aqui."""
    assert get_type_hints(typed_dict) == documented
    assert typed_dict.__required_keys__ == frozenset(documented)
