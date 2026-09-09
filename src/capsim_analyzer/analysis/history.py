from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from ..enums import Company, Segment
from ..models import CompanyFinancials, CourierReport, Product


@dataclass(frozen=True)
class ValueChange:
    previous: Any
    current: Any
    absolute_change: Any
    percent_change: Decimal | None
    status: str


@dataclass(frozen=True)
class EntityChanges:
    fields: Mapping[str, ValueChange]


@dataclass(frozen=True)
class RoundComparison:
    previous_round: int
    current_round: int
    segment_changes: Mapping[Segment, EntityChanges]
    market_share_changes: Mapping[tuple[Company, Segment], EntityChanges]
    product_changes: Mapping[str, EntityChanges]
    production_changes: Mapping[str, EntityChanges]
    financial_changes: Mapping[Company, EntityChanges]


@dataclass(frozen=True)
class HistoryIntegrity:
    simulation_id: str | None
    round_numbers: tuple[int, ...]
    ordered_by_round: bool
    duplicate_rounds: tuple[int, ...]


@dataclass(frozen=True)
class HistoryAnalysis:
    reports: tuple[CourierReport, ...]
    integrity: HistoryIntegrity
    comparisons: tuple[RoundComparison, ...]


def analyze_history(reports: Iterable[CourierReport]) -> HistoryAnalysis:
    """Compare already-parsed CourierReport objects across adjacent rounds."""
    original = tuple(reports)
    if not original:
        raise ValueError("at least one CourierReport is required")
    _validate_simulation_ids(original)

    round_numbers = tuple(report.round_number for report in original)
    duplicates = tuple(sorted({
        round_number for round_number in round_numbers
        if round_numbers.count(round_number) > 1
    }))
    if duplicates:
        raise ValueError(f"duplicate report rounds: {duplicates}")

    ordered = tuple(sorted(original, key=lambda report: report.round_number))
    integrity = HistoryIntegrity(
        simulation_id=_simulation_id(ordered),
        round_numbers=tuple(report.round_number for report in ordered),
        ordered_by_round=ordered == original,
        duplicate_rounds=duplicates,
    )
    return HistoryAnalysis(
        reports=ordered,
        integrity=integrity,
        comparisons=tuple(
            _compare_rounds(previous, current)
            for previous, current in zip(ordered, ordered[1:])
        ),
    )


def _validate_simulation_ids(reports: tuple[CourierReport, ...]) -> None:
    ids = {report.simulation_id for report in reports if report.simulation_id}
    if len(ids) > 1:
        raise ValueError("history reports must belong to the same simulation")


def _simulation_id(reports: tuple[CourierReport, ...]) -> str | None:
    ids = [report.simulation_id for report in reports if report.simulation_id]
    return ids[0] if ids else None


def _compare_rounds(previous: CourierReport, current: CourierReport) -> RoundComparison:
    return RoundComparison(
        previous_round=previous.round_number,
        current_round=current.round_number,
        segment_changes=_segment_changes(previous, current),
        market_share_changes=_market_share_changes(previous, current),
        product_changes=_product_changes(previous, current),
        production_changes=_production_changes(previous, current),
        financial_changes=_financial_changes(previous, current),
    )


def _segment_changes(previous: CourierReport, current: CourierReport):
    old = {item.segment: item for item in previous.segment_reports}
    new = {item.segment: item for item in current.segment_reports}
    changes = {}
    for segment in set(old) | set(new):
        old_item, new_item = old.get(segment), new.get(segment)
        changes[segment] = EntityChanges({
            "industry_unit_demand": _change(
                getattr(old_item, "total_industry_unit_demand", None),
                getattr(new_item, "total_industry_unit_demand", None),
            ),
            "actual_industry_unit_sales": _change(
                getattr(old_item, "actual_industry_unit_sales", None),
                getattr(new_item, "actual_industry_unit_sales", None),
            ),
            "percent_of_total_industry": _change(
                getattr(old_item, "percent_of_total_industry", None),
                getattr(new_item, "percent_of_total_industry", None),
            ),
            "next_year_growth_rate_percent": _change(
                getattr(old_item, "next_year_growth_rate_percent", None),
                getattr(new_item, "next_year_growth_rate_percent", None),
            ),
        })
    return changes


def _market_share_changes(previous: CourierReport, current: CourierReport):
    old = _market_share_values(previous)
    new = _market_share_values(current)
    return {
        key: EntityChanges({
            "actual_percent": _change(old.get(key, (None, None))[0], new.get(key, (None, None))[0]),
            "potential_percent": _change(old.get(key, (None, None))[1], new.get(key, (None, None))[1]),
        })
        for key in set(old) | set(new)
    }


def _market_share_values(report: CourierReport):
    values = {}
    if report.market_share is None:
        return values
    actual = {item.company: item for item in report.market_share.actual}
    potential = {item.company: item for item in report.market_share.potential}
    for company in set(actual) | set(potential):
        for segment in report.segments:
            values[(company, segment)] = (
                actual.get(company).segment_percentages.get(segment)
                if actual.get(company) else None,
                potential.get(company).segment_percentages.get(segment)
                if potential.get(company) else None,
            )
    return values


def _product_changes(previous: CourierReport, current: CourierReport):
    old = {item.name: item for item in previous.products}
    new = {item.name: item for item in current.products}
    fields = (
        "units_sold", "inventory_units", "list_price", "mtbf",
        "perceptual_position.performance", "perceptual_position.size",
    )
    return {
        name: EntityChanges({
            field: _change(_product_value(old.get(name), field), _product_value(new.get(name), field))
            for field in fields
        })
        for name in set(old) | set(new)
    }


def _product_value(product: Product | None, field: str):
    if product is None:
        return None
    value: Any = product
    for part in field.split("."):
        value = getattr(value, part)
    return value


def _production_changes(previous: CourierReport, current: CourierReport):
    old = {item.product_name: item for item in previous.production}
    new = {item.product_name: item for item in current.production}
    fields = (
        "capacity_next_round", "plant_utilization_percent",
        "units_sold", "inventory_units",
    )
    return {
        name: EntityChanges({
            field: _change(_production_value(old.get(name), field), _production_value(new.get(name), field))
            for field in fields
        })
        for name in set(old) | set(new)
    }


def _production_value(record, field: str):
    return getattr(record, field, None)


def _financial_changes(previous: CourierReport, current: CourierReport):
    old = {item.company: item for item in previous.company_financials}
    new = {item.company: item for item in current.company_financials}
    return {
        company: EntityChanges(_financial_fields(old.get(company), new.get(company)))
        for company in set(old) | set(new)
    }


def _financial_fields(
    previous: CompanyFinancials | None,
    current: CompanyFinancials | None,
):
    fields = {}
    for statement_name in ("income_statement", "balance_sheet", "cash_flow_statement"):
        old_values = getattr(previous, statement_name, {}) if previous else {}
        new_values = getattr(current, statement_name, {}) if current else {}
        for key in set(old_values) | set(new_values):
            fields[f"{statement_name}.{key}"] = _change(
                old_values.get(key),
                new_values.get(key),
            )
    return fields


def _change(previous: Any, current: Any) -> ValueChange:
    if previous is None and current is None:
        return ValueChange(previous, current, None, None, "unavailable")
    if previous is None:
        return ValueChange(previous, current, None, None, "missing_previous")
    if current is None:
        return ValueChange(previous, current, None, None, "missing_current")
    absolute = current - previous
    if previous == 0:
        return ValueChange(previous, current, absolute, None, "zero_previous")
    percent = Decimal(str(absolute)) / Decimal(str(previous)) * Decimal("100")
    return ValueChange(previous, current, absolute, percent, "available")
