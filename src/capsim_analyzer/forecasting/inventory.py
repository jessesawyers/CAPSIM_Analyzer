from __future__ import annotations

from decimal import Decimal

from ..models import Product
from .types import ForecastStatus, ForecastValue


INVENTORY_COVERAGE_METHOD = "inventory_coverage"
INVENTORY_CHANGE_METHOD = "required_inventory_change"
PRODUCTION_REQUIREMENT_METHOD = "mechanical_production_requirement"
NO_ROUNDING_ASSUMPTION = "inventory quantities remain Decimal and are not rounded"
COVERAGE_ASSUMPTION = "coverage is an explicitly supplied inventory-to-sales quantity"
PRODUCTION_ASSUMPTION = (
    "production is a mechanical quantity calculation, not a CAPSIM production decision"
)


def forecast_ending_inventory(
    product: Product,
    forecast_sales: ForecastValue[Decimal] | None,
    inventory_coverage: Decimal | None,
) -> ForecastValue[Decimal]:
    """Estimate ending inventory from sales and an explicit coverage assumption."""
    common = _common(
        INVENTORY_COVERAGE_METHOD,
        forecast_sales,
        assumptions=(COVERAGE_ASSUMPTION, NO_ROUNDING_ASSUMPTION),
    )
    if forecast_sales is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if forecast_sales.status is not ForecastStatus.AVAILABLE:
        return ForecastValue(None, forecast_sales.status, **common)
    if forecast_sales.value is None or inventory_coverage is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if inventory_coverage <= 0:
        return ForecastValue(None, ForecastStatus.UNSUPPORTED, **common)
    return ForecastValue(
        forecast_sales.value * inventory_coverage,
        ForecastStatus.AVAILABLE,
        **common,
    )


def calculate_required_inventory_change(
    product: Product,
    forecast_ending_inventory: ForecastValue[Decimal] | None,
) -> ForecastValue[Decimal]:
    """Calculate the change from current product inventory to forecast inventory."""
    common = _common(
        INVENTORY_CHANGE_METHOD,
        forecast_ending_inventory,
        assumptions=(NO_ROUNDING_ASSUMPTION,),
    )
    if forecast_ending_inventory is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if forecast_ending_inventory.status is not ForecastStatus.AVAILABLE:
        return ForecastValue(None, forecast_ending_inventory.status, **common)
    if (
        forecast_ending_inventory.value is None
        or product.inventory_units is None
    ):
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    return ForecastValue(
        forecast_ending_inventory.value - Decimal(product.inventory_units),
        ForecastStatus.AVAILABLE,
        **common,
    )


def calculate_required_production(
    forecast_sales: ForecastValue[Decimal] | None,
    desired_ending_inventory: Decimal | None,
    beginning_inventory: Decimal | None,
) -> ForecastValue[Decimal]:
    """Calculate production mechanically from sales and inventory quantities."""
    common = _common(
        PRODUCTION_REQUIREMENT_METHOD,
        forecast_sales,
        assumptions=(PRODUCTION_ASSUMPTION, NO_ROUNDING_ASSUMPTION),
    )
    if forecast_sales is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if forecast_sales.status is not ForecastStatus.AVAILABLE:
        return ForecastValue(None, forecast_sales.status, **common)
    if (
        forecast_sales.value is None
        or desired_ending_inventory is None
        or beginning_inventory is None
    ):
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    return ForecastValue(
        forecast_sales.value + desired_ending_inventory - beginning_inventory,
        ForecastStatus.AVAILABLE,
        **common,
    )


def _common(
    method: str,
    source: ForecastValue[Decimal] | None,
    *,
    assumptions: tuple[str, ...],
) -> dict:
    return {
        "method": method,
        "source_rounds": () if source is None else source.source_rounds,
        "required_history": 1 if source is None else source.required_history,
        "available_history": 0 if source is None else source.available_history,
        "assumptions": assumptions,
    }
