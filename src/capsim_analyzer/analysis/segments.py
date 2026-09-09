from __future__ import annotations

from ..models import CourierReport, SegmentReport
from .types import IndustryTotals, SegmentAnalysis, SegmentMetrics


def analyze_segments(report: CourierReport) -> SegmentAnalysis:
    """Calculate reusable segment facts from an existing CourierReport."""
    reports = {segment_report.segment: segment_report for segment_report in report.segment_reports}
    metrics = {
        segment: _metrics(segment, reports.get(segment))
        for segment in report.segments
    }
    return SegmentAnalysis(
        metrics=metrics,
        industry_totals=IndustryTotals(
            industry_unit_demand=_available_total(
                item.industry_unit_demand for item in metrics.values()
            ),
            actual_industry_unit_sales=_available_total(
                item.actual_industry_unit_sales for item in metrics.values()
            ),
            complete=all(
                item.industry_unit_demand is not None
                and item.actual_industry_unit_sales is not None
                for item in metrics.values()
            ),
        ),
        rankings_by_demand=_rank(metrics, "industry_unit_demand"),
        rankings_by_growth=_rank(metrics, "next_year_growth_rate_percent"),
    )


def _metrics(segment, segment_report: SegmentReport | None) -> SegmentMetrics:
    if segment_report is None:
        return SegmentMetrics(segment, None, None, None, None, None)
    demand = segment_report.total_industry_unit_demand
    sales = segment_report.actual_industry_unit_sales
    return SegmentMetrics(
        segment=segment,
        industry_unit_demand=demand,
        actual_industry_unit_sales=sales,
        demand_to_sales_gap=demand - sales,
        percent_of_total_industry=segment_report.percent_of_total_industry,
        next_year_growth_rate_percent=segment_report.next_year_growth_rate_percent,
    )


def _available_total(values):
    values = tuple(values)
    available = tuple(value for value in values if value is not None)
    return sum(available) if available else None


def _rank(metrics, field_name: str) -> tuple:
    available = (
        item for item in metrics.values()
        if getattr(item, field_name) is not None
    )
    return tuple(
        item.segment
        for item in sorted(
            available,
            key=lambda item: (-getattr(item, field_name), item.segment.value),
        )
    )
