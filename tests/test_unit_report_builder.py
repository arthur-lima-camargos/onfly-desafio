"""Testes unitários: ReportBuilder com fontes em memória (sem disco nem subprocess).

As fontes fake satisfazem os Protocols ReservationSource e RateSource por estrutura.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, getcontext

import pytest
from helpers import BASE

from onfly_report.models import RawRow
from onfly_report.services.report_builder import ReportBuilder

RATES = {"BRL": Decimal("1.000000"), "USD": Decimal("5.420000"), "EUR": Decimal("5.880000")}
FIXED_NOW = datetime(2025, 7, 1, 10, 0, 0, tzinfo=timezone(timedelta(hours=-3)))


class InMemoryReservations:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = [RawRow(line_number=index + 2, values={**BASE, **row}) for index, row in enumerate(rows)]

    def read(self) -> list[RawRow]:
        return self._rows


class InMemoryRates:
    def __init__(self, rates: dict[str, Decimal] = RATES) -> None:
        self._rates = rates

    def read(self) -> dict[str, Decimal]:
        return self._rates


def build(
    rows: list[dict[str, str]],
    top_n: int = 5,
    now: datetime | None = FIXED_NOW,
    rates: dict[str, Decimal] = RATES,
) -> dict:
    return ReportBuilder(InMemoryReservations(rows), InMemoryRates(rates), top_n=top_n, now=now).build()


def half_up_money(value: int, scale: int) -> str:
    """Formata value / 10**scale com 2 casas half-up, só com inteiros (oráculo sem Decimal)."""
    cents, remainder = divmod(value, 10 ** (scale - 2))
    cents += 2 * remainder >= 10 ** (scale - 2)
    return f"{cents // 100}.{cents % 100:02d}"


# --- by_month ---------------------------------------------------------------------------------


def test_by_month_uses_checkin_month_and_keeps_all_nights_there():
    """Estadia de 30/12 a 02/01 conta inteira em 2024-12: o relatório não rateia noites entre meses."""
    report = build([{"checkin_date": "2024-12-30", "checkout_date": "2025-01-02", "amount": "300.00"}])

    assert report["by_month"] == [{"month": "2024-12", "reservations": 1, "room_nights": 3, "total_brl": "300.00"}]


def test_by_month_is_sorted_ascending_across_years():
    report = build(
        [
            {"reservation_id": "R-1", "checkin_date": "2025-02-10", "checkout_date": "2025-02-11"},
            {"reservation_id": "R-2", "checkin_date": "2024-12-10", "checkout_date": "2024-12-11"},
            {"reservation_id": "R-3", "checkin_date": "2025-01-10", "checkout_date": "2025-01-11"},
        ]
    )

    assert [month["month"] for month in report["by_month"]] == ["2024-12", "2025-01", "2025-02"]


def test_by_month_aggregates_reservations_of_the_same_month():
    report = build(
        [
            {"reservation_id": "R-1", "checkin_date": "2025-01-05", "checkout_date": "2025-01-07", "amount": "200.00"},
            {
                "reservation_id": "R-2",
                "checkin_date": "2025-01-20",
                "checkout_date": "2025-01-21",
                "rooms": "2",
                "currency": "USD",
                "amount": "50.00",
            },
        ]
    )

    assert report["by_month"] == [{"month": "2025-01", "reservations": 2, "room_nights": 4, "total_brl": "471.00"}]


# --- summary ----------------------------------------------------------------------------------


def test_average_nightly_rate_is_total_divided_by_nights():
    """100 / 3 = 33.333... -> "33.33"."""
    report = build([{"checkin_date": "2025-01-10", "checkout_date": "2025-01-13", "amount": "100.00"}])

    assert report["summary"]["average_nightly_rate_brl"] == "33.33"


def test_average_is_rounded_half_up():
    """200 / 3 = 66.666... -> "66.67"; 0.125 por noite -> "0.13" (half-up, não half-even)."""
    report = build([{"checkin_date": "2025-01-10", "checkout_date": "2025-01-13", "amount": "200.00"}])
    assert report["summary"]["average_nightly_rate_brl"] == "66.67"

    report = build([{"checkin_date": "2025-01-10", "checkout_date": "2025-01-18", "amount": "1.00"}])
    assert report["summary"]["average_nightly_rate_brl"] == "0.13"


def test_average_uses_exact_total_not_rounded_total():
    """USD 0.02 = BRL 0.1084 em 2 noites: média exata 0.0542 -> "0.05"; a partir de "0.11" daria "0.06"."""
    report = build([{"currency": "USD", "amount": "0.02", "checkin_date": "2025-01-10", "checkout_date": "2025-01-12"}])

    assert report["summary"]["total_amount_brl"] == "0.11"
    assert report["summary"]["average_nightly_rate_brl"] == "0.05"


def test_totals_sum_exact_values_and_round_only_at_the_end():
    """Duas reservas de USD 0.01 (0.0542 cada): soma exata 0.1084 -> "0.11"; arredondar antes daria "0.10"."""
    report = build(
        [
            {"reservation_id": "R-1", "currency": "USD", "amount": "0.01"},
            {"reservation_id": "R-2", "currency": "USD", "amount": "0.01"},
        ]
    )

    assert report["summary"]["total_amount_brl"] == "0.11"
    assert report["by_month"][0]["total_brl"] == "0.11"
    assert report["top_hotels"][0]["total_brl"] == "0.11"


# --- Precisão ---------------------------------------------------------------------------------


def test_largest_amount_times_largest_rate_is_summed_exactly_over_a_thousand_reservations():
    """Pior caso que a entrada permite: 21 dígitos x 21 dígitos, 1000 vezes, conferido com inteiros."""
    rows = [{"reservation_id": f"R-{n}", "currency": "XXX", "amount": "999999999999999.999999"} for n in range(1000)]

    report = build(rows, rates={"XXX": Decimal("999999999.999999999999")})

    expected_total = 1000 * 999999999999999999999 * 999999999999999999999  # escala 10**-18
    assert report["summary"]["total_amount_brl"] == half_up_money(expected_total, scale=18)
    assert report["by_month"][0]["total_brl"] == half_up_money(expected_total, scale=18)
    assert report["top_hotels"][0]["total_brl"] == half_up_money(expected_total, scale=18)


def test_average_of_a_total_above_28_digits_is_exact_to_the_cent():
    """Total de 29 dígitos dividido por 3 noites: a precisão padrão do Decimal já teria arredondado o total."""
    rows = [
        {"reservation_id": f"R-{n}", "currency": "USD", "amount": "999999999999999.999999"} for n in range(3)
    ]

    summary = build(rows)["summary"]

    total = 3 * 999999999999999999999 * 5420000  # escala 10**-12
    assert summary["total_room_nights"] == 3
    assert summary["average_nightly_rate_brl"] == half_up_money(total // 3, scale=12)


def test_build_does_not_change_the_decimal_precision_of_the_caller():
    before = getcontext().prec

    build([{}])

    assert getcontext().prec == before == 28


def test_empty_source_produces_empty_report():
    report = build([])

    assert report["summary"] == {
        "total_reservations": 0,
        "confirmed_reservations": 0,
        "cancelled_reservations": 0,
        "no_show_reservations": 0,
        "total_room_nights": 0,
        "total_amount_brl": "0.00",
        "average_nightly_rate_brl": "0.00",
    }
    assert report["by_month"] == []
    assert report["top_hotels"] == []


# --- top_hotels -------------------------------------------------------------------------------


def test_top_n_is_passed_to_the_ranking():
    rows = [{"reservation_id": f"R-{index}", "hotel_id": f"H{index:02d}"} for index in range(1, 8)]

    assert len(build(rows, top_n=5)["top_hotels"]) == 5
    assert len(build(rows, top_n=2)["top_hotels"]) == 2


def test_top_hotel_item_carries_name_and_nights():
    report = build(
        [
            {
                "hotel_id": "H09",
                "hotel_name": "Hotel Lisboa, Centro",
                "checkin_date": "2025-01-30",
                "checkout_date": "2025-02-02",
                "rooms": "2",
                "currency": "EUR",
                "amount": "150.00",
            }
        ]
    )

    assert report["top_hotels"] == [
        {"hotel_id": "H09", "hotel_name": "Hotel Lisboa, Centro", "room_nights": 6, "total_brl": "882.00"}
    ]


# --- metadados --------------------------------------------------------------------------------


def test_report_version_and_injected_generated_at():
    report = build([])

    assert report["report_version"] == "1.0"
    assert report["generated_at"] == "2025-07-01T10:00:00-03:00"


def test_generated_at_defaults_to_now_with_fixed_minus_three_offset():
    before = datetime.now(timezone.utc).replace(microsecond=0)
    generated_at = datetime.fromisoformat(build([], now=None)["generated_at"])
    after = datetime.now(timezone.utc)

    assert generated_at.utcoffset() == timedelta(hours=-3)
    assert before <= generated_at <= after


@pytest.mark.parametrize("money_field", ["total_amount_brl", "average_nightly_rate_brl"])
def test_money_is_serialized_as_string_with_two_decimals(money_field):
    report = build([{"amount": "1234.5"}])

    value = report["summary"][money_field]
    assert isinstance(value, str)
    assert value == "1234.50"


# --- Inconsistências suspeitas ----------------------------------------------------------------


def test_divergent_hotel_name_uses_the_first_one_in_file_order():
    """Mesmo que a primeira linha do hotel não seja faturável, o nome dela é o que vale."""
    report = build(
        [
            {"reservation_id": "R-1", "hotel_name": "Hotel Primeiro", "status": "CANCELLED"},
            {"reservation_id": "R-2", "hotel_name": "Hotel Segundo"},
            {"reservation_id": "R-3", "hotel_name": "Hotel Terceiro"},
        ]
    )

    assert report["top_hotels"][0]["hotel_name"] == "Hotel Primeiro"


def test_inconsistencies_are_logged_as_warnings_and_report_is_still_built(caplog):
    rows = [{"reservation_id": "R-1"}, {"reservation_id": "R-1", "amount": "50.00"}]

    with caplog.at_level("WARNING", logger="onfly_report"):
        report = build(rows)

    assert [record.levelname for record in caplog.records] == ["WARNING"]
    assert "reservation_id repetido" in caplog.records[0].getMessage()
    assert report["summary"]["total_reservations"] == 2
    assert report["summary"]["total_amount_brl"] == "150.00"


def test_consistent_input_logs_nothing(caplog):
    with caplog.at_level("WARNING", logger="onfly_report"):
        build([{"reservation_id": "R-1"}, {"reservation_id": "R-2"}])

    assert caplog.records == []
