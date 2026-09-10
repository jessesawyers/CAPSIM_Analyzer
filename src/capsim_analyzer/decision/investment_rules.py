from __future__ import annotations

from typing import Iterable

from ..enums import Company
from ..models import CompanyFinancials, CourierReport, Product, ProductionRecord
from .context import DecisionContext
from .types import DecisionStatus, Evidence, RuleResult


def evaluate_capacity_investment(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    record = _production_record(context, product_name)
    next_capacity = (
        record.capacity_next_round
        if record is not None
        else product.capacity_next_round
        if product is not None
        else None
    )
    evidence = _product_evidence(
        context,
        product_name,
        (
            ("current_capacity", None, "units"),
            ("next_round_capacity", next_capacity, "units"),
        ),
        DecisionStatus.MISSING_INPUT,
    )
    return _product_result(
        "capacity_investment",
        product_name,
        DecisionStatus.MISSING_INPUT,
        evidence,
        (
            "The report provides next-round capacity but no separate current-capacity value.",
        ),
    )


def evaluate_automation_investment(
    context: DecisionContext,
    product_name: str,
) -> RuleResult:
    product = _product(context, product_name)
    record = _production_record(context, product_name)
    automation = (
        record.automation_level
        if record is not None
        else product.automation_level
        if product is not None
        else None
    )
    evidence = _product_evidence(
        context,
        product_name,
        (
            ("current_automation", None, "level"),
            ("next_round_automation", automation, "level"),
        ),
        DecisionStatus.MISSING_INPUT,
    )
    return _product_result(
        "automation_investment",
        product_name,
        DecisionStatus.MISSING_INPUT,
        evidence,
        (
            "The report provides one automation value but no separate current and next-round values.",
        ),
    )


def evaluate_plant_equipment_evidence(
    context: DecisionContext,
    company: Company,
) -> RuleResult:
    financials = _financials(context.report, company)
    balance = financials.balance_sheet if financials else {}
    income = financials.income_statement if financials else {}
    values = (
        ("plant_and_equipment", balance.get("plant_and_equipment"), "currency"),
        ("accumulated_depreciation", balance.get("accumulated_depreciation"), "currency"),
        ("depreciation", income.get("depreciation"), "currency"),
    )
    status = (
        DecisionStatus.AVAILABLE
        if any(value is not None for _, value, _ in values)
        else DecisionStatus.MISSING_INPUT
    )
    evidence = _company_evidence(context, company, values, status)
    observations = (
        (f"{company.value}'s reported plant/equipment and depreciation evidence is available.",)
        if status is DecisionStatus.AVAILABLE
        else ()
    )
    return RuleResult(
        "plant_equipment_evidence",
        status,
        "company",
        company.value,
        observations,
        evidence,
        (),
        None,
    )


def evaluate_investment_evidence_completeness(
    context: DecisionContext,
    product_name: str,
    company: Company,
) -> RuleResult:
    product = _product(context, product_name)
    record = _production_record(context, product_name)
    financials = _financials(context.report, company)
    balance = financials.balance_sheet if financials else {}
    income = financials.income_statement if financials else {}
    values = (
        ("reported_capacity", _capacity(product, record), "units"),
        ("reported_automation", _automation(product, record), "level"),
        ("plant_and_equipment", balance.get("plant_and_equipment"), "currency"),
        ("accumulated_depreciation", balance.get("accumulated_depreciation"), "currency"),
        ("depreciation", income.get("depreciation"), "currency"),
    )
    missing = tuple(metric for metric, value, _ in values if value is None)
    status = DecisionStatus.AVAILABLE if not missing else DecisionStatus.MISSING_INPUT
    evidence = _mixed_evidence(context, product_name, company, values, status)
    observation = (
        f"Investment evidence is complete for {product_name} and {company.value}."
        if not missing
        else f"Investment evidence is missing: {', '.join(missing)}."
    )
    return _product_result(
        "investment_evidence_completeness",
        product_name,
        status,
        evidence,
        (observation,),
    )


def _product(context: DecisionContext, product_name: str) -> Product | None:
    return next(
        (product for product in context.report.products if product.name == product_name),
        None,
    )


def _production_record(
    context: DecisionContext,
    product_name: str,
) -> ProductionRecord | None:
    return next(
        (
            record
            for record in context.report.production
            if record.product_name == product_name
        ),
        None,
    )


def _financials(
    report: CourierReport,
    company: Company,
) -> CompanyFinancials | None:
    return next(
        (financials for financials in report.company_financials if financials.company is company),
        None,
    )


def _capacity(
    product: Product | None,
    record: ProductionRecord | None,
) -> int | None:
    if record is not None:
        return record.capacity_next_round
    return product.capacity_next_round if product is not None else None


def _automation(
    product: Product | None,
    record: ProductionRecord | None,
):
    if record is not None:
        return record.automation_level
    return product.automation_level if product is not None else None


def _product_evidence(
    context: DecisionContext,
    product_name: str,
    values: Iterable[tuple[str, object, str | None]],
    status: DecisionStatus,
) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(
            "observed",
            metric,
            "product",
            product_name,
            value,
            unit,
            (context.report.round_number,),
            status,
            f"{metric} for product {product_name}.",
        )
        for metric, value, unit in values
    )


def _company_evidence(
    context: DecisionContext,
    company: Company,
    values: Iterable[tuple[str, object, str | None]],
    status: DecisionStatus,
) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(
            "observed",
            metric,
            "company",
            company.value,
            value,
            unit,
            (context.report.round_number,),
            status,
            f"{metric} for company {company.value}.",
        )
        for metric, value, unit in values
    )


def _mixed_evidence(
    context: DecisionContext,
    product_name: str,
    company: Company,
    values: Iterable[tuple[str, object, str | None]],
    status: DecisionStatus,
) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(
            "observed",
            metric,
            "product",
            product_name,
            value,
            unit,
            (context.report.round_number,),
            status,
            f"{metric} for {product_name} and {company.value}.",
        )
        for metric, value, unit in values
    )


def _product_result(
    rule_id: str,
    product_name: str,
    status: DecisionStatus,
    evidence: tuple[Evidence, ...],
    observations: tuple[str, ...] = (),
) -> RuleResult:
    return RuleResult(
        rule_id,
        status,
        "product",
        product_name,
        observations,
        evidence,
        (),
        None,
    )
