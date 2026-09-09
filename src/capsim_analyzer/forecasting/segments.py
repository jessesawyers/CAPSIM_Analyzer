from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from ..analysis.history import analyze_history
from ..enums import Segment
from ..models import CourierReport, SegmentReport
from .types import ForecastStatus, ForecastValue


COURIER_GROWTH_METHOD = "courier_next_year_growth"
ABSOLUTE_CHANGE_METHOD = "historical_absolute_change"
PERCENTAGE_GROWTH_METHOD = "historical_percentage_growth"
NO_ROUNDING_ASSUMPTION = "forecast demand remains Decimal and is not rounded"


def forecast_segment_demand_with_courier_growth(
    report: CourierReport,
) -> Mapping[Segment, ForecastValue[Decimal]]:
    """Forecast each segment using its Courier-provided next-year growth rate."""
    return {
        segment: _courier_growth_value(report, segment)
        for segment in _report_segments(report)
    }


def forecast_segment_demand_absolute_change(
    reports: Iterable[CourierReport],
) -> Mapping[Segment, ForecastValue[int]]:
    """Extrapolate each segment's latest demand by its latest absolute change."""
    history = analyze_history(reports)
    if not history.reports:
        return {}

    current = history.reports[-1]
    segments = _report_segments(current)
    if len(history.reports) < 2:
        return {
            segment: _unavailable_history(
                ABSOLUTE_CHANGE_METHOD,
                history,
                value_type="int",
            )
            for segment in segments
        }

    previous = history.reports[-2]
    return {
        segment: _absolute_change_value(previous, current, segment, history)
        for segment in segments
    }


def forecast_segment_demand_percentage_growth(
    reports: Iterable[CourierReport],
) -> Mapping[Segment, ForecastValue[Decimal]]:
    """Extrapolate each segment's latest demand by its latest percentage growth."""
    history = analyze_history(reports)
    if not history.reports:
        return {}

    current = history.reports[-1]
    segments = _report_segments(current)
    if len(history.reports) < 2:
        return {
            segment: _unavailable_history(
                PERCENTAGE_GROWTH_METHOD,
                history,
                value_type="decimal",
            )
            for segment in segments
        }

    previous = history.reports[-2]
    return {
        segment: _percentage_growth_value(previous, current, segment, history)
        for segment in segments
    }


def _courier_growth_value(
    report: CourierReport,
    segment: Segment,
) -> ForecastValue[Decimal]:
    segment_report = _segment_report(report, segment)
    source_rounds = (report.round_number,)
    common = {
        "method": COURIER_GROWTH_METHOD,
        "source_rounds": source_rounds,
        "required_history": 1,
        "available_history": 1,
        "assumptions": (NO_ROUNDING_ASSUMPTION,),
    }
    if segment_report is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if (
        segment_report.total_industry_unit_demand is None
        or segment_report.next_year_growth_rate_percent is None
    ):
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)

    demand = Decimal(segment_report.total_industry_unit_demand)
    growth = segment_report.next_year_growth_rate_percent / Decimal("100")
    return ForecastValue(
        demand * (Decimal("1") + growth),
        ForecastStatus.AVAILABLE,
        **common,
    )


def _absolute_change_value(
    previous: CourierReport,
    current: CourierReport,
    segment: Segment,
    history,
) -> ForecastValue[int]:
    previous_demand = _demand(previous, segment)
    current_demand = _demand(current, segment)
    common = _historical_common(ABSOLUTE_CHANGE_METHOD, history)
    if previous_demand is None or current_demand is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    change = current_demand - previous_demand
    return ForecastValue(
        current_demand + change,
        ForecastStatus.AVAILABLE,
        **common,
    )


def _percentage_growth_value(
    previous: CourierReport,
    current: CourierReport,
    segment: Segment,
    history,
) -> ForecastValue[Decimal]:
    previous_demand = _demand(previous, segment)
    current_demand = _demand(current, segment)
    common = _historical_common(PERCENTAGE_GROWTH_METHOD, history)
    if previous_demand is None or current_demand is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if previous_demand == 0:
        return ForecastValue(None, ForecastStatus.ZERO_DENOMINATOR, **common)

    previous_decimal = Decimal(previous_demand)
    current_decimal = Decimal(current_demand)
    growth = (current_decimal - previous_decimal) / previous_decimal
    return ForecastValue(
        current_decimal * (Decimal("1") + growth),
        ForecastStatus.AVAILABLE,
        **common,
    )


def _historical_common(method: str, history) -> dict:
    return {
        "method": method,
        "source_rounds": (
            history.reports[-2].round_number,
            history.reports[-1].round_number,
        ),
        "required_history": 2,
        "available_history": len(history.reports),
        "assumptions": (NO_ROUNDING_ASSUMPTION,),
    }


def _unavailable_history(method: str, history, *, value_type: str):
    return ForecastValue(
        value=None,
        status=ForecastStatus.INSUFFICIENT_HISTORY,
        method=method,
        source_rounds=tuple(report.round_number for report in history.reports),
        required_history=2,
        available_history=len(history.reports),
        assumptions=(NO_ROUNDING_ASSUMPTION, f"forecast value type: {value_type}"),
    )


def _report_segments(report: CourierReport) -> tuple[Segment, ...]:
    segments = list(report.segments)
    for segment_report in report.segment_reports:
        if segment_report.segment not in segments:
            segments.append(segment_report.segment)
    return tuple(segments)


def _segment_report(
    report: CourierReport,
    segment: Segment,
) -> SegmentReport | None:
    return next(
        (item for item in report.segment_reports if item.segment is segment),
        None,
    )


def _demand(report: CourierReport, segment: Segment) -> int | None:
    segment_report = _segment_report(report, segment)
    return (
        segment_report.total_industry_unit_demand
        if segment_report is not None
        else None
    )
