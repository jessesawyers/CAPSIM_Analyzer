from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from ..analysis.history import analyze_history
from ..enums import Segment
from ..models import CourierReport, Product, SegmentProductSnapshot
from .segments import forecast_segment_demand_with_courier_growth
from .types import ForecastStatus, ForecastValue


MARKET_SHARE_METHOD = "market_share_based_product_sales"
HISTORICAL_GROWTH_METHOD = "historical_product_percentage_growth"
NO_ROUNDING_ASSUMPTION = "forecast product units remain Decimal and are not rounded"
SHARE_ASSUMPTION = "the most recent observed product market share persists"


def forecast_product_sales_from_market_share(
    reports: Iterable[CourierReport],
    segment_demand_forecasts: Mapping[
        Segment, ForecastValue[Decimal]
    ] | None = None,
) -> Mapping[str, ForecastValue[Decimal]]:
    """Forecast latest products from forecast segment demand and observed share."""
    history = analyze_history(reports)
    current = history.reports[-1]
    demand_forecasts = segment_demand_forecasts
    if demand_forecasts is None:
        demand_forecasts = forecast_segment_demand_with_courier_growth(current)

    return {
        product.name: _market_share_forecast(
            current,
            product,
            demand_forecasts.get(product.segment),
        )
        for product in current.products
    }


def forecast_product_sales_percentage_growth(
    reports: Iterable[CourierReport],
) -> Mapping[str, ForecastValue[Decimal]]:
    """Extrapolate latest product sales using the latest observed growth."""
    history = analyze_history(reports)
    if not history.reports:
        return {}

    current = history.reports[-1]
    names = _product_names(history.reports[-2:]) if len(history.reports) >= 2 else {
        product.name for product in current.products
    }
    if len(history.reports) < 2:
        return {
            name: _historical_unavailable(history)
            for name in sorted(names)
        }

    previous = history.reports[-2]
    return {
        name: _historical_growth_forecast(previous, current, name, history)
        for name in sorted(names)
    }


forecast_product_sales_with_market_share = forecast_product_sales_from_market_share


def _market_share_forecast(
    report: CourierReport,
    product: Product,
    segment_demand_forecast: ForecastValue[Decimal] | None,
) -> ForecastValue[Decimal]:
    snapshot = _snapshot(report, product)
    source_rounds = _source_rounds(
        segment_demand_forecast.source_rounds if segment_demand_forecast else (),
        report.round_number,
    )
    common = {
        "method": MARKET_SHARE_METHOD,
        "source_rounds": source_rounds,
        "required_history": 1,
        "available_history": 1,
        "assumptions": (SHARE_ASSUMPTION, NO_ROUNDING_ASSUMPTION),
    }
    if snapshot is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if snapshot.market_share_percent is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if segment_demand_forecast is None or segment_demand_forecast.value is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if segment_demand_forecast.status is not ForecastStatus.AVAILABLE:
        return ForecastValue(
            None,
            segment_demand_forecast.status,
            **common,
        )

    value = (
        segment_demand_forecast.value
        * snapshot.market_share_percent
        / Decimal("100")
    )
    return ForecastValue(value, ForecastStatus.AVAILABLE, **common)


def _historical_growth_forecast(
    previous: CourierReport,
    current: CourierReport,
    product_name: str,
    history,
) -> ForecastValue[Decimal]:
    previous_product = _product(previous, product_name)
    current_product = _product(current, product_name)
    common = {
        "method": HISTORICAL_GROWTH_METHOD,
        "source_rounds": (
            previous.round_number,
            current.round_number,
        ),
        "required_history": 2,
        "available_history": len(history.reports),
        "assumptions": (NO_ROUNDING_ASSUMPTION,),
    }
    if previous_product is None or current_product is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if previous_product.units_sold is None or current_product.units_sold is None:
        return ForecastValue(None, ForecastStatus.MISSING_INPUT, **common)
    if previous_product.units_sold == 0:
        return ForecastValue(None, ForecastStatus.ZERO_DENOMINATOR, **common)

    previous_units = Decimal(previous_product.units_sold)
    current_units = Decimal(current_product.units_sold)
    growth = (current_units - previous_units) / previous_units
    return ForecastValue(
        current_units * (Decimal("1") + growth),
        ForecastStatus.AVAILABLE,
        **common,
    )


def _historical_unavailable(history) -> ForecastValue[Decimal]:
    return ForecastValue(
        value=None,
        status=ForecastStatus.INSUFFICIENT_HISTORY,
        method=HISTORICAL_GROWTH_METHOD,
        source_rounds=tuple(report.round_number for report in history.reports),
        required_history=2,
        available_history=len(history.reports),
        assumptions=(NO_ROUNDING_ASSUMPTION,),
    )


def _snapshot(
    report: CourierReport,
    product: Product,
) -> SegmentProductSnapshot | None:
    for segment_report in report.segment_reports:
        if segment_report.segment is not product.segment:
            continue
        for snapshot in segment_report.products:
            if snapshot.product_name == product.name:
                return snapshot
    return None


def _product(report: CourierReport, name: str) -> Product | None:
    return next((product for product in report.products if product.name == name), None)


def _product_names(reports: tuple[CourierReport, ...]) -> set[str]:
    return {
        product.name
        for report in reports
        for product in report.products
    }


def _source_rounds(demand_rounds: tuple[int, ...], product_round: int) -> tuple[int, ...]:
    return tuple(dict.fromkeys((*demand_rounds, product_round)))
