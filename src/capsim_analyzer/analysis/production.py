from __future__ import annotations

from decimal import Decimal

from ..enums import Company, Segment
from ..models import CourierReport, ProductionRecord, SegmentProductSnapshot
from .types import (
    ProductionAnalysis,
    ProductionConsistencyCheck,
    ProductionMetrics,
    ProductionSummary,
)


def analyze_production(report: CourierReport) -> ProductionAnalysis:
    """Calculate production, capacity, inventory, and consistency facts."""
    products = {product.name: product for product in report.products}
    snapshots = _snapshots(report)
    records = {
        record.product_name: record
        for record in report.production
    }
    metrics = {
        name: _metrics(record)
        for name, record in records.items()
    }
    return ProductionAnalysis(
        products=metrics,
        rankings_by_utilization=_utilization_ranking(metrics),
        company_summaries={
            company: _summary(
                [item for item in metrics.values() if item.company is company]
            )
            for company in report.companies
        },
        segment_summaries={
            segment: _summary(
                [item for item in metrics.values() if item.segment is segment]
            )
            for segment in report.segments
        },
        consistency_checks=_consistency_checks(
            report,
            products,
            records,
            snapshots,
        ),
    )


def _metrics(record: ProductionRecord) -> ProductionMetrics:
    units = record.units_sold
    capacity = record.capacity_next_round
    inventory = record.inventory_units
    return ProductionMetrics(
        product_name=record.product_name,
        company=record.company,
        segment=record.primary_segment,
        units_sold=units,
        inventory_units=inventory,
        capacity_next_round=capacity,
        plant_utilization_percent=record.plant_utilization_percent,
        units_sold_as_capacity_percent=(
            None
            if units is None or capacity in (None, 0)
            else Decimal(units) / Decimal(capacity) * Decimal("100")
        ),
        capacity_headroom=(
            None if units is None or capacity is None else capacity - units
        ),
        second_shift_percent=record.second_shift_percent,
        overtime=record.overtime,
        inventory_to_sales_ratio=(
            None
            if inventory is None or units in (None, 0)
            else Decimal(inventory) / Decimal(units)
        ),
    )


def _utilization_ranking(
    products: dict[str, ProductionMetrics],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                name
                for name, item in products.items()
                if item.plant_utilization_percent is not None
            ),
            key=lambda name: (
                -products[name].plant_utilization_percent,
                name,
            ),
        )
    )


def _summary(items: list[ProductionMetrics]) -> ProductionSummary:
    return ProductionSummary(
        units_sold=_total(items, "units_sold"),
        inventory_units=_total(items, "inventory_units"),
        capacity_next_round=_total(items, "capacity_next_round"),
        capacity_headroom=_total(items, "capacity_headroom"),
        complete_units=_complete(items, "units_sold"),
        complete_inventory=_complete(items, "inventory_units"),
        complete_capacity=_complete(items, "capacity_next_round"),
    )


def _total(items: list[ProductionMetrics], field_name: str) -> int | None:
    values = [
        getattr(item, field_name)
        for item in items
        if getattr(item, field_name) is not None
    ]
    return sum(values) if values else None


def _complete(items: list[ProductionMetrics], field_name: str) -> bool:
    return bool(items) and all(getattr(item, field_name) is not None for item in items)


def _snapshots(
    report: CourierReport,
) -> dict[tuple[str, Segment], SegmentProductSnapshot]:
    return {
        (snapshot.product_name, segment_report.segment): snapshot
        for segment_report in report.segment_reports
        for snapshot in segment_report.products
    }


def _consistency_checks(
    report: CourierReport,
    products,
    records: dict[str, ProductionRecord],
    snapshots: dict[tuple[str, Segment], SegmentProductSnapshot],
) -> dict[str, ProductionConsistencyCheck]:
    names = set(products) | set(records)
    checks = {}
    for name in names:
        product = products.get(name)
        record = records.get(name)
        snapshot = (
            snapshots.get((name, product.segment))
            if product is not None
            else None
        )
        checks[name] = ProductionConsistencyCheck(
            product_name=name,
            product_found=product is not None,
            segment_snapshot_found=snapshot is not None,
            company_consistent=(
                None
                if product is None or record is None
                else product.company is record.company
            ),
            segment_consistent=_segment_consistent(product, record, snapshot),
            units_sold_consistent=_units_consistent(product, record, snapshot),
        )
    return checks


def _segment_consistent(product, record, snapshot) -> bool | None:
    values = [
        value
        for value in (
            product.segment if product is not None else None,
            record.primary_segment if record is not None else None,
            _snapshot_segment(snapshot),
        )
        if value is not None
    ]
    return None if len(values) < 2 else len(set(values)) == 1


def _snapshot_segment(snapshot):
    return None


def _units_consistent(product, record, snapshot) -> bool | None:
    values = [
        value
        for value in (
            product.units_sold if product is not None else None,
            record.units_sold if record is not None else None,
            snapshot.units_sold if snapshot is not None else None,
        )
        if value is not None
    ]
    return None if len(values) < 2 else len(set(values)) == 1
