from __future__ import annotations

from decimal import Decimal

from .context import DecisionContext
from .investment_rules import (
    evaluate_automation_investment,
    evaluate_capacity_investment,
    evaluate_investment_evidence_completeness,
    evaluate_plant_equipment_evidence,
)
from .finance_rules import (
    evaluate_cash_position,
    evaluate_debt_leverage,
    evaluate_financial_evidence_completeness,
    evaluate_financial_history,
    evaluate_profitability,
    evaluate_sales_contribution_margin,
)
from .marketing_rules import (
    evaluate_customer_survey_score,
    evaluate_marketing_evidence_completeness,
    evaluate_marketing_market_share_gap,
    evaluate_marketing_market_share_history,
    evaluate_promotion_awareness,
    evaluate_sales_budget_accessibility,
)
from .product_rules import (
    evaluate_product_age,
    evaluate_product_market_share_gap,
    evaluate_product_market_share_history,
    evaluate_product_mtbf,
    evaluate_product_positioning,
    evaluate_product_price,
    evaluate_product_sales_forecast,
)
from .production_rules import (
    evaluate_forecast_inventory_vs_desired,
    evaluate_forecast_sales_vs_capacity,
    evaluate_forecast_sales_vs_current,
    evaluate_inventory_stockout,
    evaluate_required_production_vs_capacity,
    evaluate_utilization_indicators,
)
from .types import DecisionReport, DecisionStatus, RuleResult


def evaluate_decisions(context: DecisionContext) -> DecisionReport:
    results = (
        *_product_results(context),
        *_production_results(context),
        *_marketing_results(context),
        *_finance_results(context),
        *_investment_results(context),
    )

    recommendations = tuple(
        result.recommendation
        for result in results
        if result.recommendation is not None
    )
    blocked_rules = tuple(
        result
        for result in results
        if result.status in _blocked_statuses()
    )
    data_quality_issues = tuple(
        evidence
        for result in blocked_rules
        for evidence in result.evidence
    )

    return DecisionReport(
        status=_overall_status(results),
        observations=results,
        recommendations=recommendations,
        blocked_rules=blocked_rules,
        data_quality_issues=data_quality_issues,
    )


def _product_results(context: DecisionContext) -> tuple[RuleResult, ...]:
    results: list[RuleResult] = []

    for product in context.report.products:
        product_name = product.name
        potential = _market_share_potential(context, product)
        results.extend(
            (
                evaluate_product_positioning(context, product_name),
                evaluate_product_price(context, product_name),
                evaluate_product_mtbf(context, product_name),
                evaluate_product_age(context, product_name),
                evaluate_product_market_share_gap(
                    context,
                    product_name,
                    potential=potential,
                ),
                evaluate_product_market_share_history(context, product_name),
                evaluate_product_sales_forecast(context, product_name),
            )
        )

    return tuple(results)


def _production_results(context: DecisionContext) -> tuple[RuleResult, ...]:
    results: list[RuleResult] = []

    for product in context.report.products:
        product_name = product.name
        results.extend(
            (
                evaluate_forecast_sales_vs_current(context, product_name),
                evaluate_forecast_sales_vs_capacity(context, product_name),
                evaluate_forecast_inventory_vs_desired(context, product_name),
                evaluate_required_production_vs_capacity(context, product_name),
                evaluate_utilization_indicators(context, product_name),
                evaluate_inventory_stockout(context, product_name),
            )
        )

    return tuple(results)


def _marketing_results(context: DecisionContext) -> tuple[RuleResult, ...]:
    results: list[RuleResult] = []

    for product in context.report.products:
        product_name = product.name
        potential = _market_share_potential(context, product)
        results.extend(
            (
                evaluate_promotion_awareness(context, product_name),
                evaluate_sales_budget_accessibility(context, product_name),
                evaluate_customer_survey_score(context, product_name),
                evaluate_marketing_market_share_gap(
                    context,
                    product_name,
                    potential=potential,
                ),
                evaluate_marketing_market_share_history(context, product_name),
                evaluate_marketing_evidence_completeness(context, product_name),
            )
        )

    return tuple(results)


def _finance_results(context: DecisionContext) -> tuple[RuleResult, ...]:
    results: list[RuleResult] = []

    for company in context.report.companies:
        results.extend(
            (
                evaluate_cash_position(context, company),
                evaluate_debt_leverage(context, company),
                evaluate_profitability(context, company),
                evaluate_sales_contribution_margin(context, company),
                evaluate_financial_history(context, company),
                evaluate_financial_evidence_completeness(context, company),
            )
        )

    return tuple(results)


def _investment_results(context: DecisionContext) -> tuple[RuleResult, ...]:
    results: list[RuleResult] = []

    for product in context.report.products:
        product_name = product.name
        results.extend(
            (
                evaluate_capacity_investment(context, product_name),
                evaluate_automation_investment(context, product_name),
            )
        )

    for company in context.report.companies:
        results.append(evaluate_plant_equipment_evidence(context, company))

    for product in context.report.products:
        product_name = product.name
        for company in context.report.companies:
            results.append(
                evaluate_investment_evidence_completeness(
                    context,
                    product_name,
                    company,
                )
            )

    return tuple(results)


def _market_share_potential(
    context: DecisionContext,
    product,
) -> Decimal | None:
    if context.market_share_analysis is None:
        return None
    metrics = context.market_share_analysis.companies.get(product.company)
    if metrics is None:
        return None
    return metrics.potential_by_segment.get(product.segment)


def _blocked_statuses() -> frozenset[DecisionStatus]:
    return frozenset(
        {
            DecisionStatus.MISSING_INPUT,
            DecisionStatus.INSUFFICIENT_DATA,
            DecisionStatus.CONFLICTING_DATA,
            DecisionStatus.UNSUPPORTED,
            DecisionStatus.ASSUMPTION_REQUIRED,
            DecisionStatus.ZERO_DENOMINATOR,
        }
    )


def _overall_status(results: tuple[RuleResult, ...]) -> DecisionStatus:
    statuses = {result.status for result in results}

    for status in (
        DecisionStatus.CONFLICTING_DATA,
        DecisionStatus.MISSING_INPUT,
        DecisionStatus.INSUFFICIENT_DATA,
        DecisionStatus.ZERO_DENOMINATOR,
        DecisionStatus.ASSUMPTION_REQUIRED,
        DecisionStatus.UNSUPPORTED,
    ):
        if status in statuses:
            return status

    if DecisionStatus.AVAILABLE in statuses:
        return DecisionStatus.AVAILABLE

    if DecisionStatus.INFORMATIONAL in statuses:
        return DecisionStatus.INFORMATIONAL

    return DecisionStatus.INSUFFICIENT_DATA
