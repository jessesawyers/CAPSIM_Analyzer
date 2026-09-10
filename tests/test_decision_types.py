from datetime import date
from decimal import Decimal

import pytest

from capsim_analyzer.analysis.types import SegmentAnalysis
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.types import (
    DecisionReport,
    DecisionStatus,
    Evidence,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RuleResult,
)
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.types import ForecastStatus, ForecastValue
from capsim_analyzer.models import CourierReport


def _report():
    return CourierReport(
        simulation_id="SIM01",
        round_number=0,
        report_date=date(2026, 12, 31),
        companies=list(Company),
        segments=list(Segment),
    )


def _evidence():
    return Evidence(
        kind="observed",
        metric="inventory_units",
        entity_type="product",
        entity_id="Able",
        value=Decimal("189"),
        unit="units",
        source_rounds=(0,),
        status=DecisionStatus.AVAILABLE,
        explanation="Current inventory from the Courier report.",
    )


def test_decision_enum_values():
    assert DecisionStatus.ASSUMPTION_REQUIRED.value == "assumption_required"
    assert RecommendationCategory.DATA_QUALITY.value == "data_quality"
    assert RecommendationPriority.INFORMATIONAL.value == "informational"


def test_evidence_is_immutable():
    evidence = _evidence()

    with pytest.raises(Exception):
        evidence.metric = "other"


def test_recommendation_construction():
    evidence = _evidence()
    recommendation = Recommendation(
        recommendation_id="inventory-review",
        category=RecommendationCategory.INVENTORY,
        priority=RecommendationPriority.MEDIUM,
        entity_type="product",
        entity_id="Able",
        action="Review inventory coverage.",
        rationale="Current inventory should be compared with the supplied assumption.",
        evidence=(evidence,),
        assumptions=("Coverage is supplied by the caller.",),
        status=DecisionStatus.ASSUMPTION_REQUIRED,
    )

    assert recommendation.evidence == (evidence,)
    assert recommendation.category is RecommendationCategory.INVENTORY


def test_rule_result_and_report_construction():
    evidence = _evidence()
    recommendation = Recommendation(
        recommendation_id="review",
        category=RecommendationCategory.PRODUCT,
        priority=RecommendationPriority.INFORMATIONAL,
        entity_type="product",
        entity_id="Able",
        action="Review product facts.",
        rationale="Example only.",
        evidence=(evidence,),
        assumptions=(),
        status=DecisionStatus.INFORMATIONAL,
    )
    result = RuleResult(
        rule_id="product-position",
        status=DecisionStatus.AVAILABLE,
        entity_type="product",
        entity_id="Able",
        observations=("Position is available.",),
        evidence=(evidence,),
        assumptions=(),
        recommendation=recommendation,
    )
    report = DecisionReport(
        status=DecisionStatus.AVAILABLE,
        observations=(result,),
        recommendations=(recommendation,),
        blocked_rules=(),
        data_quality_issues=(),
    )

    assert report.observations == (result,)
    assert report.recommendations[0].recommendation_id == "review"


def test_decision_context_accepts_optional_analysis_and_forecasts():
    segment_forecast = ForecastValue(
        value=Decimal("100"),
        status=ForecastStatus.AVAILABLE,
        method="test",
        source_rounds=(0,),
        required_history=1,
        available_history=1,
    )
    context = DecisionContext(
        report=_report(),
        segment_analysis=SegmentAnalysis(
            metrics={},
            industry_totals=None,
            rankings_by_demand=(),
            rankings_by_growth=(),
        ),
        segment_demand_forecasts={Segment.TRADITIONAL: segment_forecast},
    )

    assert context.report.round_number == 0
    assert context.market_share_analysis is None
    assert context.segment_demand_forecasts[Segment.TRADITIONAL] == segment_forecast
    assert context.product_sales_forecasts == {}
    assert context.inventory_forecasts == {}


def test_decision_context_defaults_optional_inputs_without_computing_them():
    context = DecisionContext(report=_report())

    assert context.segment_analysis is None
    assert context.history_analysis is None
    assert context.segment_demand_forecasts == {}
