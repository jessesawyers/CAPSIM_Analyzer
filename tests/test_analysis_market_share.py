from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.analysis.market_share import analyze_market_share
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import CompanyMarketShare, CourierReport, MarketShareReport
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _report(market_share: MarketShareReport | None) -> CourierReport:
    return CourierReport(
        simulation_id="TEST01",
        round_number=1,
        report_date=date(2027, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        market_share=market_share,
    )


def _share(company, values, total=None):
    return CompanyMarketShare(company, values, total)


def test_market_share_analysis_reads_actual_and_potential_shares():
    actual = _share(
        Company.ANDREWS,
        {Segment.TRADITIONAL: Decimal("20"), Segment.LOW_END: Decimal("10")},
        Decimal("30"),
    )
    potential = _share(
        Company.ANDREWS,
        {Segment.TRADITIONAL: Decimal("25"), Segment.LOW_END: Decimal("15")},
        Decimal("40"),
    )
    analysis = analyze_market_share(
        _report(
            MarketShareReport(
                industry_unit_sales={},
                industry_units_demanded={},
                actual=[actual],
                potential=[potential],
            )
        )
    )

    andrews = analysis.companies[Company.ANDREWS]
    assert andrews.actual_by_segment[Segment.TRADITIONAL] == Decimal("20")
    assert andrews.potential_by_segment[Segment.TRADITIONAL] == Decimal("25")
    assert andrews.potential_minus_actual_by_segment[Segment.TRADITIONAL] == Decimal("5")
    assert andrews.actual_total_percent == Decimal("30")
    assert andrews.potential_total_percent == Decimal("40")


def test_market_share_analysis_ranks_and_selects_deterministic_leaders():
    shares = [
        _share(Company.ANDREWS, {Segment.TRADITIONAL: Decimal("20")}),
        _share(Company.BALDWIN, {Segment.TRADITIONAL: Decimal("30")}),
        _share(Company.CHESTER, {Segment.TRADITIONAL: Decimal("30")}),
    ]
    analysis = analyze_market_share(
        _report(MarketShareReport({}, {}, actual=shares, potential=shares))
    )

    assert analysis.actual_rankings[Segment.TRADITIONAL][:3] == (
        Company.BALDWIN,
        Company.CHESTER,
        Company.ANDREWS,
    )
    assert analysis.actual_leaders[Segment.TRADITIONAL] is Company.BALDWIN
    assert analysis.potential_leaders[Segment.TRADITIONAL] is Company.BALDWIN


def test_market_share_analysis_reconciles_available_segment_shares():
    shares = [
        _share(company, {Segment.TRADITIONAL: Decimal("50")})
        for company in (Company.ANDREWS, Company.BALDWIN)
    ]
    analysis = analyze_market_share(_report(MarketShareReport({}, {}, actual=shares)))
    reconciliation = analysis.reconciliation[Segment.TRADITIONAL]

    assert reconciliation.actual_total_percent == Decimal("100")
    assert reconciliation.actual_difference_from_100 == Decimal("0")
    assert reconciliation.actual_complete is False
    assert reconciliation.potential_total_percent is None


def test_market_share_analysis_preserves_missing_data():
    analysis = analyze_market_share(_report(None))

    andrews = analysis.companies[Company.ANDREWS]
    assert andrews.actual_by_segment[Segment.TRADITIONAL] is None
    assert andrews.potential_by_segment[Segment.TRADITIONAL] is None
    assert andrews.potential_minus_actual_by_segment[Segment.TRADITIONAL] is None
    assert andrews.actual_total_percent is None
    assert analysis.actual_leaders[Segment.TRADITIONAL] is None
    assert analysis.actual_rankings[Segment.TRADITIONAL] == ()


def test_market_share_analysis_round_0_values():
    report = parse_courier_pdf(PDF_PATH)
    analysis = analyze_market_share(report)

    andrews = analysis.companies[Company.ANDREWS]
    assert andrews.actual_by_segment[Segment.TRADITIONAL] == Decimal("16.7")
    assert andrews.potential_by_segment[Segment.TRADITIONAL] == Decimal("16.7")
    assert andrews.potential_minus_actual_by_segment[Segment.TRADITIONAL] == Decimal("0.0")
    assert andrews.actual_total_percent == Decimal("16.7")
    assert analysis.actual_leaders[Segment.SIZE] is Company.ANDREWS
    assert report.market_share is not None
    assert analysis.industry_unit_sales[Segment.TRADITIONAL] == 7387
