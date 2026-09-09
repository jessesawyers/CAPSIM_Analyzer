from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from .enums import Company, Segment


Scalar = Decimal | int | str | bool | None


@dataclass(frozen=True)
class PerceptualPosition:
    performance: Decimal | None = None
    size: Decimal | None = None


@dataclass(frozen=True)
class BuyingCriterion:
    rank: int
    criterion: str
    expectations: dict[str, Scalar]
    importance_percent: Decimal


@dataclass(frozen=True)
class SegmentProductSnapshot:
    product_name: str
    market_share_percent: Decimal | None = None
    units_sold: int | None = None
    revision_date: date | None = None
    perceptual_position: PerceptualPosition = field(default_factory=PerceptualPosition)
    list_price: Decimal | None = None
    mtbf: int | None = None
    age_years: Decimal | None = None
    promotion_budget: Decimal | None = None
    customer_awareness_percent: Decimal | None = None
    sales_budget: Decimal | None = None
    customer_accessibility_percent: Decimal | None = None
    customer_survey_score: Decimal | None = None


@dataclass(frozen=True)
class SegmentReport:
    segment: Segment
    total_industry_unit_demand: int
    actual_industry_unit_sales: int
    percent_of_total_industry: Decimal
    next_year_growth_rate_percent: Decimal
    buying_criteria: list[BuyingCriterion] = field(default_factory=list)
    products: list[SegmentProductSnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class Product:
    name: str
    company: Company
    segment: Segment
    perceptual_position: PerceptualPosition = field(default_factory=PerceptualPosition)
    revision_date: date | None = None
    age_years: Decimal | None = None
    mtbf: int | None = None
    list_price: Decimal | None = None
    material_cost: Decimal | None = None
    labor_cost: Decimal | None = None
    contribution_margin_percent: Decimal | None = None
    units_sold: int | None = None
    inventory_units: int | None = None
    capacity_next_round: int | None = None
    plant_utilization_percent: Decimal | None = None
    automation_level: Decimal | None = None


@dataclass(frozen=True)
class CompanyMarketShare:
    company: Company
    segment_percentages: dict[Segment, Decimal | None]
    total_percent: Decimal | None = None


@dataclass(frozen=True)
class MarketShareReport:
    industry_unit_sales: dict[Segment, int]
    industry_units_demanded: dict[Segment, int]
    actual: list[CompanyMarketShare] = field(default_factory=list)
    potential: list[CompanyMarketShare] = field(default_factory=list)


@dataclass(frozen=True)
class ProductionRecord:
    company: Company
    product_name: str
    primary_segment: Segment | None = None
    units_sold: int | None = None
    inventory_units: int | None = None
    capacity_next_round: int | None = None
    plant_utilization_percent: Decimal | None = None
    second_shift_percent: Decimal | None = None
    # Courier reports one combined "2nd Shift & Overtime" percentage,
    # not a standalone overtime percentage.
    overtime: Decimal | None = None
    automation_level: Decimal | None = None


@dataclass(frozen=True)
class BondRecord:
    series: str
    face_value: Decimal | None = None
    yield_percent: Decimal | None = None
    close_price: Decimal | None = None
    rating: str | None = None


@dataclass(frozen=True)
class CompanyFinancials:
    company: Company
    selected_statistics: dict[str, Scalar] = field(default_factory=dict)
    stock_summary: dict[str, Scalar] | None = None
    bond_summary: list[BondRecord] | None = None
    cash_flow_statement: dict[str, Decimal | None] = field(default_factory=dict)
    balance_sheet: dict[str, Decimal | None] = field(default_factory=dict)
    income_statement: dict[str, Decimal | None] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductFinancials:
    company: Company
    product_name: str
    values: dict[str, Decimal | None] = field(default_factory=dict)


@dataclass(frozen=True)
class CourierReport:
    simulation_id: str
    round_number: int
    report_date: date
    companies: list[Company]
    segments: list[Segment]
    products: list[Product] = field(default_factory=list)
    segment_reports: list[SegmentReport] = field(default_factory=list)
    market_share: MarketShareReport | None = None
    production: list[ProductionRecord] = field(default_factory=list)
    company_financials: list[CompanyFinancials] = field(default_factory=list)
    product_financials: list[ProductFinancials] = field(default_factory=list)

    def product_by_name(self, name: str) -> Product:
        return next(product for product in self.products if product.name == name)
