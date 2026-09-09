from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.analysis.production import analyze_production
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import (
    CourierReport,
    PerceptualPosition,
    Product,
    ProductionRecord,
    SegmentProductSnapshot,
    SegmentReport,
)
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "CourierC165051R0TBK0CA.PDF"


def _report(products=(), production=(), segment_reports=()):
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


def _record(
    name,
    company=Company.ANDREWS,
    segment=Segment.TRADITIONAL,
    units=80,
    inventory=20,
    capacity=100,
    utilization=Decimal("80"),
    shift=Decimal("10"),
):
    return ProductionRecord(
        company,
        name,
        segment,
        units,
        inventory,
        capacity,
        utilization,
        shift,
    )


def test_production_analysis_calculates_capacity_and_inventory_metrics():
    analysis = analyze_production(_report(production=[_record("Able")]))
    metrics = analysis.products["Able"]

    assert metrics.units_sold == 80
    assert metrics.inventory_units == 20
    assert metrics.capacity_next_round == 100
    assert metrics.capacity_headroom == 20
    assert metrics.plant_utilization_percent == Decimal("80")
    assert metrics.units_sold_as_capacity_percent == Decimal("80")
    assert metrics.second_shift_percent == Decimal("10")
    assert metrics.inventory_to_sales_ratio == Decimal("0.25")


def test_production_analysis_summarizes_by_company_and_segment():
    records = [
        _record("Able", units=80, inventory=20, capacity=100),
        _record("Baker", company=Company.BALDWIN, units=40, inventory=10, capacity=60),
    ]
    analysis = analyze_production(_report(production=records))

    andrews = analysis.company_summaries[Company.ANDREWS]
    traditional = analysis.segment_summaries[Segment.TRADITIONAL]
    assert andrews.units_sold == 80
    assert andrews.inventory_units == 20
    assert andrews.capacity_next_round == 100
    assert andrews.capacity_headroom == 20
    assert traditional.units_sold == 120
    assert traditional.inventory_units == 30
    assert traditional.capacity_next_round == 160
    assert traditional.capacity_headroom == 40


def test_production_analysis_ranks_utilization_deterministically():
    records = [
        _record("Able", utilization=Decimal("80")),
        _record("Baker", utilization=Decimal("80")),
        _record("Acre", utilization=Decimal("50")),
    ]
    analysis = analyze_production(_report(production=records))

    assert analysis.rankings_by_utilization == ("Able", "Baker", "Acre")


def test_production_analysis_handles_zero_and_missing_values():
    zero = _record("Able", units=0, inventory=10, capacity=100)
    missing = _record("Acre", units=None, inventory=None, capacity=None, utilization=None, shift=None)
    analysis = analyze_production(_report(production=[zero, missing]))

    assert analysis.products["Able"].inventory_to_sales_ratio is None
    assert analysis.products["Able"].units_sold_as_capacity_percent == Decimal("0")
    assert analysis.products["Acre"].capacity_headroom is None
    assert analysis.products["Acre"].inventory_to_sales_ratio is None
    assert analysis.company_summaries[Company.ANDREWS].complete_inventory is False


def test_production_analysis_reports_consistency_without_mutating_report():
    product = Product(
        "Able", Company.ANDREWS, Segment.TRADITIONAL, units_sold=80
    )
    snapshot = SegmentProductSnapshot("Able", units_sold=80)
    segment = SegmentReport(
        Segment.TRADITIONAL, 100, 90, Decimal("50"), Decimal("10"),
        products=[snapshot],
    )
    report = _report(
        products=[product],
        production=[_record("Able", units=81)],
        segment_reports=[segment],
    )
    before = report
    analysis = analyze_production(report)

    check = analysis.consistency_checks["Able"]
    assert check.product_found is True
    assert check.segment_snapshot_found is True
    assert check.company_consistent is True
    assert check.segment_consistent is True
    assert check.units_sold_consistent is False
    assert report is before
    assert report.production[0].units_sold == 81


def test_production_analysis_round_0_able_and_aft():
    report = parse_courier_pdf(PDF_PATH)
    analysis = analyze_production(report)

    able = analysis.products["Able"]
    assert able.company is Company.ANDREWS
    assert able.units_sold == 999
    assert able.inventory_units == 189
    assert able.capacity_next_round == 1800
    assert able.capacity_headroom == 801
    assert able.plant_utilization_percent == Decimal("66")
    assert able.units_sold_as_capacity_percent == Decimal("55.5")
    assert able.inventory_to_sales_ratio == Decimal("189") / Decimal("999")

    aft = analysis.products["Aft"]
    assert aft.segment is Segment.PERFORMANCE
    assert aft.units_sold == 358
    assert aft.inventory_units == 78
    assert aft.capacity_next_round == 600
    assert aft.capacity_headroom == 242
    assert aft.plant_utilization_percent == Decimal("73")
    assert aft.second_shift_percent == Decimal("0")
