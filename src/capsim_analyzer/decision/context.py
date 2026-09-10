from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from ..analysis.history import HistoryAnalysis
from ..analysis.types import (
    FinancialAnalysis,
    MarketShareAnalysis,
    ProductAnalysis,
    ProductionAnalysis,
    SegmentAnalysis,
)
from ..enums import Segment
from ..forecasting.types import ForecastValue
from ..models import CourierReport


@dataclass(frozen=True)
class DecisionContext:
    report: CourierReport
    segment_analysis: SegmentAnalysis | None = None
    market_share_analysis: MarketShareAnalysis | None = None
    product_analysis: ProductAnalysis | None = None
    production_analysis: ProductionAnalysis | None = None
    financial_analysis: FinancialAnalysis | None = None
    history_analysis: HistoryAnalysis | None = None
    segment_demand_forecasts: Mapping[
        Segment, ForecastValue[Decimal]
    ] = field(default_factory=dict)
    product_sales_forecasts: Mapping[
        str, ForecastValue[Decimal]
    ] = field(default_factory=dict)
    inventory_forecasts: Mapping[
        str, ForecastValue[Decimal]
    ] = field(default_factory=dict)
