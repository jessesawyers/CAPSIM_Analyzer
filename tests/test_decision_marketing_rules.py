from datetime import date
from decimal import Decimal

from capsim_analyzer.analysis.history import analyze_history
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.marketing_rules import (
    evaluate_customer_survey_score,
    evaluate_marketing_evidence_completeness,
    evaluate_marketing_market_share_gap,
    evaluate_marketing_market_share_history,
    evaluate_promotion_awareness,
    evaluate_sales_budget_accessibility,
)
from capsim_analyzer.decision.types import DecisionStatus
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import (
    CourierReport,
    Product,
    SegmentProductSnapshot,
    SegmentReport,
)
from capsim_analyzer.parser import parse_courier_pdf
from pathlib import Path


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _context(*, share=Decimal("10"), awareness=Decimal("70"), accessibility=Decimal("60"), score=Decimal("30"), promotion=Decimal("100"), sales=Decimal("100"), peer=True, round_number=0):
    snapshots = [SegmentProductSnapshot("Able", share, promotion_budget=promotion, customer_awareness_percent=awareness, sales_budget=sales, customer_accessibility_percent=accessibility, customer_survey_score=score)]
    if peer:
        snapshots.append(SegmentProductSnapshot("Baker", Decimal("8"), customer_awareness_percent=Decimal("80"), customer_accessibility_percent=Decimal("70"), customer_survey_score=Decimal("40")))
    report = CourierReport(
        "SIM01", round_number, date(2026 + round_number, 12, 31), list(Company), list(Segment),
        products=[Product("Able", Company.ANDREWS, Segment.TRADITIONAL)],
        segment_reports=[SegmentReport(Segment.TRADITIONAL, 100, 100, Decimal("50"), Decimal("10"), products=snapshots)],
    )
    return DecisionContext(report=report)


def test_budget_awareness_and_accessibility_use_peer_evidence_conservatively():
    context = _context()
    awareness = evaluate_promotion_awareness(context, "Able")
    accessibility = evaluate_sales_budget_accessibility(context, "Able")
    assert awareness.status is DecisionStatus.AVAILABLE
    assert awareness.recommendation is not None
    assert accessibility.recommendation is not None
    assert "specific result" not in awareness.recommendation.action


def test_survey_score_flags_below_peer_average_and_missing_score():
    result = evaluate_customer_survey_score(_context(), "Able")
    missing = evaluate_customer_survey_score(_context(score=None), "Able")
    assert result.status is DecisionStatus.AVAILABLE
    assert result.recommendation is not None
    assert missing.status is DecisionStatus.MISSING_INPUT


def test_market_share_gap_and_history():
    gap = evaluate_marketing_market_share_gap(_context(), "Able", actual=Decimal("10"), potential=Decimal("15"))
    first = _context(share=Decimal("10"))
    second = _context(share=Decimal("12"), round_number=1)
    history = DecisionContext(report=second.report, history_analysis=analyze_history([first.report, second.report]))
    trend = evaluate_marketing_market_share_history(history, "Able")
    assert gap.status is DecisionStatus.AVAILABLE
    assert gap.recommendation is not None
    assert trend.status is DecisionStatus.AVAILABLE
    assert "increased" in trend.observations[0]


def test_marketing_evidence_completeness_handles_missing_values():
    complete = evaluate_marketing_evidence_completeness(_context(), "Able")
    incomplete = evaluate_marketing_evidence_completeness(_context(score=None), "Able")
    assert complete.status is DecisionStatus.AVAILABLE
    assert incomplete.status is DecisionStatus.MISSING_INPUT
    assert "customer_survey_score" in incomplete.observations[0]


def test_round_0_integration_uses_reported_marketing_snapshot():
    report = parse_courier_pdf(PDF_PATH)
    context = DecisionContext(report=report)
    result = evaluate_marketing_evidence_completeness(context, "Able")
    assert result.entity_id == "Able"
    assert result.evidence
