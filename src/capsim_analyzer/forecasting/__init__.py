"""Pure forecasting functions over structured Courier reports."""

from .segments import (
    forecast_segment_demand_absolute_change,
    forecast_segment_demand_percentage_growth,
    forecast_segment_demand_with_courier_growth,
)
from .products import (
    forecast_product_sales_from_market_share,
    forecast_product_sales_percentage_growth,
    forecast_product_sales_with_market_share,
)
from .types import ForecastStatus, ForecastValue

__all__ = [
    "ForecastStatus",
    "ForecastValue",
    "forecast_product_sales_from_market_share",
    "forecast_product_sales_percentage_growth",
    "forecast_product_sales_with_market_share",
    "forecast_segment_demand_absolute_change",
    "forecast_segment_demand_percentage_growth",
    "forecast_segment_demand_with_courier_growth",
]
