from datetime import date
from decimal import Decimal

import pytest

from capsim_analyzer.analysis.history import analyze_history
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import (
    CompanyFinancials,
    CompanyMarketShare,
    CourierReport,
    MarketShareReport,
    Product,
    ProductionRecord,
    SegmentReport,
)


def _report(round_number, *, products=(), production=(), segments=(), market_share=None, financials=()):
    return CourierReport(
        simulation_id="SIM01",
        round_number=round_number,
        report_date=date(2026 + round_number, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        products=list(products),
        production=list(production),
        segment_reports=list(segments),
        market_share=market_share,
        company_financials=list(financials),
    )


def _segment(demand, sales):
    return SegmentReport(
        Segment.TRADITIONAL, demand, sales, Decimal("50"), Decimal("10")
    )


def test_history_compares_adjacent_rounds_with_absolute_and_percent_changes():
    old = _report(0, segments=[_segment(100, 80)])
    new = _report(1, segments=[_segment(150, 100)])

    history = analyze_history([old, new])
    change = history.comparisons[0].segment_changes[Segment.TRADITIONAL].fields

    assert change["industry_unit_demand"].absolute_change == 50
    assert change["industry_unit_demand"].percent_change == Decimal("50")
    assert change["actual_industry_unit_sales"].absolute_change == 20
    assert history.integrity.round_numbers == (0, 1)


def test_history_compares_products_production_market_share_and_finance():
    product_old = Product("Able", Company.ANDREWS, Segment.TRADITIONAL, list_price=Decimal("28"), units_sold=100)
    product_new = Product("Able", Company.ANDREWS, Segment.TRADITIONAL, list_price=Decimal("30"), units_sold=120)
    production_old = ProductionRecord(Company.ANDREWS, "Able", Segment.TRADITIONAL, 100, 10, 200, Decimal("50"))
    production_new = ProductionRecord(Company.ANDREWS, "Able", Segment.TRADITIONAL, 120, 8, 250, Decimal("60"))
    shares_old = MarketShareReport({}, {}, actual=[CompanyMarketShare(Company.ANDREWS, {Segment.TRADITIONAL: Decimal("10")})])
    shares_new = MarketShareReport({}, {}, actual=[CompanyMarketShare(Company.ANDREWS, {Segment.TRADITIONAL: Decimal("15")})])
    finance_old = CompanyFinancials(Company.ANDREWS, income_statement={"net_profit": Decimal("100")})
    finance_new = CompanyFinancials(Company.ANDREWS, income_statement={"net_profit": Decimal("125")})

    comparison = analyze_history([
        _report(0, products=[product_old], production=[production_old], market_share=shares_old, financials=[finance_old]),
        _report(1, products=[product_new], production=[production_new], market_share=shares_new, financials=[finance_new]),
    ]).comparisons[0]

    assert comparison.product_changes["Able"].fields["list_price"].absolute_change == Decimal("2")
    assert comparison.production_changes["Able"].fields["capacity_next_round"].absolute_change == 50
    assert comparison.market_share_changes[(Company.ANDREWS, Segment.TRADITIONAL)].fields["actual_percent"].absolute_change == Decimal("5")
    assert comparison.financial_changes[Company.ANDREWS].fields["income_statement.net_profit"].percent_change == Decimal("25")


def test_history_orders_rounds_and_rejects_duplicates_or_mixed_simulations():
    first = _report(0)
    second = _report(1)
    history = analyze_history([second, first])

    assert history.reports == (first, second)
    assert history.integrity.ordered_by_round is False

    with pytest.raises(ValueError, match="duplicate"):
        analyze_history([first, _report(0)])
    with pytest.raises(ValueError, match="same simulation"):
        analyze_history([first, CourierReport("OTHER", 1, date(2027, 12, 31), list(Company), list(Segment))])


def test_history_preserves_missing_values_and_zero_previous_status():
    old = _report(
        0,
        products=[Product("Able", Company.ANDREWS, Segment.TRADITIONAL, units_sold=0)],
    )
    new = _report(1)
    fields = analyze_history([old, new]).comparisons[0].product_changes["Able"].fields

    assert fields["units_sold"].status == "missing_current"
    assert fields["units_sold"].percent_change is None

    old = _report(0, segments=[_segment(0, 0)])
    new = _report(1, segments=[_segment(10, 5)])
    demand = analyze_history([old, new]).comparisons[0].segment_changes[Segment.TRADITIONAL].fields["industry_unit_demand"]
    assert demand.absolute_change == 10
    assert demand.percent_change is None
    assert demand.status == "zero_previous"


def test_history_supports_partial_financial_coverage_and_real_round_0_report():
    from pathlib import Path
    from capsim_analyzer.parser import parse_courier_pdf

    report = parse_courier_pdf(Path(__file__).parents[1] / "data" / "Week_0.PDF")
    history = analyze_history([report])

    assert history.reports[0] is report
    assert history.comparisons == ()
    assert history.integrity.simulation_id == "C165051"
    assert history.integrity.round_numbers == (0,)
