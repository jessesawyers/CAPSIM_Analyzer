from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from .enums import Company, Segment
from .models import (
    BuyingCriterion,
    CompanyFinancials,
    CompanyMarketShare,
    CourierReport,
    MarketShareReport,
    PerceptualPosition,
    Product,
    ProductFinancials,
    ProductionRecord,
    SegmentProductSnapshot,
    SegmentReport,
)

SCHEMA_VERSION = "1.0"


def report_to_dict(report: CourierReport) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "report": _encode(report)}


def report_to_json(report: CourierReport, *, indent: int = 2) -> str:
    return json.dumps(report_to_dict(report), indent=indent, sort_keys=True)


def report_from_dict(payload: dict[str, Any]) -> CourierReport:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported or missing schema_version")
    raw = payload["report"]
    products = [_product(item) for item in raw.get("products", [])]
    segment_reports = [_segment_report(item) for item in raw.get("segment_reports", [])]
    market_share = _market_share(raw["market_share"]) if raw.get("market_share") else None
    financials = [_company_financials(item) for item in raw.get("company_financials", [])]
    production = [_production(item) for item in raw.get("production", [])]
    product_financials = [_product_financials(item) for item in raw.get("product_financials", [])]
    return CourierReport(
        simulation_id=raw["simulation_id"],
        round_number=raw["round_number"],
        report_date=date.fromisoformat(raw["report_date"]),
        companies=[Company(item) for item in raw["companies"]],
        segments=[Segment(item) for item in raw["segments"]],
        products=products,
        segment_reports=segment_reports,
        market_share=market_share,
        production=production,
        company_financials=financials,
        product_financials=product_financials,
    )


def report_from_json(payload: str) -> CourierReport:
    return report_from_dict(json.loads(payload))


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _encode(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(_encode(key)): _encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    return value


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _position(value: dict[str, Any]) -> PerceptualPosition:
    return PerceptualPosition(_decimal(value.get("performance")), _decimal(value.get("size")))


def _product(value: dict[str, Any]) -> Product:
    return Product(
        name=value["name"],
        company=Company(value["company"]),
        segment=Segment(value["segment"]),
        perceptual_position=_position(value.get("perceptual_position", {})),
        revision_date=date.fromisoformat(value["revision_date"]) if value.get("revision_date") else None,
        age_years=_decimal(value.get("age_years")),
        mtbf=value.get("mtbf"),
        list_price=_decimal(value.get("list_price")),
        material_cost=_decimal(value.get("material_cost")),
        labor_cost=_decimal(value.get("labor_cost")),
        contribution_margin_percent=_decimal(value.get("contribution_margin_percent")),
        units_sold=value.get("units_sold"),
        inventory_units=value.get("inventory_units"),
        capacity_next_round=value.get("capacity_next_round"),
        plant_utilization_percent=_decimal(value.get("plant_utilization_percent")),
        automation_level=_decimal(value.get("automation_level")),
    )


def _criterion(value: dict[str, Any]) -> BuyingCriterion:
    expectations = {
        key: _decimal(item) if isinstance(item, str) and _is_decimal(item) else item
        for key, item in value["expectations"].items()
    }
    return BuyingCriterion(value["rank"], value["criterion"], expectations, _decimal(value["importance_percent"]))


def _snapshot(value: dict[str, Any]) -> SegmentProductSnapshot:
    return SegmentProductSnapshot(
        product_name=value["product_name"],
        market_share_percent=_decimal(value.get("market_share_percent")),
        units_sold=value.get("units_sold"),
        revision_date=date.fromisoformat(value["revision_date"]) if value.get("revision_date") else None,
        perceptual_position=_position(value.get("perceptual_position", {})),
        list_price=_decimal(value.get("list_price")),
        mtbf=value.get("mtbf"),
        age_years=_decimal(value.get("age_years")),
        promotion_budget=_decimal(value.get("promotion_budget")),
        customer_awareness_percent=_decimal(value.get("customer_awareness_percent")),
        sales_budget=_decimal(value.get("sales_budget")),
        customer_accessibility_percent=_decimal(value.get("customer_accessibility_percent")),
        customer_survey_score=_decimal(value.get("customer_survey_score")),
    )


def _segment_report(value: dict[str, Any]) -> SegmentReport:
    return SegmentReport(
        segment=Segment(value["segment"]),
        total_industry_unit_demand=value["total_industry_unit_demand"],
        actual_industry_unit_sales=value["actual_industry_unit_sales"],
        percent_of_total_industry=_decimal(value["percent_of_total_industry"]),
        next_year_growth_rate_percent=_decimal(value["next_year_growth_rate_percent"]),
        buying_criteria=[_criterion(item) for item in value.get("buying_criteria", [])],
        products=[_snapshot(item) for item in value.get("products", [])],
    )


def _shares(values: list[dict[str, Any]]) -> list[CompanyMarketShare]:
    return [
        CompanyMarketShare(
            company=Company(item["company"]),
            segment_percentages={Segment(key): _decimal(value) for key, value in item["segment_percentages"].items()},
            total_percent=_decimal(item.get("total_percent")),
        )
        for item in values
    ]


def _market_share(value: dict[str, Any]) -> Any:
    return MarketShareReport(
        industry_unit_sales={Segment(key): item for key, item in value["industry_unit_sales"].items()},
        industry_units_demanded={Segment(key): item for key, item in value["industry_units_demanded"].items()},
        actual=_shares(value.get("actual", [])),
        potential=_shares(value.get("potential", [])),
    )


def _production(value: dict[str, Any]) -> ProductionRecord:
    return ProductionRecord(
        company=Company(value["company"]),
        product_name=value["product_name"],
        primary_segment=Segment(value["primary_segment"]) if value.get("primary_segment") else None,
        units_sold=value.get("units_sold"),
        inventory_units=value.get("inventory_units"),
        capacity_next_round=value.get("capacity_next_round"),
        plant_utilization_percent=_decimal(value.get("plant_utilization_percent")),
        second_shift_percent=_decimal(value.get("second_shift_percent")),
        overtime=value.get("overtime"),
        automation_level=_decimal(value.get("automation_level")),
    )


def _company_financials(value: dict[str, Any]) -> CompanyFinancials:
    return CompanyFinancials(
        company=Company(value["company"]),
        selected_statistics=_decode_scalars(value.get("selected_statistics", {})),
        stock_summary=_decode_scalars(value["stock_summary"]) if value.get("stock_summary") else None,
        cash_flow_statement=_decode_scalars(value.get("cash_flow_statement", {})),
        balance_sheet=_decode_scalars(value.get("balance_sheet", {})),
        income_statement=_decode_scalars(value.get("income_statement", {})),
    )


def _product_financials(value: dict[str, Any]) -> ProductFinancials:
    return ProductFinancials(
        company=Company(value["company"]),
        product_name=value["product_name"],
        values=_decode_scalars(value.get("values", {})),
    )


def _decode_scalars(values: dict[str, Any]) -> dict[str, Any]:
    return {key: _decimal(value) if isinstance(value, str) and _is_decimal(value) else value for key, value in values.items()}


def _is_decimal(value: str) -> bool:
    try:
        Decimal(value)
    except (ValueError, ArithmeticError):
        return False
    else:
        return True
