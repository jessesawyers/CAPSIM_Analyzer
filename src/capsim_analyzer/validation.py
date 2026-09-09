from __future__ import annotations

from decimal import Decimal

from .enums import Company, Segment
from .models import CourierReport


EXPECTED_COMPANIES = list(Company)
EXPECTED_SEGMENTS = list(Segment)


def validate_report(report: CourierReport) -> None:
    errors: list[str] = []

    if report.round_number < 0:
        errors.append("round_number must be non-negative")
    if set(report.companies) != set(EXPECTED_COMPANIES):
        errors.append("report must contain exactly the six CAPSIM companies")
    if set(report.segments) != set(EXPECTED_SEGMENTS):
        errors.append("report must contain exactly the five CAPSIM segments")
    if len({product.name for product in report.products}) != len(report.products):
        errors.append("product names must be unique")

    company_set = set(report.companies)
    for product in report.products:
        if product.company not in company_set:
            errors.append(f"product {product.name!r} references an unknown company")
        errors.extend(message for message in (_non_negative(product.name, value, field_name) for field_name, value in (
            ("units_sold", product.units_sold),
            ("inventory_units", product.inventory_units),
            ("capacity_next_round", product.capacity_next_round),
            ("mtbf", product.mtbf),
        ) if value is not None) if message)
        for field_name, value in (
            ("contribution_margin_percent", product.contribution_margin_percent),
            ("plant_utilization_percent", product.plant_utilization_percent),
        ):
            if value is not None and not _percentage(value):
                errors.append(f"{product.name}.{field_name} must be between 0 and 100")

    for segment_report in report.segment_reports:
        if segment_report.segment not in report.segments:
            errors.append(f"unknown segment report: {segment_report.segment}")
        for field_name in ("total_industry_unit_demand", "actual_industry_unit_sales"):
            if getattr(segment_report, field_name) < 0:
                errors.append(f"{segment_report.segment}.{field_name} must be non-negative")
        if not _percentage(segment_report.percent_of_total_industry):
            errors.append(f"{segment_report.segment}.percent_of_total_industry must be between 0 and 100")
        if not _percentage(segment_report.next_year_growth_rate_percent):
            errors.append(f"{segment_report.segment}.next_year_growth_rate_percent must be between 0 and 100")

    for financials in report.company_financials:
        if financials.company not in company_set:
            errors.append(f"financials reference an unknown company: {financials.company}")

    if errors:
        raise ValueError("; ".join(errors))


def _percentage(value: Decimal) -> bool:
    return Decimal("0") <= value <= Decimal("100")


def _non_negative(product_name: str, value: int, field_name: str) -> str:
    return "" if value >= 0 else f"{product_name}.{field_name} must be non-negative"
