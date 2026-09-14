from datetime import date
from decimal import Decimal
from dataclasses import replace
from pathlib import Path

from capsim_analyzer.analysis.production import analyze_production
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.production_rules import (
    evaluate_forecast_inventory_vs_desired,
    evaluate_forecast_sales_vs_capacity,
    evaluate_forecast_sales_vs_current,
    evaluate_inventory_stockout,
    evaluate_required_production_vs_capacity,
    evaluate_utilization_indicators,
)
from capsim_analyzer.decision.types import CapacityPosition, DecisionStatus
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.types import ForecastStatus, ForecastValue
from capsim_analyzer.models import CourierReport, Product, ProductionRecord
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _forecast(value, status=ForecastStatus.AVAILABLE):
    return ForecastValue(value, status, "test", (1,), 1, 1, ("explicit assumption",))


def _context(*, units=100, inventory=20, capacity=120, sales=None, inventory_forecast=None, record=True):
    product = Product("Able", Company.ANDREWS, Segment.TRADITIONAL, units_sold=units, inventory_units=inventory, capacity_next_round=capacity)
    production = [ProductionRecord(Company.ANDREWS, "Able", Segment.TRADITIONAL, units, inventory, capacity, Decimal("75"), Decimal("10"), Decimal("10"))] if record else []
    return DecisionContext(
        report=CourierReport("SIM01", 1, date(2027, 12, 31), list(Company), list(Segment), products=[product], production=production),
        product_sales_forecasts={} if sales is None else {"Able": sales},
        inventory_forecasts={} if inventory_forecast is None else {"Able": inventory_forecast},
    )


def test_forecast_sales_vs_current_and_capacity():
    context = _context(sales=_forecast(110), capacity=120)
    current = evaluate_forecast_sales_vs_current(context, "Able")
    capacity = evaluate_forecast_sales_vs_capacity(context, "Able")

    assert current.status is DecisionStatus.AVAILABLE
    assert "increase" in current.observations[0]
    assert capacity.status is DecisionStatus.AVAILABLE
    assert "headroom" in capacity.observations[0]


def test_forecast_sales_vs_current_recommends_for_increase_and_decrease_but_not_no_change():
    increase = evaluate_forecast_sales_vs_current(
        _context(sales=_forecast(110)),
        "Able",
    )
    decrease = evaluate_forecast_sales_vs_current(
        _context(sales=_forecast(90)),
        "Able",
    )
    no_change = evaluate_forecast_sales_vs_current(
        _context(sales=_forecast(100)),
        "Able",
    )

    assert increase.recommendation is not None
    assert decrease.recommendation is not None
    assert no_change.recommendation is None
    assert no_change.observations


def test_forecast_capacity_exceeds_and_missing_capacity():
    exceeds = evaluate_forecast_sales_vs_capacity(_context(sales=_forecast(130), capacity=120), "Able")
    missing = evaluate_forecast_sales_vs_capacity(_context(sales=_forecast(100), capacity=None, record=False), "Able")

    assert "exceeds" in exceeds.observations[0]
    assert exceeds.recommendation is not None
    assert missing.status is DecisionStatus.MISSING_INPUT


def test_capacity_falls_back_to_production_record_when_analysis_is_missing():
    context = _context(sales=_forecast(110), capacity=120)
    analysis = analyze_production(context.report)
    metrics = replace(analysis.products["Able"], capacity_next_round=None)
    context = replace(
        context,
        production_analysis=replace(analysis, products={"Able": metrics}),
    )

    result = evaluate_forecast_sales_vs_capacity(context, "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[1].value == 120


def test_utilization_falls_back_to_production_record_per_field():
    context = _context()
    analysis = analyze_production(context.report)
    metrics = replace(
        analysis.products["Able"],
        plant_utilization_percent=None,
        overtime=None,
    )
    context = replace(
        context,
        production_analysis=replace(analysis, products={"Able": metrics}),
    )

    result = evaluate_utilization_indicators(context, "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("75")
    assert result.evidence[1].value == Decimal("10")


def test_utilization_preserves_analysis_value_while_falling_back_only_missing_field():
    context = _context()
    analysis = analyze_production(context.report)
    metrics = replace(
        analysis.products["Able"],
        plant_utilization_percent=Decimal("80"),
        overtime=None,
    )
    context = replace(
        context,
        production_analysis=replace(analysis, products={"Able": metrics}),
    )

    result = evaluate_utilization_indicators(context, "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("80")
    assert result.evidence[1].value == Decimal("10")


def test_utilization_preserves_non_none_analysis_values():
    context = _context()
    analysis = analyze_production(context.report)
    metrics = replace(
        analysis.products["Able"],
        plant_utilization_percent=Decimal("80"),
        overtime=Decimal("20"),
    )
    context = replace(
        context,
        production_analysis=replace(analysis, products={"Able": metrics}),
    )

    result = evaluate_utilization_indicators(context, "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("80")
    assert result.evidence[1].value == Decimal("20")


def test_inventory_vs_desired_uses_supplied_desired_value():
    result = evaluate_forecast_inventory_vs_desired(
        _context(inventory_forecast=_forecast(60)),
        "Able",
        desired_inventory=Decimal("50"),
    )

    assert result.status is DecisionStatus.AVAILABLE
    assert "increase" in result.observations[0]
    assert result.assumptions == ("explicit assumption",)


def test_inventory_vs_desired_requires_existing_forecast_and_assumption():
    context = _context()
    assert evaluate_forecast_inventory_vs_desired(context, "Able", Decimal("50")).status is DecisionStatus.MISSING_INPUT
    assert evaluate_forecast_inventory_vs_desired(_context(inventory_forecast=_forecast(50)), "Able").status is DecisionStatus.MISSING_INPUT


def test_required_production_vs_capacity_uses_existing_forecast():
    required = _forecast(120)
    result = evaluate_required_production_vs_capacity(_context(capacity=120), "Able", required)

    assert result.status is DecisionStatus.AVAILABLE
    assert "exact" in result.observations[0]


def test_utilization_and_overtime_are_reported_without_interpretation():
    result = evaluate_utilization_indicators(_context(), "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("75")
    assert result.evidence[1].value == Decimal("10")


def test_stockout_trigger_and_nonstockout():
    stockout = evaluate_inventory_stockout(_context(inventory=0), "Able")
    normal = evaluate_inventory_stockout(_context(inventory=20), "Able")

    assert stockout.status is DecisionStatus.AVAILABLE
    assert stockout.recommendation is not None
    assert "stockout" in stockout.observations[0]
    assert normal.recommendation is None


def test_forecast_status_is_propagated_and_inputs_are_not_mutated():
    forecast = _forecast(None, ForecastStatus.INSUFFICIENT_HISTORY)
    context = _context(sales=forecast)

    result = evaluate_forecast_sales_vs_current(context, "Able")

    assert result.status is DecisionStatus.INSUFFICIENT_DATA
    assert context.report.products[0].units_sold == 100


def test_round_0_integration_uses_reported_capacity_inventory_and_overtime():
    report = parse_courier_pdf(PDF_PATH)
    able = report.product_by_name("Able")
    context = DecisionContext(
        report=report,
        product_sales_forecasts={"Able": _forecast(Decimal("1048.65852"),)},
    )

    result = evaluate_forecast_sales_vs_capacity(context, "Able")
    utilization = evaluate_utilization_indicators(context, "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert "headroom" in result.observations[0]
    assert utilization.evidence[1].value == Decimal("0")
