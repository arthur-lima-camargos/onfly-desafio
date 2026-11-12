"""Regressão no dataset real (data/reservas_hoteis.csv).

O esperado é recalculado aqui por um oráculo independente: leitura com csv puro e as regras do
README escritas da forma mais direta possível, sem reaproveitar nada de onfly_report. Comparar com
um JSON gerado pelo próprio CLI seria tautológico.
"""

import csv
import json
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from cli_support import run_cli_args
from helpers import PROJECT_ROOT

DATA = PROJECT_ROOT / "data"


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    with (DATA / "reservas_hoteis.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def oracle(rows) -> dict:
    with (DATA / "taxas_cambio.csv").open(encoding="utf-8", newline="") as handle:
        rates = {line["currency"]: Decimal(line["rate_to_brl"]) for line in csv.DictReader(handle)}

    nights_total, amount_total = 0, Decimal(0)
    months: dict[str, list] = defaultdict(lambda: [0, 0, Decimal(0)])
    hotels: dict[str, list] = defaultdict(lambda: ["", 0, Decimal(0)])

    for line in rows:
        if line["status"] != "CONFIRMED":
            continue
        nights = (date.fromisoformat(line["checkout_date"]) - date.fromisoformat(line["checkin_date"])).days
        nights *= int(line["rooms"])
        amount = Decimal(line["amount"]) * rates[line["currency"]]

        nights_total += nights
        amount_total += amount
        month = months[line["checkin_date"][:7]]
        month[0], month[1], month[2] = month[0] + 1, month[1] + nights, month[2] + amount
        hotel = hotels[line["hotel_id"]]
        hotel[0], hotel[1], hotel[2] = line["hotel_name"], hotel[1] + nights, hotel[2] + amount

    statuses = [line["status"] for line in rows]
    ranking = sorted(hotels.items(), key=lambda item: (-item[1][2], item[0]))[:5]
    return {
        "summary": {
            "total_reservations": len(rows),
            "confirmed_reservations": statuses.count("CONFIRMED"),
            "cancelled_reservations": statuses.count("CANCELLED"),
            "no_show_reservations": statuses.count("NO_SHOW"),
            "total_room_nights": nights_total,
            "total_amount_brl": money(amount_total),
            "average_nightly_rate_brl": money(amount_total / nights_total) if nights_total else "0.00",
        },
        "by_month": [
            {"month": key, "reservations": count, "room_nights": nights, "total_brl": money(amount)}
            for key, (count, nights, amount) in sorted(months.items())
        ],
        "top_hotels": [
            {"hotel_id": hotel_id, "hotel_name": name, "room_nights": nights, "total_brl": money(amount)}
            for hotel_id, (name, nights, amount) in ranking
        ],
    }


@pytest.fixture(scope="module")
def report(tmp_path_factory) -> dict:
    output_path = tmp_path_factory.mktemp("dataset") / "report.json"
    process = run_cli_args(
        [
            "--input",
            str(DATA / "reservas_hoteis.csv"),
            "--rates",
            str(DATA / "taxas_cambio.csv"),
            "--output",
            str(output_path),
        ]
    )
    assert process.returncode == 0, process.stderr
    return json.loads(output_path.read_text(encoding="utf-8"))


# --- Fatos do dataset (garantem que o oráculo lê o arquivo inteiro) ----------------------------


def test_dataset_shape(rows):
    statuses = [line["status"] for line in rows]

    assert len(rows) == 300
    assert (statuses.count("CONFIRMED"), statuses.count("CANCELLED"), statuses.count("NO_SHOW")) == (235, 31, 34)


# --- Comparação com o oráculo -----------------------------------------------------------------


def test_summary_matches_oracle(report, oracle):
    assert report["summary"] == oracle["summary"]


def test_by_month_matches_oracle(report, oracle):
    assert report["by_month"] == oracle["by_month"]


def test_top_hotels_match_oracle(report, oracle):
    assert report["top_hotels"] == oracle["top_hotels"]


# --- Invariantes internos do relatório --------------------------------------------------------


def test_status_counts_add_up_to_total(report):
    summary = report["summary"]

    assert (
        summary["confirmed_reservations"] + summary["cancelled_reservations"] + summary["no_show_reservations"]
        == summary["total_reservations"]
    )


def test_by_month_adds_up_to_summary(report):
    """Cada reserva faturável cai em exatamente um mês (o do check-in)."""
    by_month, summary = report["by_month"], report["summary"]

    assert sum(item["reservations"] for item in by_month) == summary["confirmed_reservations"]
    assert sum(item["room_nights"] for item in by_month) == summary["total_room_nights"]
    month_total = sum(Decimal(item["total_brl"]) for item in by_month)
    assert abs(month_total - Decimal(summary["total_amount_brl"])) <= Decimal("0.01") * len(by_month)


def test_by_month_starts_in_december_2024(report):
    """Reservas com check-in em 2024-12 que terminam em 2025 ficam no mês do check-in."""
    assert report["by_month"][0]["month"] == "2024-12"


def test_top_hotels_are_five_and_sorted_descending(report):
    totals = [Decimal(item["total_brl"]) for item in report["top_hotels"]]

    assert len(totals) == 5
    assert totals == sorted(totals, reverse=True)


def test_average_is_consistent_with_totals(report):
    summary = report["summary"]
    average = Decimal(summary["total_amount_brl"]) / summary["total_room_nights"]

    assert abs(average - Decimal(summary["average_nightly_rate_brl"])) <= Decimal("0.01")
