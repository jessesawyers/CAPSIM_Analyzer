from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.segments import (
    forecast_segment_demand_absolute_change,
    forecast_segment_demand_percentage_growth,
    forecast_segment_demand_with_courier_growth,
)
from capsim_analyzer.forecasting.types import ForecastStatus
from capsim_analyzer.models import CourierReport, SegmentReport
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _report(round_number, *, simulation_id="SIM01", segment_reports=()):
    return CourierReport(
        simulation_id=simulation_id,
        round_number=round_number,
        report_date=date(2026 + round_number, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        segment_reports=list(segment_reports),
    )


def _segment(segment, demand=None, growth=None):
    return SegmentReport(
        segment=segment,
        total_industry_unit_demand=demand,
        actual_industry_unit_sales=demand or 0,
        percent_of_total_industry=Decimal("20"),
        next_year_growth_rate_percent=growth,
    )


def test_courier_growth_forecast_preserves_decimal_precision():
    report = _report(
        0,
        segment_reports=[_segment(Segment.TRADITIONAL, 100, Decimal("12.345"))],
    )

    result = forecast_segment_demand_with_courier_growth(report)[Segment.TRADITIONAL]

    assert result.value == Decimal("112.345")
    assert result.status is ForecastStatus.AVAILABLE
    assert result.method == "courier_next_year_growth"
    assert result.source_rounds == (0,)
    assert result.required_history == 1


def test_courier_growth_reports_missing_inputs():
    report = _report(
        0,
        segment_reports=[_segment(Segment.TRADITIONAL, None, None)],
    )

    result = forecast_segment_demand_with_courier_growth(report)[Segment.TRADITIONAL]

    assert result.value is None
    assert result.status is ForecastStatus.MISSING_INPUT


def test_absolute_change_forecast_uses_latest_ordered_rounds():
    first = _report(0, segment_reports=[_segment(Segment.TRADITIONAL, 100, Decimal("1"))])
    latest = _report(2, segment_reports=[_segment(Segment.TRADITIONAL, 140, Decimal("1"))])

    result = forecast_segment_demand_absolute_change([latest, first])[Segment.TRADITIONAL]

    assert result.value == 180
    assert result.source_rounds == (0, 2)
    assert result.available_history == 2
    assert result.status is ForecastStatus.AVAILABLE


def test_percentage_growth_forecast_uses_latest_growth():
    first = _report(0, segment_reports=[_segment(Segment.TRADITIONAL, 100, Decimal("1"))])
    latest = _report(1, segment_reports=[_segment(Segment.TRADITIONAL, 125, Decimal("1"))])

    result = forecast_segment_demand_percentage_growth([first, latest])[Segment.TRADITIONAL]

    assert result.value == Decimal("156.25")
    assert result.status is ForecastStatus.AVAILABLE


def test_historical_methods_handle_missing_and_zero_values():
    first = _report(0, segment_reports=[_segment(Segment.TRADITIONAL, 0, Decimal("1"))])
    latest = _report(1, segment_reports=[_segment(Segment.TRADITIONAL, 10, Decimal("1"))])

    absolute = forecast_segment_demand_absolute_change([first, latest])[Segment.TRADITIONAL]
    percentage = forecast_segment_demand_percentage_growth([first, latest])[Segment.TRADITIONAL]

    assert absolute.value == 20
    assert percentage.value is None
    assert percentage.status is ForecastStatus.ZERO_DENOMINATOR

    missing = _report(1, segment_reports=[_segment(Segment.TRADITIONAL, None, Decimal("1"))])
    result = forecast_segment_demand_absolute_change([first, missing])[Segment.TRADITIONAL]
    assert result.status is ForecastStatus.MISSING_INPUT


def test_historical_methods_require_two_rounds():
    report = _report(0, segment_reports=[_segment(Segment.TRADITIONAL, 100, Decimal("1"))])

    result = forecast_segment_demand_percentage_growth([report])[Segment.TRADITIONAL]

    assert result.value is None
    assert result.status is ForecastStatus.INSUFFICIENT_HISTORY
    assert result.source_rounds == (0,)
    assert result.available_history == 1


def test_forecasts_are_deterministic_and_do_not_mutate_reports():
    first = _report(0, segment_reports=[_segment(Segment.TRADITIONAL, 100, Decimal("1"))])
    latest = _report(1, segment_reports=[_segment(Segment.TRADITIONAL, 120, Decimal("1"))])
    before = latest.segment_reports

    first_result = forecast_segment_demand_percentage_growth([latest, first])
    second_result = forecast_segment_demand_percentage_growth([latest, first])

    assert first_result == second_result
    assert latest.segment_reports == before


def test_round_0_courier_growth_values_are_consumed():
    report = parse_courier_pdf(PDF_PATH)
    results = forecast_segment_demand_with_courier_growth(report)

    assert results[Segment.TRADITIONAL].value == Decimal("8066.604")
    assert results[Segment.PERFORMANCE].value == Decimal("2294.170")
    assert results[Segment.HIGH_END].source_rounds == (0,)
