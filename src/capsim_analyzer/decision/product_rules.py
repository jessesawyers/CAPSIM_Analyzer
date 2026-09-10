from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from ..analysis.history import analyze_history
from ..enums import Segment
from ..forecasting.types import ForecastStatus, ForecastValue
from ..models import CourierReport, Product
from .comparisons import (
    compare_actual_to_potential,
    compare_forecast_to_current,
    compare_to_expected,
    compare_value_to_range,
)
from .context import DecisionContext
from .types import (
    DecisionStatus,
    Evidence,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RuleResult,
)


def evaluate_product_positioning(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    segment_report = _segment_report(context, product)
    criteria = _criterion(segment_report, "Ideal Position")
    performance = product.perceptual_position.performance if product else None
    size = product.perceptual_position.size if product else None
    ideal_performance = _criterion_value(criteria, "performance")
    ideal_size = _criterion_value(criteria, "size")
    status = (
        DecisionStatus.MISSING_INPUT
        if product is None or criteria is None
        or performance is None or size is None
        or ideal_performance is None or ideal_size is None
        else DecisionStatus.AVAILABLE
    )
    evidence = _evidence(
        product_name,
        (
            ("segment", product.segment.value if product else None, "segment"),
            ("performance", performance, "position"),
            ("size", size, "position"),
            ("ideal_performance", ideal_performance, "position"),
            ("ideal_size", ideal_size, "position"),
        ),
        context.report.round_number,
        status,
    )
    if status is not DecisionStatus.AVAILABLE:
        return _result("product_positioning", product_name, status, evidence)
    performance_difference = compare_to_expected(performance, ideal_performance)
    size_difference = compare_to_expected(size, ideal_size)
    distance = _distance(performance_difference.difference, size_difference.difference)
    matches = performance_difference.difference == 0 and size_difference.difference == 0
    observation = (
        f"{product_name}'s position matches the reported segment ideal."
        if matches
        else f"Evaluate whether {product_name}'s positioning should be reviewed."
    )
    evidence += _evidence(
        product_name,
        (("perceptual_distance", distance, "position"),),
        context.report.round_number,
        status,
    )
    recommendation = None if matches else _review(
        "product-positioning-review",
        RecommendationCategory.PRODUCT,
        product_name,
        f"Evaluate whether {product_name}'s positioning should be reviewed.",
        evidence,
    )
    return _result(
        "product_positioning",
        product_name,
        status,
        evidence,
        observations=(observation,),
        recommendation=recommendation,
    )


def evaluate_product_price(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    criterion = _criterion(_segment_report(context, product), "Price")
    minimum, maximum = _range(criterion)
    comparison = compare_value_to_range(
        product.list_price if product else None,
        minimum,
        maximum,
    )
    evidence = _evidence(
        product_name,
        (
            ("price", product.list_price if product else None, "currency"),
            ("price_minimum", minimum, "currency"),
            ("price_maximum", maximum, "currency"),
        ),
        context.report.round_number,
        comparison.status,
    )
    observation = None if comparison.position is None else (
        f"{product_name}'s price is {comparison.position.value} the reported segment range."
    )
    recommendation = None
    if comparison.position is not None and comparison.position.value != "within":
        recommendation = _review(
            "product-price-review",
            RecommendationCategory.PRODUCT,
            product_name,
            f"Review {product_name}'s price position relative to the reported segment expectation.",
            evidence,
        )
    return _result(
        "product_price",
        product_name,
        comparison.status,
        evidence,
        observations=() if observation is None else (observation,),
        recommendation=recommendation,
    )


def evaluate_product_mtbf(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    criterion = _criterion(_segment_report(context, product), "Reliability")
    minimum, maximum = _range(criterion)
    comparison = compare_value_to_range(product.mtbf if product else None, minimum, maximum)
    evidence = _evidence(
        product_name,
        (
            ("mtbf", product.mtbf if product else None, "hours"),
            ("mtbf_minimum", minimum, "hours"),
            ("mtbf_maximum", maximum, "hours"),
        ),
        context.report.round_number,
        comparison.status,
    )
    observation = None if comparison.position is None else (
        f"{product_name}'s MTBF is {comparison.position.value} the reported segment range."
    )
    return _result(
        "product_mtbf",
        product_name,
        comparison.status,
        evidence,
        observations=() if observation is None else (observation,),
        recommendation=None,
    )


def evaluate_product_age(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    criterion = _criterion(_segment_report(context, product), "Age")
    expected = _criterion_value(criterion, "ideal_age_years")
    comparison = compare_to_expected(product.age_years if product else None, expected)
    evidence = _evidence(
        product_name,
        (
            ("age", product.age_years if product else None, "years"),
            ("ideal_age", expected, "years"),
        ),
        context.report.round_number,
        comparison.status,
    )
    observation = None if comparison.direction is None else (
        f"{product_name}'s age is {comparison.direction.value} the reported segment ideal."
    )
    recommendation = None
    if comparison.direction is not None and comparison.direction.value != "no_change":
        recommendation = _review(
            "product-age-review",
            RecommendationCategory.PRODUCT,
            product_name,
            f"Evaluate whether {product_name}'s age and positioning should be reviewed.",
            evidence,
        )
    return _result(
        "product_age",
        product_name,
        comparison.status,
        evidence,
        observations=() if observation is None else (observation,),
        recommendation=recommendation,
    )


def evaluate_product_market_share_gap(
    context: DecisionContext,
    product_name: str,
    *,
    actual: Decimal | None = None,
    potential: Decimal | None = None,
) -> RuleResult:
    product = _product(context, product_name)
    if actual is None:
        actual = _product_market_share(context, product)
    comparison = compare_actual_to_potential(actual, potential)
    evidence = _evidence(
        product_name,
        (
            ("actual_market_share", actual, "percent"),
            ("potential_market_share", potential, "percent"),
        ),
        context.report.round_number,
        comparison.status,
    )
    observation = None if comparison.direction is None else (
        f"{product_name}'s actual market share is "
        f"{comparison.direction.value} potential market share."
    )
    recommendation = None
    if comparison.status is DecisionStatus.AVAILABLE and comparison.gap != 0:
        recommendation = _review(
            "product-market-share-gap",
            RecommendationCategory.MARKETING,
            product_name,
            f"Investigate {product_name}'s observed actual-versus-potential market-share gap.",
            evidence,
        )
    return _result(
        "product_market_share_gap",
        product_name,
        comparison.status,
        evidence,
        observations=() if observation is None else (observation,),
        recommendation=recommendation,
    )


def evaluate_product_market_share_history(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    history = context.history_analysis
    if history is None:
        return _result(
            "product_market_share_history",
            product_name,
            DecisionStatus.INSUFFICIENT_DATA,
            (),
        )
    reports = history.reports
    if len(reports) < 2:
        return _result(
            "product_market_share_history",
            product_name,
            DecisionStatus.INSUFFICIENT_DATA,
            (),
        )
    previous = _snapshot_share(reports[-2], product_name)
    current = _snapshot_share(reports[-1], product_name)
    comparison = compare_to_expected(current, previous)
    evidence = _evidence(
        product_name,
        (
            ("previous_market_share", previous, "percent"),
            ("current_market_share", current, "percent"),
        ),
        reports[-1].round_number,
        comparison.status,
    )
    observation = None if comparison.direction is None else (
        f"{product_name}'s market share {comparison.direction.value}d across the latest rounds."
    )
    return _result(
        "product_market_share_history",
        product_name,
        comparison.status,
        evidence,
        observations=() if observation is None else (observation,),
    )


def evaluate_product_sales_forecast(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    forecast = context.product_sales_forecasts.get(product_name)
    product = _product(context, product_name)
    current = product.units_sold if product else None
    if forecast is None:
        return _result(
            "product_sales_forecast",
            product_name,
            DecisionStatus.MISSING_INPUT,
            _evidence(
                product_name,
                (("forecast_sales", None, "units"), ("current_sales", current, "units")),
                context.report.round_number,
                DecisionStatus.MISSING_INPUT,
            ),
        )
    comparison = compare_forecast_to_current(forecast.value, current)
    status = _forecast_status(forecast.status) if forecast.status is not ForecastStatus.AVAILABLE else comparison.status
    evidence = _evidence(
        product_name,
        (
            ("forecast_sales", forecast.value, "units"),
            ("current_sales", current, "units"),
            ("forecast_method", forecast.method, None),
            ("forecast_assumptions", forecast.assumptions, None),
        ),
        context.report.round_number,
        status,
        source_rounds=forecast.source_rounds,
    )
    observation = None if comparison.direction is None else (
        f"{product_name}'s forecast sales indicate a {comparison.direction.value}."
    )
    recommendation = None
    if status is DecisionStatus.AVAILABLE and comparison.direction is not None and comparison.direction.value != "no_change":
        recommendation = _review(
            "product-sales-forecast-monitor",
            RecommendationCategory.PRODUCT,
            product_name,
            f"Monitor {product_name}'s sales direction using the supplied forecast.",
            evidence,
        )
    return _result(
        "product_sales_forecast",
        product_name,
        status,
        evidence,
        observations=() if observation is None else (observation,),
        assumptions=forecast.assumptions,
        recommendation=recommendation,
    )


def _product(context: DecisionContext, name: str) -> Product | None:
    return next((item for item in context.report.products if item.name == name), None)


def _segment_report(context: DecisionContext, product: Product | None):
    if product is None:
        return None
    return next(
        (item for item in context.report.segment_reports if item.segment is product.segment),
        None,
    )


def _criterion(segment_report, name: str):
    if segment_report is None:
        return None
    return next(
        (item for item in segment_report.buying_criteria if item.criterion == name),
        None,
    )


def _criterion_value(criterion, key: str):
    if criterion is None:
        return None
    return criterion.expectations.get(key)


def _range(criterion):
    if criterion is None:
        return None, None
    return criterion.expectations.get("minimum"), criterion.expectations.get("maximum")


def _product_market_share(context: DecisionContext, product: Product | None):
    if product is None:
        return None
    analysis = context.product_analysis
    if analysis is not None and product.name in analysis.products:
        market_share = analysis.products[product.name].market_share_percent
        if market_share is not None:
            return market_share
    for segment_report in context.report.segment_reports:
        if segment_report.segment is product.segment:
            snapshot = next(
                (item for item in segment_report.products if item.product_name == product.name),
                None,
            )
            return snapshot.market_share_percent if snapshot else None
    return None


def _snapshot_share(report: CourierReport, product_name: str) -> Decimal | None:
    for segment_report in report.segment_reports:
        for snapshot in segment_report.products:
            if snapshot.product_name == product_name:
                return snapshot.market_share_percent
    return None


def _distance(first, second):
    if first is None or second is None:
        return None
    return (first * first + second * second).sqrt()


def _forecast_status(status: ForecastStatus) -> DecisionStatus:
    if status is ForecastStatus.INSUFFICIENT_HISTORY:
        return DecisionStatus.INSUFFICIENT_DATA
    if status is ForecastStatus.MISSING_INPUT:
        return DecisionStatus.MISSING_INPUT
    if status is ForecastStatus.ZERO_DENOMINATOR:
        return DecisionStatus.ZERO_DENOMINATOR
    if status is ForecastStatus.UNSUPPORTED:
        return DecisionStatus.UNSUPPORTED
    return DecisionStatus.AVAILABLE


def _evidence(
    product_name: str,
    values: Iterable[tuple[str, object, str | None]],
    round_number: int,
    status: DecisionStatus,
    *,
    source_rounds: tuple[int, ...] | None = None,
) -> tuple[Evidence, ...]:
    rounds = (round_number,) if source_rounds is None else source_rounds
    return tuple(
        Evidence(
            kind="observed",
            metric=metric,
            entity_type="product",
            entity_id=product_name,
            value=value,
            unit=unit,
            source_rounds=rounds,
            status=status,
            explanation=f"{metric} for product {product_name}.",
        )
        for metric, value, unit in values
    )


def _result(
    rule_id: str,
    product_name: str,
    status: DecisionStatus,
    evidence: tuple[Evidence, ...],
    *,
    observations: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    recommendation: Recommendation | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        status=status,
        entity_type="product",
        entity_id=product_name,
        observations=observations,
        evidence=evidence,
        assumptions=assumptions,
        recommendation=recommendation,
    )


def _review(
    recommendation_id: str,
    category: RecommendationCategory,
    product_name: str,
    action: str,
    evidence: tuple[Evidence, ...],
) -> Recommendation:
    return Recommendation(
        recommendation_id=recommendation_id,
        category=category,
        priority=RecommendationPriority.INFORMATIONAL,
        entity_type="product",
        entity_id=product_name,
        action=action,
        rationale="This is a review trigger based on supplied observations, not a guaranteed action.",
        evidence=evidence,
        assumptions=(),
        status=DecisionStatus.INFORMATIONAL,
    )
