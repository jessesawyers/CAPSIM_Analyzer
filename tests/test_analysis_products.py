from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.analysis.products import analyze_products
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import (
    BuyingCriterion,
    CourierReport,
    PerceptualPosition,
    Product,
    ProductionRecord,
    SegmentProductSnapshot,
    SegmentReport,
)
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _report(*, products, segments, production=(), segment_reports=()):
    return CourierReport(
        simulation_id="TEST01",
        round_number=1,
        report_date=date(2027, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        products=list(products),
        production=list(production),
        segment_reports=list(segment_reports),
    )


def _traditional_report():
    criteria = [
        BuyingCriterion(1, "Ideal Position", {"performance": Decimal("5"), "size": Decimal("15")}, Decimal("40")),
        BuyingCriterion(2, "Price", {"minimum": Decimal("20"), "maximum": Decimal("30")}, Decimal("30")),
        BuyingCriterion(3, "Reliability", {"minimum": 14000, "maximum": 19000}, Decimal("20")),
        BuyingCriterion(4, "Age", {"ideal_age_years": Decimal("2")}, Decimal("10")),
    ]
    segment = SegmentReport(
        Segment.TRADITIONAL, 1000, 900, Decimal("50"), Decimal("10"),
        buying_criteria=criteria,
        products=[
            SegmentProductSnapshot(
                "Able", Decimal("12.5"), 90,
                perceptual_position=PerceptualPosition(Decimal("5.5"), Decimal("14.5")),
                list_price=Decimal("28"), mtbf=17500, age_years=Decimal("3"),
                customer_awareness_percent=Decimal("55"),
                customer_accessibility_percent=Decimal("54"),
                customer_survey_score=Decimal("18"),
            )
        ],
    )
    product = Product(
        "Able", Company.ANDREWS, Segment.TRADITIONAL,
        perceptual_position=PerceptualPosition(Decimal("5.5"), Decimal("14.5")),
        age_years=Decimal("3"), mtbf=17500, list_price=Decimal("28"),
        material_cost=Decimal("11"), labor_cost=Decimal("7"),
        contribution_margin_percent=Decimal("35"),
        units_sold=100, inventory_units=25,
    )
    production = ProductionRecord(
        Company.ANDREWS, "Able", Segment.TRADITIONAL, units_sold=100
    )
    return _report(products=[product], segments=[segment], production=[production], segment_reports=[segment])


def test_product_analysis_calculates_position_expectations_and_performance():
    metrics = analyze_products(_traditional_report()).products["Able"]

    assert metrics.performance_difference == Decimal("0.5")
    assert metrics.size_difference == Decimal("-0.5")
    assert metrics.perceptual_distance == Decimal("0.7071067811865476")
    assert metrics.price_difference == Decimal("3")
    assert metrics.price_in_expected_range is True
    assert metrics.mtbf_difference == 1000
    assert metrics.mtbf_in_expected_range is True
    assert metrics.age_difference == Decimal("1")


def test_product_analysis_calculates_performance_and_customer_facts():
    metrics = analyze_products(_traditional_report()).products["Able"]

    assert metrics.units_sold == 100
    assert metrics.inventory_units == 25
    assert metrics.inventory_to_sales_ratio == Decimal("0.25")
    assert metrics.market_share_percent == Decimal("12.5")
    assert metrics.contribution_margin_amount == Decimal("1000")
    assert metrics.contribution_margin_percent == Decimal("35")
    assert metrics.customer_awareness_percent == Decimal("55")
    assert metrics.customer_accessibility_percent == Decimal("54")
    assert metrics.customer_survey_score == Decimal("18")


def test_product_analysis_ranks_each_metric_and_checks_consistency():
    report = _traditional_report()
    second = Product("Baker", Company.BALDWIN, Segment.TRADITIONAL, units_sold=50)
    analysis = analyze_products(
        _report(
            products=[*report.products, second],
            segments=report.segment_reports,
            production=report.production,
            segment_reports=report.segment_reports,
        )
    )

    rankings = analysis.rankings_by_segment[Segment.TRADITIONAL]
    assert rankings["units_sold"] == ("Able", "Baker")
    assert analysis.consistency_checks["Able"].company_consistent is True
    assert analysis.consistency_checks["Able"].segment_consistent is True
    assert analysis.consistency_checks["Able"].units_sold_consistent is False


def test_product_analysis_handles_missing_values_and_zero_sales():
    product = Product("Acre", Company.ANDREWS, Segment.LOW_END, units_sold=0, inventory_units=10)
    metrics = analyze_products(_report(products=[product], segments=[])).products["Acre"]

    assert metrics.performance_difference is None
    assert metrics.perceptual_distance is None
    assert metrics.inventory_to_sales_ratio is None
    assert metrics.market_share_percent is None
    assert metrics.contribution_margin_amount is None
    assert metrics.price_in_expected_range is None


def test_product_analysis_round_0_able_and_aft():
    report = parse_courier_pdf(PDF_PATH)
    analysis = analyze_products(report)

    able = analysis.products["Able"]
    assert able.company is Company.ANDREWS
    assert able.performance_difference == Decimal("0.5")
    assert able.size_difference == Decimal("-0.5")
    assert able.price_difference == Decimal("3.00")
    assert able.inventory_units == 189
    assert able.units_sold == 999
    assert able.market_share_percent == Decimal("13")
    assert able.plant_utilization_percent == Decimal("66")

    aft = analysis.products["Aft"]
    assert aft.segment is Segment.PERFORMANCE
    assert aft.performance_difference == Decimal("0.0")
    assert aft.size_difference == Decimal("-0.5")
    assert aft.price_difference == Decimal("3.00")
    assert aft.mtbf_difference == 500
    assert aft.units_sold == 358
