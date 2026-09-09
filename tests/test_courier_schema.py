from decimal import Decimal

import pytest

from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import Product
from capsim_analyzer.validation import validate_report
from tests.fixtures.round_0_expected import round_0_report


def test_round_0_segment_statistics():
    report = round_0_report()
    values = {item.segment: item for item in report.segment_reports}

    assert values[Segment.TRADITIONAL].total_industry_unit_demand == 7387
    assert values[Segment.LOW_END].next_year_growth_rate_percent == Decimal("11.7")
    assert values[Segment.HIGH_END].percent_of_total_industry == Decimal("11.2")
    assert values[Segment.PERFORMANCE].total_industry_unit_demand == 1915
    assert values[Segment.SIZE].next_year_growth_rate_percent == Decimal("18.3")


def test_valid_round_0_report_passes_validation():
    validate_report(round_0_report())


def test_product_ownership_and_segments():
    report = round_0_report()
    expected = {
        "Able": Segment.TRADITIONAL, "Acre": Segment.LOW_END,
        "Adam": Segment.HIGH_END, "Aft": Segment.PERFORMANCE,
        "Agape": Segment.SIZE,
    }
    for name, segment in expected.items():
        product = report.product_by_name(name)
        assert product.company is Company.ANDREWS
        assert product.segment is segment


def test_aft_round_0_values():
    aft = round_0_report().product_by_name("Aft")

    assert aft.segment is Segment.PERFORMANCE
    assert aft.perceptual_position.performance == Decimal("9.4")
    assert aft.perceptual_position.size == Decimal("15.5")
    assert aft.mtbf == 25000
    assert aft.list_price == Decimal("33.00")


def test_financial_values_remain_in_statement_categories():
    financials = round_0_report().company_financials[0]

    assert financials.balance_sheet == {
        "cash": Decimal("3434"),
        "accounts_receivable": Decimal("8307"),
        "inventory": Decimal("8617"),
        "total_assets": Decimal("96225"),
        "accounts_payable": Decimal("6583"),
        "long_term_debt": Decimal("41700"),
        "common_stock": Decimal("18360"),
        "retained_earnings": Decimal("29582"),
    }
    assert financials.income_statement["net_profit"] == Decimal("4189")


def test_validation_rejects_duplicate_products():
    report = round_0_report()
    duplicate = Product("Able", Company.ANDREWS, Segment.TRADITIONAL)
    invalid = report.__class__(**{**report.__dict__, "products": report.products + [duplicate]})

    with pytest.raises(ValueError, match="unique"):
        validate_report(invalid)
