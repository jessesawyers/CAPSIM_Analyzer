from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.analysis.segments import analyze_segments
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import CourierReport, SegmentReport
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "CourierC165051R0TBK0CA.PDF"


def _report(*segment_reports: SegmentReport) -> CourierReport:
    return CourierReport(
        simulation_id="TEST01",
        round_number=1,
        report_date=date(2027, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        segment_reports=list(segment_reports),
    )


def _segment(segment, demand, sales, share, growth):
    return SegmentReport(segment, demand, sales, share, growth)


def test_segment_analysis_calculates_metrics_and_totals():
    analysis = analyze_segments(
        _report(
            _segment(Segment.TRADITIONAL, 100, 90, Decimal("40.0"), Decimal("5.5")),
            _segment(Segment.LOW_END, 200, 150, Decimal("60.0"), Decimal("12.5")),
        )
    )

    traditional = analysis.metrics[Segment.TRADITIONAL]
    assert traditional.industry_unit_demand == 100
    assert traditional.actual_industry_unit_sales == 90
    assert traditional.demand_to_sales_gap == 10
    assert traditional.percent_of_total_industry == Decimal("40.0")
    assert traditional.next_year_growth_rate_percent == Decimal("5.5")
    assert analysis.industry_totals.industry_unit_demand == 300
    assert analysis.industry_totals.actual_industry_unit_sales == 240
    assert analysis.industry_totals.complete is False


def test_segment_analysis_ranks_demand_and_growth():
    analysis = analyze_segments(
        _report(
            _segment(Segment.TRADITIONAL, 100, 90, Decimal("40"), Decimal("20")),
            _segment(Segment.LOW_END, 300, 250, Decimal("60"), Decimal("10")),
            _segment(Segment.SIZE, 200, 190, Decimal("30"), Decimal("30")),
        )
    )

    assert analysis.rankings_by_demand == (
        Segment.LOW_END,
        Segment.SIZE,
        Segment.TRADITIONAL,
    )
    assert analysis.rankings_by_growth == (
        Segment.SIZE,
        Segment.TRADITIONAL,
        Segment.LOW_END,
    )


def test_segment_analysis_preserves_missing_data_and_zero_values():
    analysis = analyze_segments(
        _report(_segment(Segment.TRADITIONAL, 0, 0, Decimal("0"), Decimal("0")))
    )

    missing = analysis.metrics[Segment.LOW_END]
    assert missing.industry_unit_demand is None
    assert missing.actual_industry_unit_sales is None
    assert missing.demand_to_sales_gap is None
    assert missing.next_year_growth_rate_percent is None
    assert analysis.industry_totals.industry_unit_demand == 0
    assert analysis.industry_totals.complete is False
    assert analysis.rankings_by_demand == (Segment.TRADITIONAL,)


def test_segment_analysis_round_0_values_and_rankings():
    report = parse_courier_pdf(PDF_PATH)
    analysis = analyze_segments(report)

    traditional = analysis.metrics[Segment.TRADITIONAL]
    high_end = analysis.metrics[Segment.HIGH_END]
    assert traditional.industry_unit_demand == 7387
    assert traditional.next_year_growth_rate_percent == Decimal("9.2")
    assert high_end.industry_unit_demand == 2554
    assert high_end.next_year_growth_rate_percent == Decimal("16.2")
    assert analysis.rankings_by_demand[0] is Segment.LOW_END
    assert analysis.rankings_by_growth[0] is Segment.PERFORMANCE
