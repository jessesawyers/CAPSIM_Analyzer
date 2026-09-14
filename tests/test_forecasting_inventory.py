from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.inventory import (
    calculate_required_inventory_change,
    calculate_required_production,
    forecast_ending_inventory,
)
from capsim_analyzer.forecasting.types import ForecastStatus, ForecastValue
from capsim_analyzer.models import CourierReport, Product
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _product(*, inventory=20):
    return Product(
        name="Able",
        company=Company.ANDREWS,
        segment=Segment.TRADITIONAL,
        inventory_units=inventory,
    )


def _sales(value=Decimal("100"), status=ForecastStatus.AVAILABLE, rounds=(1,)):
    return ForecastValue(
        value=value,
        status=status,
        method="test_sales_forecast",
        source_rounds=rounds,
        required_history=1,
        available_history=len(rounds),
    )


def test_forecast_ending_inventory_uses_explicit_coverage():
    result = forecast_ending_inventory(_product(), _sales(Decimal("125")), Decimal("0.4"))

    assert result.value == Decimal("50.0")
    assert result.status is ForecastStatus.AVAILABLE
    assert result.method == "inventory_coverage"
    assert result.source_rounds == (1,)
    assert "explicitly supplied" in result.assumptions[0]


def test_required_inventory_change_uses_current_inventory():
    ending = forecast_ending_inventory(_product(), _sales(Decimal("125")), Decimal("0.4"))

    result = calculate_required_inventory_change(_product(inventory=20), ending)

    assert result.value == Decimal("30.0")
    assert result.status is ForecastStatus.AVAILABLE


def test_required_production_is_mechanical():
    result = calculate_required_production(
        _sales(Decimal("125")),
        desired_ending_inventory=Decimal("40"),
        beginning_inventory=Decimal("20"),
    )

    assert result.value == Decimal("145")
    assert result.status is ForecastStatus.AVAILABLE
    assert "mechanical" in result.assumptions[0]


def test_inventory_forecast_handles_missing_and_invalid_inputs():
    assert forecast_ending_inventory(_product(), _sales(), None).status is ForecastStatus.MISSING_INPUT
    assert forecast_ending_inventory(_product(), None, Decimal("0.5")).status is ForecastStatus.MISSING_INPUT
    assert forecast_ending_inventory(_product(), _sales(), Decimal("0")).status is ForecastStatus.UNSUPPORTED
    assert forecast_ending_inventory(_product(), _sales(), Decimal("-0.5")).status is ForecastStatus.UNSUPPORTED

    ending = forecast_ending_inventory(_product(inventory=None), _sales(), Decimal("0.5"))
    assert calculate_required_inventory_change(_product(inventory=None), ending).status is ForecastStatus.MISSING_INPUT
    assert calculate_required_production(_sales(), None, Decimal("0")).status is ForecastStatus.MISSING_INPUT
    assert calculate_required_production(_sales(), Decimal("10"), None).status is ForecastStatus.MISSING_INPUT


def test_zero_sales_and_zero_beginning_inventory_are_valid():
    ending = forecast_ending_inventory(_product(), _sales(Decimal("0")), Decimal("0.5"))
    assert ending.value == Decimal("0.0")
    assert ending.status is ForecastStatus.AVAILABLE

    production = calculate_required_production(
        _sales(Decimal("0")),
        desired_ending_inventory=Decimal("10"),
        beginning_inventory=Decimal("0"),
    )
    assert production.value == Decimal("10")
    assert production.status is ForecastStatus.AVAILABLE


def test_sales_status_and_history_are_preserved():
    sales = _sales(
        value=None,
        status=ForecastStatus.INSUFFICIENT_HISTORY,
        rounds=(0,),
    )

    ending = forecast_ending_inventory(_product(), sales, Decimal("0.5"))
    production = calculate_required_production(sales, Decimal("10"), Decimal("5"))

    assert ending.status is ForecastStatus.INSUFFICIENT_HISTORY
    assert production.status is ForecastStatus.INSUFFICIENT_HISTORY
    assert ending.source_rounds == (0,)
    assert production.available_history == 1


def test_inventory_forecast_is_deterministic_and_does_not_mutate_product():
    product = _product(inventory=20)
    before = product

    first = forecast_ending_inventory(product, _sales(Decimal("80")), Decimal("0.25"))
    second = forecast_ending_inventory(product, _sales(Decimal("80")), Decimal("0.25"))

    assert first == second
    assert product == before


def test_round_0_inventory_forecast_uses_real_able_data():
    report = parse_courier_pdf(PDF_PATH)
    able = report.product_by_name("Able")
    sales = _sales(Decimal("1048.65852"), rounds=(report.round_number,))

    ending = forecast_ending_inventory(able, sales, Decimal("0.5"))
    change = calculate_required_inventory_change(able, ending)

    assert able.inventory_units == 189
    assert ending.value == Decimal("524.329260")
    assert change.value == Decimal("335.329260")
