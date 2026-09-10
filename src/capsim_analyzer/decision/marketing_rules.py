from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from ..models import CourierReport, Product, SegmentProductSnapshot
from .comparisons import compare_actual_to_potential, compare_to_expected
from .context import DecisionContext
from .types import (
    DecisionStatus,
    Evidence,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RuleResult,
)


def evaluate_promotion_awareness(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    snapshot = _snapshot(context.report, product_name)
    budget = _value(context, product_name, snapshot, "promotion_budget")
    awareness = _value(context, product_name, snapshot, "customer_awareness_percent")
    peer_average = _peer_average(context.report, product_name, "customer_awareness_percent")
    status = _available_or_missing(budget, awareness)
    evidence = _evidence(
        product_name,
        (
            ("promotion_budget", budget, "currency"),
            ("customer_awareness_percent", awareness, "percent"),
            ("peer_awareness_average", peer_average, "percent"),
        ),
        context,
        status,
    )
    observations = ()
    recommendation = None
    if status is DecisionStatus.AVAILABLE:
        if peer_average is not None and awareness < peer_average:
            observations = (
                f"{product_name}'s reported awareness is below the available same-segment peer average.",
            )
            recommendation = _review(
                "promotion-awareness-review",
                product_name,
                f"Review {product_name}'s promotion and awareness position against available segment evidence.",
                evidence,
            )
        else:
            observations = (f"{product_name}'s promotion budget and awareness are reported.",)
    return _result("promotion_awareness", product_name, status, evidence, observations, recommendation=recommendation)


def evaluate_sales_budget_accessibility(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    snapshot = _snapshot(context.report, product_name)
    budget = _value(context, product_name, snapshot, "sales_budget")
    accessibility = _value(context, product_name, snapshot, "customer_accessibility_percent")
    peer_average = _peer_average(context.report, product_name, "customer_accessibility_percent")
    status = _available_or_missing(budget, accessibility)
    evidence = _evidence(
        product_name,
        (
            ("sales_budget", budget, "currency"),
            ("customer_accessibility_percent", accessibility, "percent"),
            ("peer_accessibility_average", peer_average, "percent"),
        ),
        context,
        status,
    )
    observations = ()
    recommendation = None
    if status is DecisionStatus.AVAILABLE:
        if peer_average is not None and accessibility < peer_average:
            observations = (
                f"{product_name}'s reported accessibility is below the available same-segment peer average.",
            )
            recommendation = _review(
                "sales-accessibility-review",
                product_name,
                f"Review {product_name}'s sales budget and accessibility position against available segment evidence.",
                evidence,
            )
        else:
            observations = (f"{product_name}'s sales budget and accessibility are reported.",)
    return _result("sales_budget_accessibility", product_name, status, evidence, observations, recommendation=recommendation)


def evaluate_customer_survey_score(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    snapshot = _snapshot(context.report, product_name)
    score = _value(context, product_name, snapshot, "customer_survey_score")
    peer_average = _peer_average(context.report, product_name, "customer_survey_score")
    status = DecisionStatus.AVAILABLE if score is not None else DecisionStatus.MISSING_INPUT
    evidence = _evidence(
        product_name,
        (("customer_survey_score", score, "score"), ("peer_survey_average", peer_average, "score")),
        context,
        status,
    )
    observations = ()
    recommendation = None
    if status is DecisionStatus.AVAILABLE:
        if peer_average is not None and score < peer_average:
            observations = (
                f"{product_name}'s survey score is below the available same-segment peer average.",
            )
            recommendation = _review(
                "customer-survey-review",
                product_name,
                f"Review {product_name}'s customer-perception position using the supplied survey evidence.",
                evidence,
            )
        else:
            observations = (f"{product_name}'s reported survey score is available.",)
    return _result("customer_survey_score", product_name, status, evidence, observations, recommendation=recommendation)


def evaluate_marketing_market_share_gap(
    context: DecisionContext,
    product_name: str,
    *,
    actual: Decimal | None = None,
    potential: Decimal | None = None,
) -> RuleResult:
    if actual is None:
        snapshot = _snapshot(context.report, product_name)
        actual = _value(context, product_name, snapshot, "market_share_percent")
    comparison = compare_actual_to_potential(actual, potential)
    evidence = _evidence(
        product_name,
        (("actual_market_share", actual, "percent"), ("potential_market_share", potential, "percent")),
        context,
        comparison.status,
    )
    observations = ()
    recommendation = None
    if comparison.direction is not None:
        observations = (f"{product_name}'s actual market share is {comparison.direction.value} potential market share.",)
        if comparison.gap != 0:
            recommendation = _review(
                "marketing-market-share-gap",
                product_name,
                f"Investigate {product_name}'s observed actual-versus-potential market-share gap.",
                evidence,
            )
    return _result("marketing_market_share_gap", product_name, comparison.status, evidence, observations, recommendation=recommendation)


def evaluate_marketing_market_share_history(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    history = context.history_analysis
    if history is None or len(history.reports) < 2:
        return _result("marketing_market_share_history", product_name, DecisionStatus.INSUFFICIENT_DATA, ())
    previous = _snapshot_share(history.reports[-2], product_name)
    current = _snapshot_share(history.reports[-1], product_name)
    comparison = compare_to_expected(current, previous)
    evidence = _evidence(
        product_name,
        (("previous_market_share", previous, "percent"), ("current_market_share", current, "percent")),
        context,
        comparison.status,
        round_number=history.reports[-1].round_number,
    )
    observations = () if comparison.direction is None else (
        f"{product_name}'s market share {comparison.direction.value}d across the latest rounds.",
    )
    return _result("marketing_market_share_history", product_name, comparison.status, evidence, observations)


def evaluate_marketing_evidence_completeness(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    snapshot = _snapshot(context.report, product_name)
    values = (
        ("promotion_budget", _value(context, product_name, snapshot, "promotion_budget"), "currency"),
        ("sales_budget", _value(context, product_name, snapshot, "sales_budget"), "currency"),
        ("customer_awareness_percent", _value(context, product_name, snapshot, "customer_awareness_percent"), "percent"),
        ("customer_accessibility_percent", _value(context, product_name, snapshot, "customer_accessibility_percent"), "percent"),
        ("customer_survey_score", _value(context, product_name, snapshot, "customer_survey_score"), "score"),
        ("market_share_percent", _value(context, product_name, snapshot, "market_share_percent"), "percent"),
    )
    missing = tuple(metric for metric, value, _ in values if value is None)
    status = DecisionStatus.AVAILABLE if not missing else DecisionStatus.MISSING_INPUT
    evidence = _evidence(product_name, values, context, status)
    observation = (
        ("Marketing evidence is complete for the supplied product.",)
        if not missing
        else (f"Marketing evidence is missing: {', '.join(missing)}.",)
    )
    return _result("marketing_evidence_completeness", product_name, status, evidence, observation)


def _product(context: DecisionContext, name: str) -> Product | None:
    return next((item for item in context.report.products if item.name == name), None)


def _snapshot(report: CourierReport, product_name: str) -> SegmentProductSnapshot | None:
    for segment_report in report.segment_reports:
        for snapshot in segment_report.products:
            if snapshot.product_name == product_name:
                return snapshot
    return None


def _snapshot_share(report: CourierReport, product_name: str) -> Decimal | None:
    snapshot = _snapshot(report, product_name)
    return None if snapshot is None else snapshot.market_share_percent


def _value(context, product_name, snapshot, field):
    if snapshot is not None:
        return getattr(snapshot, field)
    analysis = context.product_analysis
    metrics = analysis.products.get(product_name) if analysis else None
    return getattr(metrics, _analysis_field(field), None) if metrics else None


def _analysis_field(field: str) -> str:
    return {
        "customer_awareness_percent": "customer_awareness_percent",
        "customer_accessibility_percent": "customer_accessibility_percent",
        "customer_survey_score": "customer_survey_score",
        "market_share_percent": "market_share_percent",
    }.get(field, field)


def _peer_average(report: CourierReport, product_name: str, field: str) -> Decimal | None:
    product = next((item for item in report.products if item.name == product_name), None)
    if product is None:
        return None
    values = [
        getattr(snapshot, field)
        for segment_report in report.segment_reports
        if segment_report.segment is product.segment
        for snapshot in segment_report.products
        if snapshot.product_name != product_name and getattr(snapshot, field) is not None
    ]
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else None


def _available_or_missing(*values) -> DecisionStatus:
    return DecisionStatus.AVAILABLE if all(value is not None for value in values) else DecisionStatus.MISSING_INPUT


def _evidence(
    product_name: str,
    values: Iterable[tuple[str, object, str | None]],
    context: DecisionContext,
    status: DecisionStatus,
    *,
    round_number: int | None = None,
) -> tuple[Evidence, ...]:
    round_value = context.report.round_number if round_number is None else round_number
    return tuple(
        Evidence(
            kind="observed",
            metric=metric,
            entity_type="product",
            entity_id=product_name,
            value=value,
            unit=unit,
            source_rounds=(round_value,),
            status=status,
            explanation=f"{metric} for product {product_name}.",
        )
        for metric, value, unit in values
    )


def _result(rule_id, product_name, status, evidence, observations=(), recommendation=None):
    return RuleResult(rule_id, status, "product", product_name, observations, evidence, (), recommendation)


def _review(recommendation_id, product_name, action, evidence):
    return Recommendation(
        recommendation_id,
        RecommendationCategory.MARKETING,
        RecommendationPriority.INFORMATIONAL,
        "product",
        product_name,
        action,
        "This is a conservative review trigger based on supplied observations, not a guaranteed action.",
        evidence,
        (),
        DecisionStatus.INFORMATIONAL,
    )
