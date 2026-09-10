from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from ..forecasting.types import ForecastStatus, ForecastValue
from ..models import Product, ProductionRecord
from .comparisons import compare_forecast_to_capacity, compare_forecast_to_current
from .context import DecisionContext
from .types import (
    CapacityPosition,
    DecisionStatus,
    Evidence,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RuleResult,
)


def evaluate_forecast_sales_vs_current(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    forecast = context.product_sales_forecasts.get(product_name)
    current = product.units_sold if product else None
    if forecast is None:
        return _result(
            "forecast_sales_vs_current",
            product_name,
            DecisionStatus.MISSING_INPUT,
            _evidence(product_name, (("forecast_sales", None, "units"), ("current_sales", current, "units")), context),
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
        context,
        status=status,
        source_rounds=forecast.source_rounds,
    )
    observation = () if comparison.direction is None else (
        f"{product_name}'s forecast sales indicate a {comparison.direction.value} versus current sales.",
    )
    recommendation = _review(
        "forecast-sales-review",
        RecommendationCategory.PRODUCTION,
        product_name,
        f"Review {product_name}'s production planning against the supplied sales forecast.",
        evidence,
    ) if (
        status is DecisionStatus.AVAILABLE
        and comparison.direction is not None
        and comparison.direction.value != "no_change"
    ) else None
    return _result("forecast_sales_vs_current", product_name, status, evidence, observation, forecast.assumptions, recommendation)


def evaluate_forecast_sales_vs_capacity(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    forecast = context.product_sales_forecasts.get(product_name)
    capacity = _capacity(context, product_name, product)
    if forecast is None:
        status = DecisionStatus.MISSING_INPUT
        comparison = None
    else:
        comparison = compare_forecast_to_capacity(forecast.value, capacity)
        status = _forecast_status(forecast.status) if forecast.status is not ForecastStatus.AVAILABLE else comparison.status
    evidence = _evidence(
        product_name,
        (
            ("forecast_sales", None if forecast is None else forecast.value, "units"),
            ("capacity_next_round", capacity, "units"),
        ),
        context,
        status=status,
        source_rounds=() if forecast is None else forecast.source_rounds,
    )
    observation = ()
    recommendation = None
    if comparison is not None and comparison.position is not None and status is DecisionStatus.AVAILABLE:
        observation = (
            f"{product_name}'s forecast sales {comparison.position.value} available capacity.",
        )
        if comparison.position is CapacityPosition.EXCEEDS:
            recommendation = _review(
                "forecast-capacity-review",
                RecommendationCategory.PRODUCTION,
                product_name,
                f"Review {product_name}'s forecast sales against available capacity.",
                evidence,
            )
    return _result("forecast_sales_vs_capacity", product_name, status, evidence, observation, recommendation=recommendation)


def evaluate_forecast_inventory_vs_desired(
    context: DecisionContext,
    product_name: str,
    desired_inventory: Decimal | None = None,
) -> RuleResult:
    forecast = context.inventory_forecasts.get(product_name)
    status = DecisionStatus.MISSING_INPUT
    comparison = None
    if forecast is not None:
        if forecast.status is not ForecastStatus.AVAILABLE:
            status = _forecast_status(forecast.status)
        elif desired_inventory is None:
            status = DecisionStatus.MISSING_INPUT
        else:
            comparison = compare_forecast_to_current(forecast.value, desired_inventory)
            status = comparison.status
    evidence = _evidence(
        product_name,
        (
            ("forecast_ending_inventory", None if forecast is None else forecast.value, "units"),
            ("desired_inventory", desired_inventory, "units"),
        ),
        context,
        status=status,
        source_rounds=() if forecast is None else forecast.source_rounds,
    )
    observation = () if comparison is None or comparison.direction is None else (
        f"{product_name}'s forecast ending inventory indicates a {comparison.direction.value} versus desired inventory.",
    )
    recommendation = None
    if status is DecisionStatus.AVAILABLE and comparison and comparison.direction.value != "no_change":
        recommendation = _review(
            "inventory-assumption-review",
            RecommendationCategory.INVENTORY,
            product_name,
            f"Review {product_name}'s inventory assumptions and production planning.",
            evidence,
        )
    assumptions = () if forecast is None else forecast.assumptions
    return _result("forecast_inventory_vs_desired", product_name, status, evidence, observation, assumptions, recommendation)


def evaluate_required_production_vs_capacity(
    context: DecisionContext,
    product_name: str,
    required_production: ForecastValue[Decimal] | None = None,
) -> RuleResult:
    product = _product(context, product_name)
    capacity = _capacity(context, product_name, product)
    status = DecisionStatus.MISSING_INPUT
    comparison = None
    if required_production is not None:
        if required_production.status is not ForecastStatus.AVAILABLE:
            status = _forecast_status(required_production.status)
        else:
            comparison = compare_forecast_to_capacity(required_production.value, capacity)
            status = comparison.status
    evidence = _evidence(
        product_name,
        (
            ("required_production", None if required_production is None else required_production.value, "units"),
            ("capacity_next_round", capacity, "units"),
        ),
        context,
        status=status,
        source_rounds=() if required_production is None else required_production.source_rounds,
    )
    observation = ()
    if comparison is not None and comparison.position is not None:
        observation = (
            f"{product_name}'s required production {comparison.position.value} available capacity.",
        )
    recommendation = None
    if comparison is not None and comparison.position is CapacityPosition.EXCEEDS and status is DecisionStatus.AVAILABLE:
        recommendation = _review(
            "required-production-capacity-review",
            RecommendationCategory.PRODUCTION,
            product_name,
            f"Review {product_name}'s required production against available capacity.",
            evidence,
        )
    return _result("required_production_vs_capacity", product_name, status, evidence, observation, recommendation=recommendation)


def evaluate_utilization_indicators(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    record = _production_record(context, product_name)
    metrics = context.production_analysis.products.get(product_name) if context.production_analysis else None
    utilization = metrics.plant_utilization_percent if metrics else None
    if utilization is None and record is not None:
        utilization = record.plant_utilization_percent
    overtime = metrics.overtime if metrics else None
    if overtime is None and record is not None:
        overtime = record.overtime
    status = DecisionStatus.AVAILABLE if utilization is not None and overtime is not None else DecisionStatus.MISSING_INPUT
    evidence = _evidence(
        product_name,
        (
            ("plant_utilization_percent", utilization, "percent"),
            ("combined_second_shift_overtime_percent", overtime, "percent"),
        ),
        context,
        status=status,
    )
    observations = ()
    if status is DecisionStatus.AVAILABLE:
        observations = (
            f"{product_name}'s reported plant utilization is {utilization}% and combined 2nd Shift & Overtime is {overtime}%.",
        )
    return _result("utilization_indicators", product_name, status, evidence, observations)


def evaluate_inventory_stockout(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    inventory = product.inventory_units if product else None
    forecast = context.inventory_forecasts.get(product_name)
    status = DecisionStatus.AVAILABLE if inventory is not None else DecisionStatus.MISSING_INPUT
    evidence = _evidence(
        product_name,
        (
            ("current_inventory", inventory, "units"),
            ("forecast_ending_inventory", None if forecast is None else forecast.value, "units"),
        ),
        context,
        status=status,
        source_rounds=() if forecast is None else forecast.source_rounds,
    )
    if status is not DecisionStatus.AVAILABLE:
        return _result("inventory_stockout", product_name, status, evidence)
    if inventory == 0:
        return _result(
            "inventory_stockout",
            product_name,
            status,
            evidence,
            ("A reported zero-inventory stockout condition is present.",),
            recommendation=_review(
                "inventory-stockout-review",
                RecommendationCategory.INVENTORY,
                product_name,
                f"Review {product_name}'s inventory and production planning.",
                evidence,
            ),
        )
    return _result("inventory_stockout", product_name, status, evidence, ("No reported zero-inventory stockout condition is present.",))


def _product(context: DecisionContext, name: str) -> Product | None:
    return next((item for item in context.report.products if item.name == name), None)


def _production_record(context: DecisionContext, name: str) -> ProductionRecord | None:
    return next((item for item in context.report.production if item.product_name == name), None)


def _capacity(context: DecisionContext, name: str, product: Product | None) -> int | None:
    metrics = context.production_analysis.products.get(name) if context.production_analysis else None
    if metrics is not None and metrics.capacity_next_round is not None:
        return metrics.capacity_next_round
    record = _production_record(context, name)
    if record is not None:
        if record.capacity_next_round is not None:
            return record.capacity_next_round
    return product.capacity_next_round if product else None


def _forecast_status(status: ForecastStatus) -> DecisionStatus:
    return {
        ForecastStatus.INSUFFICIENT_HISTORY: DecisionStatus.INSUFFICIENT_DATA,
        ForecastStatus.MISSING_INPUT: DecisionStatus.MISSING_INPUT,
        ForecastStatus.ZERO_DENOMINATOR: DecisionStatus.ZERO_DENOMINATOR,
        ForecastStatus.UNSUPPORTED: DecisionStatus.UNSUPPORTED,
    }.get(status, DecisionStatus.AVAILABLE)


def _evidence(
    product_name: str,
    values: Iterable[tuple[str, object, str | None]],
    context: DecisionContext,
    *,
    status: DecisionStatus,
    source_rounds: tuple[int, ...] | None = None,
) -> tuple[Evidence, ...]:
    rounds = (context.report.round_number,) if source_rounds is None else source_rounds
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
    observations: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    recommendation: Recommendation | None = None,
) -> RuleResult:
    return RuleResult(rule_id, status, "product", product_name, observations, evidence, assumptions, recommendation)


def _review(
    recommendation_id: str,
    category: RecommendationCategory,
    product_name: str,
    action: str,
    evidence: tuple[Evidence, ...],
) -> Recommendation:
    return Recommendation(
        recommendation_id,
        category,
        RecommendationPriority.INFORMATIONAL,
        "product",
        product_name,
        action,
        "This is a conservative review trigger based on supplied values.",
        evidence,
        (),
        DecisionStatus.INFORMATIONAL,
    )
