from __future__ import annotations

from decimal import Decimal
from math import sqrt

from ..enums import Segment
from ..models import (
    BuyingCriterion,
    CourierReport,
    Product,
    ProductionRecord,
    SegmentProductSnapshot,
)
from .types import ProductAnalysis, ProductConsistencyCheck, ProductMetrics


def analyze_products(report: CourierReport) -> ProductAnalysis:
    """Calculate product facts from an existing structured CourierReport."""
    snapshots = _snapshots_by_product(report)
    criteria = {
        segment: _criteria_by_name(segment_report.buying_criteria)
        for segment, segment_report in _segment_reports(report).items()
    }
    products = {
        product.name: _product_metrics(
            product,
            snapshots.get((product.name, product.segment)),
            criteria.get(product.segment, {}),
        )
        for product in report.products
    }
    return ProductAnalysis(
        products=products,
        rankings_by_segment=_rankings(products, report.segments),
        consistency_checks=_consistency_checks(report, snapshots),
    )


def _segment_reports(report: CourierReport):
    return {item.segment: item for item in report.segment_reports}


def _snapshots_by_product(
    report: CourierReport,
) -> dict[tuple[str, Segment], SegmentProductSnapshot]:
    snapshots = {}
    for segment_report in report.segment_reports:
        for snapshot in segment_report.products:
            snapshots[(snapshot.product_name, segment_report.segment)] = snapshot
    return snapshots


def _criteria_by_name(criteria: list[BuyingCriterion]) -> dict[str, BuyingCriterion]:
    return {criterion.criterion: criterion for criterion in criteria}


def _product_metrics(
    product: Product,
    snapshot: SegmentProductSnapshot | None,
    criteria: dict[str, BuyingCriterion],
) -> ProductMetrics:
    position = product.perceptual_position
    ideal_position = criteria.get("Ideal Position")
    ideal_performance, ideal_size = _position_expectations(ideal_position)
    performance_difference = _difference(position.performance, ideal_performance)
    size_difference = _difference(position.size, ideal_size)
    distance = _distance(performance_difference, size_difference)

    price_criterion = criteria.get("Price")
    price_min, price_max = _range_expectations(price_criterion, "minimum", "maximum")
    mtbf_criterion = criteria.get("Reliability")
    mtbf_min, mtbf_max = _range_expectations(mtbf_criterion, "minimum", "maximum")
    age_criterion = criteria.get("Age")
    ideal_age = _criterion_value(age_criterion, "ideal_age_years")

    units_sold = product.units_sold
    inventory = product.inventory_units
    margin_amount = _contribution_margin_amount(product)
    return ProductMetrics(
        product_name=product.name,
        company=product.company,
        segment=product.segment,
        performance_difference=performance_difference,
        size_difference=size_difference,
        perceptual_distance=distance,
        price_difference=_difference(product.list_price, _midpoint(price_min, price_max)),
        price_in_expected_range=_in_range(product.list_price, price_min, price_max),
        mtbf_difference=_difference(product.mtbf, _midpoint_int(mtbf_min, mtbf_max)),
        mtbf_in_expected_range=_in_range(product.mtbf, mtbf_min, mtbf_max),
        age_difference=_difference(product.age_years, ideal_age),
        units_sold=units_sold,
        inventory_units=inventory,
        inventory_to_sales_ratio=(
            None if units_sold in (None, 0) or inventory is None
            else Decimal(inventory) / Decimal(units_sold)
        ),
        market_share_percent=snapshot.market_share_percent if snapshot else None,
        contribution_margin_amount=margin_amount,
        contribution_margin_percent=product.contribution_margin_percent,
        material_cost=product.material_cost,
        labor_cost=product.labor_cost,
        customer_awareness_percent=snapshot.customer_awareness_percent if snapshot else None,
        customer_accessibility_percent=snapshot.customer_accessibility_percent if snapshot else None,
        customer_survey_score=snapshot.customer_survey_score if snapshot else None,
        plant_utilization_percent=product.plant_utilization_percent,
    )


def _position_expectations(criterion: BuyingCriterion | None):
    if criterion is None:
        return None, None
    return (
        _decimal_value(criterion.expectations.get("performance")),
        _decimal_value(criterion.expectations.get("size")),
    )


def _range_expectations(criterion: BuyingCriterion | None, low_key: str, high_key: str):
    if criterion is None:
        return None, None
    return (
        _numeric_value(criterion.expectations.get(low_key)),
        _numeric_value(criterion.expectations.get(high_key)),
    )


def _criterion_value(criterion: BuyingCriterion | None, key: str):
    return _decimal_value(criterion.expectations.get(key)) if criterion else None


def _decimal_value(value):
    return value if isinstance(value, Decimal) else None


def _numeric_value(value):
    return value if isinstance(value, (Decimal, int)) else None


def _difference(value, expected):
    return None if value is None or expected is None else value - expected


def _distance(performance_difference, size_difference):
    if performance_difference is None or size_difference is None:
        return None
    return Decimal(str(sqrt(float(performance_difference ** 2 + size_difference ** 2))))


def _midpoint(low, high):
    return None if low is None or high is None else (low + high) / Decimal("2")


def _midpoint_int(low, high):
    return None if low is None or high is None else (low + high) // 2


def _in_range(value, low, high):
    if value is None or low is None or high is None:
        return None
    return low <= value <= high


def _contribution_margin_amount(product: Product):
    if (
        product.units_sold is None
        or product.list_price is None
        or product.material_cost is None
        or product.labor_cost is None
    ):
        return None
    unit_margin = product.list_price - product.material_cost - product.labor_cost
    return unit_margin * Decimal(product.units_sold)


def _rankings(products: dict[str, ProductMetrics], segments: list[Segment]):
    result = {}
    for segment in segments:
        names = [name for name, item in products.items() if item.segment is segment]
        result[segment] = {
            metric: tuple(
                sorted(
                    (
                        name for name in names
                        if getattr(products[name], metric) is not None
                    ),
                    key=lambda name: (-getattr(products[name], metric), name),
                )
            )
            for metric in ("market_share_percent", "units_sold", "customer_survey_score")
        }
    return result


def _consistency_checks(
    report: CourierReport,
    snapshots: dict[tuple[str, Segment], SegmentProductSnapshot],
):
    production = {record.product_name: record for record in report.production}
    segment_by_product = {
        snapshot.product_name: segment_report.segment
        for segment_report in report.segment_reports
        for snapshot in segment_report.products
    }
    products = {product.name: product for product in report.products}
    checks = {}
    for name, product in products.items():
        record = production.get(name)
        snapshot = snapshots.get((name, product.segment))
        checks[name] = ProductConsistencyCheck(
            product_name=name,
            production_record_found=record is not None,
            segment_snapshot_found=snapshot is not None,
            company_consistent=_company_consistent(product, record),
            segment_consistent=_segment_consistent(product, record, segment_by_product.get(name)),
            units_sold_consistent=_units_consistent(product, record, snapshot),
        )
    return checks


def _company_consistent(product: Product, record: ProductionRecord | None):
    return None if record is None else record.company is product.company


def _segment_consistent(product: Product, record, snapshot_segment):
    if record is None and snapshot_segment is None:
        return None
    return (
        (record is None or record.primary_segment is product.segment)
        and (snapshot_segment is None or snapshot_segment is product.segment)
    )


def _units_consistent(product: Product, record, snapshot):
    values = [
        value for value in (
            product.units_sold,
            record.units_sold if record else None,
            snapshot.units_sold if snapshot else None,
        ) if value is not None
    ]
    return None if len(values) < 2 else len(set(values)) == 1
