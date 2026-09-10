from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from ..enums import Company, Segment


@dataclass(frozen=True)
class SegmentMetrics:
    segment: Segment
    industry_unit_demand: int | None
    actual_industry_unit_sales: int | None
    demand_to_sales_gap: int | None
    percent_of_total_industry: Decimal | None
    next_year_growth_rate_percent: Decimal | None


@dataclass(frozen=True)
class IndustryTotals:
    industry_unit_demand: int | None
    actual_industry_unit_sales: int | None
    complete: bool


@dataclass(frozen=True)
class SegmentAnalysis:
    metrics: Mapping[Segment, SegmentMetrics]
    industry_totals: IndustryTotals
    rankings_by_demand: tuple[Segment, ...]
    rankings_by_growth: tuple[Segment, ...]


@dataclass(frozen=True)
class CompanyMarketShareMetrics:
    company: Company
    actual_by_segment: Mapping[Segment, Decimal | None]
    potential_by_segment: Mapping[Segment, Decimal | None]
    potential_minus_actual_by_segment: Mapping[Segment, Decimal | None]
    actual_total_percent: Decimal | None
    potential_total_percent: Decimal | None


@dataclass(frozen=True)
class SegmentShareReconciliation:
    segment: Segment
    actual_total_percent: Decimal | None
    potential_total_percent: Decimal | None
    actual_difference_from_100: Decimal | None
    potential_difference_from_100: Decimal | None
    actual_complete: bool
    potential_complete: bool


@dataclass(frozen=True)
class MarketShareAnalysis:
    companies: Mapping[Company, CompanyMarketShareMetrics]
    actual_leaders: Mapping[Segment, Company | None]
    potential_leaders: Mapping[Segment, Company | None]
    actual_rankings: Mapping[Segment, tuple[Company, ...]]
    potential_rankings: Mapping[Segment, tuple[Company, ...]]
    reconciliation: Mapping[Segment, SegmentShareReconciliation]
    industry_unit_sales: Mapping[Segment, int]
    industry_units_demanded: Mapping[Segment, int]


@dataclass(frozen=True)
class ProductMetrics:
    product_name: str
    company: Company
    segment: Segment
    performance_difference: Decimal | None
    size_difference: Decimal | None
    perceptual_distance: Decimal | None
    price_difference: Decimal | None
    price_in_expected_range: bool | None
    mtbf_difference: int | None
    mtbf_in_expected_range: bool | None
    age_difference: Decimal | None
    units_sold: int | None
    inventory_units: int | None
    inventory_to_sales_ratio: Decimal | None
    market_share_percent: Decimal | None
    contribution_margin_amount: Decimal | None
    contribution_margin_percent: Decimal | None
    material_cost: Decimal | None
    labor_cost: Decimal | None
    customer_awareness_percent: Decimal | None
    customer_accessibility_percent: Decimal | None
    customer_survey_score: Decimal | None
    plant_utilization_percent: Decimal | None


@dataclass(frozen=True)
class ProductConsistencyCheck:
    product_name: str
    production_record_found: bool
    segment_snapshot_found: bool
    company_consistent: bool | None
    segment_consistent: bool | None
    units_sold_consistent: bool | None


@dataclass(frozen=True)
class ProductAnalysis:
    products: Mapping[str, ProductMetrics]
    rankings_by_segment: Mapping[Segment, Mapping[str, tuple[str, ...]]]
    consistency_checks: Mapping[str, ProductConsistencyCheck]


@dataclass(frozen=True)
class ProductionMetrics:
    product_name: str
    company: Company
    segment: Segment | None
    units_sold: int | None
    inventory_units: int | None
    capacity_next_round: int | None
    plant_utilization_percent: Decimal | None
    units_sold_as_capacity_percent: Decimal | None
    capacity_headroom: int | None
    second_shift_percent: Decimal | None
    # Courier's combined "2nd Shift & Overtime" percentage.
    overtime: Decimal | None
    inventory_to_sales_ratio: Decimal | None


@dataclass(frozen=True)
class ProductionSummary:
    units_sold: int | None
    inventory_units: int | None
    capacity_next_round: int | None
    capacity_headroom: int | None
    complete_units: bool
    complete_inventory: bool
    complete_capacity: bool


@dataclass(frozen=True)
class ProductionConsistencyCheck:
    product_name: str
    product_found: bool
    segment_snapshot_found: bool
    company_consistent: bool | None
    segment_consistent: bool | None
    units_sold_consistent: bool | None


@dataclass(frozen=True)
class ProductionAnalysis:
    products: Mapping[str, ProductionMetrics]
    rankings_by_utilization: tuple[str, ...]
    company_summaries: Mapping[Company, ProductionSummary]
    segment_summaries: Mapping[Segment, ProductionSummary]
    consistency_checks: Mapping[str, ProductionConsistencyCheck]


@dataclass(frozen=True)
class FinancialMetrics:
    company: Company
    financials_available: bool
    revenue: Decimal | None
    direct_labor: Decimal | None
    direct_material: Decimal | None
    contribution_margin: Decimal | None
    contribution_margin_percent: Decimal | None
    ebit: Decimal | None
    ebit_margin: Decimal | None
    net_profit: Decimal | None
    net_profit_margin: Decimal | None
    cash: Decimal | None
    accounts_receivable: Decimal | None
    inventory: Decimal | None
    total_assets: Decimal | None
    accounts_payable: Decimal | None
    long_term_debt: Decimal | None
    common_stock: Decimal | None
    retained_earnings: Decimal | None
    current_debt: Decimal | None
    total_liabilities: Decimal | None
    total_equity: Decimal | None
    total_debt: Decimal | None
    debt_to_equity: Decimal | None
    balance_sheet_difference: Decimal | None
    balance_sheet_consistent: bool | None
    cash_flow: Mapping[str, Decimal | None]


@dataclass(frozen=True)
class FinancialAnalysis:
    companies: Mapping[Company, FinancialMetrics]
    available_companies: tuple[Company, ...]
    incomplete_companies: tuple[Company, ...]
