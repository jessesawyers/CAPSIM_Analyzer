from __future__ import annotations

from decimal import Decimal

from ..enums import Company, Segment
from ..models import CompanyMarketShare, CourierReport, MarketShareReport
from .types import (
    CompanyMarketShareMetrics,
    MarketShareAnalysis,
    SegmentShareReconciliation,
)


def analyze_market_share(report: CourierReport) -> MarketShareAnalysis:
    """Calculate actual, potential, and comparative market-share facts."""
    market_share = report.market_share
    actual = _by_company(market_share.actual if market_share else ())
    potential = _by_company(market_share.potential if market_share else ())

    company_metrics = {
        company: _company_metrics(
            company,
            actual.get(company),
            potential.get(company),
            report.segments,
        )
        for company in report.companies
    }
    actual_rankings = {
        segment: _rank_segment(segment, actual, report.companies)
        for segment in report.segments
    }
    potential_rankings = {
        segment: _rank_segment(segment, potential, report.companies)
        for segment in report.segments
    }
    return MarketShareAnalysis(
        companies=company_metrics,
        actual_leaders={
            segment: rankings[0] if rankings else None
            for segment, rankings in actual_rankings.items()
        },
        potential_leaders={
            segment: rankings[0] if rankings else None
            for segment, rankings in potential_rankings.items()
        },
        actual_rankings=actual_rankings,
        potential_rankings=potential_rankings,
        reconciliation={
            segment: _reconciliation(
                segment,
                actual,
                potential,
                report.companies,
            )
            for segment in report.segments
        },
        industry_unit_sales=market_share.industry_unit_sales if market_share else {},
        industry_units_demanded=market_share.industry_units_demanded if market_share else {},
    )


def _by_company(
    shares: tuple[CompanyMarketShare, ...] | list[CompanyMarketShare],
) -> dict[Company, CompanyMarketShare]:
    return {share.company: share for share in shares}


def _company_metrics(
    company: Company,
    actual: CompanyMarketShare | None,
    potential: CompanyMarketShare | None,
    segments: list[Segment],
) -> CompanyMarketShareMetrics:
    actual_values = _segment_values(actual, segments)
    potential_values = _segment_values(potential, segments)
    return CompanyMarketShareMetrics(
        company=company,
        actual_by_segment=actual_values,
        potential_by_segment=potential_values,
        potential_minus_actual_by_segment={
            segment: _difference(potential_values[segment], actual_values[segment])
            for segment in segments
        },
        actual_total_percent=_total(actual, actual_values, segments),
        potential_total_percent=_total(potential, potential_values, segments),
    )


def _segment_values(
    share: CompanyMarketShare | None,
    segments: list[Segment],
) -> dict[Segment, Decimal | None]:
    if share is None:
        return {segment: None for segment in segments}
    return {segment: share.segment_percentages.get(segment) for segment in segments}


def _total(
    share: CompanyMarketShare | None,
    values: dict[Segment, Decimal | None],
    segments: list[Segment],
) -> Decimal | None:
    if share is not None and share.total_percent is not None:
        return share.total_percent
    if not segments or any(values[segment] is None for segment in segments):
        return None
    return sum(values[segment] for segment in segments if values[segment] is not None)


def _difference(
    potential: Decimal | None,
    actual: Decimal | None,
) -> Decimal | None:
    return None if potential is None or actual is None else potential - actual


def _rank_segment(
    segment: Segment,
    shares: dict[Company, CompanyMarketShare],
    companies: list[Company],
) -> tuple[Company, ...]:
    available = [
        company
        for company in companies
        if shares.get(company) is not None
        and shares[company].segment_percentages.get(segment) is not None
    ]
    return tuple(
        sorted(
            available,
            key=lambda company: (
                -shares[company].segment_percentages[segment],
                company.value,
            ),
        )
    )


def _reconciliation(
    segment: Segment,
    actual: dict[Company, CompanyMarketShare],
    potential: dict[Company, CompanyMarketShare],
    companies: list[Company],
) -> SegmentShareReconciliation:
    actual_values = _available_segment_values(segment, actual, companies)
    potential_values = _available_segment_values(segment, potential, companies)
    actual_total = _sum_if_complete(actual_values)
    potential_total = _sum_if_complete(potential_values)
    hundred = Decimal("100")
    return SegmentShareReconciliation(
        segment=segment,
        actual_total_percent=actual_total,
        potential_total_percent=potential_total,
        actual_difference_from_100=None if actual_total is None else actual_total - hundred,
        potential_difference_from_100=None if potential_total is None else potential_total - hundred,
        actual_complete=len(actual_values) == len(companies),
        potential_complete=len(potential_values) == len(companies),
    )


def _available_segment_values(
    segment: Segment,
    shares: dict[Company, CompanyMarketShare],
    companies: list[Company],
) -> list[Decimal]:
    return [
        shares[company].segment_percentages[segment]
        for company in companies
        if company in shares and shares[company].segment_percentages.get(segment) is not None
    ]


def _sum_if_complete(values: list[Decimal]) -> Decimal | None:
    return sum(values) if values else None
