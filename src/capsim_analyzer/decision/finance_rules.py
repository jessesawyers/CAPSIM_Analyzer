from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Iterable

from ..analysis.finance import analyze_financials
from ..analysis.types import FinancialMetrics
from ..enums import Company
from ..models import CompanyFinancials, CourierReport
from .comparisons import compare_to_expected
from .context import DecisionContext
from .types import (
    ComparisonDirection,
    DecisionStatus,
    Evidence,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RuleResult,
)


def evaluate_cash_position(
    context: DecisionContext,
    company: Company,
    comparison_target: Decimal | None = None,
) -> RuleResult:
    metrics = _metrics(context, company)
    cash = metrics.cash if metrics else None
    status = DecisionStatus.AVAILABLE if cash is not None else DecisionStatus.MISSING_INPUT
    evidence = _evidence(
        context,
        company,
        (("cash", cash, "currency"), ("cash_comparison_target", comparison_target, "currency")),
        status,
    )
    if status is not DecisionStatus.AVAILABLE:
        return _result("cash_position", company, status, evidence)
    if comparison_target is None:
        observations = (f"{company.value}'s reported cash position is {cash}.",)
        return _result("cash_position", company, status, evidence, observations)
    comparison = compare_to_expected(cash, comparison_target)
    observations = (f"{company.value}'s cash is {comparison.direction.value} the supplied comparison target.",)
    recommendation = (
        _review(
            "cash-position-review",
            company,
            "Review the company's cash position against the supplied comparison target.",
            evidence,
        )
        if comparison.direction is ComparisonDirection.DECREASE
        else None
    )
    return _result("cash_position", company, status, evidence, observations, recommendation)


def evaluate_debt_leverage(context: DecisionContext, company: Company) -> RuleResult:
    metrics = _metrics(context, company)
    total_debt = metrics.total_debt if metrics else None
    total_equity = metrics.total_equity if metrics else None
    ratio = metrics.debt_to_equity if metrics else None
    status = _status_for_values(total_debt, total_equity, ratio)
    evidence = _evidence(
        context,
        company,
        (
            ("total_debt", total_debt, "currency"),
            ("total_equity", total_equity, "currency"),
            ("debt_to_equity", ratio, "ratio"),
        ),
        status,
    )
    observations = () if status is not DecisionStatus.AVAILABLE else (
        f"{company.value}'s reported total debt is {total_debt}, total equity is {total_equity}, "
        f"and debt-to-equity is {ratio}.",
    )
    return _result("debt_leverage", company, status, evidence, observations)


def evaluate_profitability(context: DecisionContext, company: Company) -> RuleResult:
    metrics = _metrics(context, company)
    net_profit = metrics.net_profit if metrics else None
    margin = metrics.net_profit_margin if metrics else None
    status = DecisionStatus.AVAILABLE if net_profit is not None else DecisionStatus.MISSING_INPUT
    evidence = _evidence(
        context,
        company,
        (("net_profit", net_profit, "currency"), ("net_profit_margin", margin, "percent")),
        status,
    )
    if status is not DecisionStatus.AVAILABLE:
        return _result("profitability", company, status, evidence)
    observations = (f"{company.value}'s reported net profit is {net_profit} and net profit margin is {margin}.",)
    history = evaluate_financial_history(context, company, metric="net_profit")
    if history.status is DecisionStatus.AVAILABLE:
        observations += history.observations
    return _result("profitability", company, status, evidence, observations)


def evaluate_sales_contribution_margin(
    context: DecisionContext,
    company: Company,
) -> RuleResult:
    metrics = _metrics(context, company)
    sales = metrics.revenue if metrics else None
    contribution_margin = metrics.contribution_margin if metrics else None
    margin_percent = metrics.contribution_margin_percent if metrics else None
    status = _status_for_values(sales, contribution_margin, margin_percent)
    evidence = _evidence(
        context,
        company,
        (
            ("sales", sales, "currency"),
            ("contribution_margin", contribution_margin, "currency"),
            ("contribution_margin_percent", margin_percent, "percent"),
        ),
        status,
    )
    observations = () if status is not DecisionStatus.AVAILABLE else (
        f"{company.value}'s reported sales are {sales}, contribution margin is {contribution_margin}, "
        f"and contribution-margin percentage is {margin_percent}.",
    )
    return _result("sales_contribution_margin", company, status, evidence, observations)


def evaluate_financial_history(
    context: DecisionContext,
    company: Company,
    metric: str = "net_profit",
) -> RuleResult:
    history = context.history_analysis
    if history is None or len(history.reports) < 2:
        return _result("financial_history", company, DecisionStatus.INSUFFICIENT_DATA, ())
    previous = _financial_value(history.reports[-2], company, metric)
    current = _financial_value(history.reports[-1], company, metric)
    comparison = compare_to_expected(current, previous)
    evidence = _evidence(
        context,
        company,
        ((f"previous_{metric}", previous, "currency"), (f"current_{metric}", current, "currency")),
        comparison.status,
        round_number=history.reports[-1].round_number,
    )
    observations = () if comparison.direction is None else (
        f"{company.value}'s {metric.replace('_', ' ')} {comparison.direction.value}d across the latest rounds.",
    )
    return _result("financial_history", company, comparison.status, evidence, observations)


def evaluate_financial_evidence_completeness(
    context: DecisionContext,
    company: Company,
) -> RuleResult:
    metrics = _metrics(context, company)
    values = (
        ("cash", metrics.cash if metrics else None, "currency"),
        ("total_debt", metrics.total_debt if metrics else None, "currency"),
        ("total_equity", metrics.total_equity if metrics else None, "currency"),
        ("sales", metrics.revenue if metrics else None, "currency"),
        ("contribution_margin", metrics.contribution_margin if metrics else None, "currency"),
        ("net_profit", metrics.net_profit if metrics else None, "currency"),
    )
    missing = tuple(metric for metric, value, _ in values if value is None)
    status = DecisionStatus.AVAILABLE if not missing else DecisionStatus.MISSING_INPUT
    evidence = _evidence(context, company, values, status)
    observations = (
        (f"Required financial evidence is complete for {company.value}.",)
        if not missing
        else (f"Financial evidence is missing: {', '.join(missing)}.",)
    )
    return _result("financial_evidence_completeness", company, status, evidence, observations)


def _metrics(context: DecisionContext, company: Company) -> FinancialMetrics | None:
    if context.financial_analysis is None:
        return analyze_financials(context.report).companies.get(company)

    metrics = context.financial_analysis.companies.get(company)
    financials = _financials(context.report, company)
    if financials is None:
        return metrics

    direct = _direct_values(financials)
    if metrics is None:
        return _direct_only_metrics(company, direct)

    return replace(
        metrics,
        **{
            field: getattr(metrics, field)
            if getattr(metrics, field) is not None
            else value
            for field, value in direct.items()
        },
    )


def _financials(
    report: CourierReport,
    company: Company,
) -> CompanyFinancials | None:
    return next(
        (financials for financials in report.company_financials if financials.company is company),
        None,
    )


def _direct_values(financials: CompanyFinancials) -> dict[str, Decimal | None]:
    income = financials.income_statement
    balance = financials.balance_sheet
    return {
        "cash": balance.get("cash"),
        "revenue": income.get("sales"),
        "contribution_margin": income.get("contribution_margin"),
        "net_profit": income.get("net_profit"),
        "total_equity": balance.get("total_equity"),
        "current_debt": balance.get("current_debt"),
        "long_term_debt": balance.get("long_term_debt"),
    }


def _direct_only_metrics(
    company: Company,
    direct: dict[str, Decimal | None],
) -> FinancialMetrics:
    return FinancialMetrics(
        company=company,
        financials_available=any(value is not None for value in direct.values()),
        revenue=direct["revenue"],
        direct_labor=None,
        direct_material=None,
        contribution_margin=direct["contribution_margin"],
        contribution_margin_percent=None,
        ebit=None,
        ebit_margin=None,
        net_profit=direct["net_profit"],
        net_profit_margin=None,
        cash=direct["cash"],
        accounts_receivable=None,
        inventory=None,
        total_assets=None,
        accounts_payable=None,
        long_term_debt=direct["long_term_debt"],
        common_stock=None,
        retained_earnings=None,
        current_debt=direct["current_debt"],
        total_liabilities=None,
        total_equity=direct["total_equity"],
        total_debt=None,
        debt_to_equity=None,
        balance_sheet_difference=None,
        balance_sheet_consistent=None,
        cash_flow={},
    )


def _financial_value(report: CourierReport, company: Company, metric: str) -> Decimal | None:
    metrics = analyze_financials(report).companies.get(company)
    if metrics is None:
        return None
    if metric in {"sales", "revenue"}:
        return metrics.revenue
    return getattr(metrics, metric, None)


def _status_for_values(*values) -> DecisionStatus:
    return DecisionStatus.AVAILABLE if all(value is not None for value in values) else DecisionStatus.MISSING_INPUT


def _evidence(
    context: DecisionContext,
    company: Company,
    values: Iterable[tuple[str, object, str | None]],
    status: DecisionStatus,
    *,
    round_number: int | None = None,
) -> tuple[Evidence, ...]:
    source_round = context.report.round_number if round_number is None else round_number
    return tuple(
        Evidence(
            kind="observed",
            metric=metric,
            entity_type="company",
            entity_id=company.value,
            value=value,
            unit=unit,
            source_rounds=(source_round,),
            status=status,
            explanation=f"{metric} for company {company.value}.",
        )
        for metric, value, unit in values
    )


def _result(
    rule_id: str,
    company: Company,
    status: DecisionStatus,
    evidence: tuple[Evidence, ...],
    observations: tuple[str, ...] = (),
    recommendation: Recommendation | None = None,
) -> RuleResult:
    return RuleResult(rule_id, status, "company", company.value, observations, evidence, (), recommendation)


def _review(
    recommendation_id: str,
    company: Company,
    action: str,
    evidence: tuple[Evidence, ...],
) -> Recommendation:
    return Recommendation(
        recommendation_id,
        RecommendationCategory.FINANCE,
        RecommendationPriority.INFORMATIONAL,
        "company",
        company.value,
        action,
        "This is a conservative review trigger based on supplied financial evidence, not a guaranteed outcome.",
        evidence,
        (),
        DecisionStatus.INFORMATIONAL,
    )
