from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.investment_rules import (
    evaluate_automation_investment,
    evaluate_capacity_investment,
    evaluate_investment_evidence_completeness,
    evaluate_plant_equipment_evidence,
)
from capsim_analyzer.decision.types import DecisionStatus
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import (
    CompanyFinancials,
    CourierReport,
    Product,
    ProductionRecord,
)
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _context(*, capacity=150, automation=Decimal("5"), financials=True):
    report = CourierReport(
        "SIM01",
        1,
        date(2027, 12, 31),
        [Company.ANDREWS, Company.BALDWIN],
        [Segment.TRADITIONAL],
        products=[
            Product(
                "Able",
                Company.ANDREWS,
                Segment.TRADITIONAL,
                capacity_next_round=capacity,
                automation_level=automation,
            )
        ],
        production=[
            ProductionRecord(
                Company.ANDREWS,
                "Able",
                Segment.TRADITIONAL,
                capacity_next_round=capacity,
                automation_level=automation,
            )
        ],
        company_financials=(
            [
                CompanyFinancials(
                    Company.BALDWIN,
                    balance_sheet={
                        "plant_and_equipment": Decimal("100"),
                        "accumulated_depreciation": Decimal("20"),
                    },
                    income_statement={"depreciation": Decimal("10")},
                )
            ]
            if financials
            else []
        ),
    )
    return DecisionContext(report=report)


def test_capacity_preserves_reported_value_without_self_comparison():
    result = evaluate_capacity_investment(_context(), "Able")

    evidence = {item.metric: item.value for item in result.evidence}
    assert result.status is DecisionStatus.MISSING_INPUT
    assert evidence["current_capacity"] is None
    assert evidence["next_round_capacity"] == 150
    assert result.recommendation is None
    assert "no separate current-capacity" in result.observations[0]


def test_capacity_missing_product_is_explicit():
    result = evaluate_capacity_investment(_context(), "Unknown")

    assert result.entity_id == "Unknown"
    assert result.status is DecisionStatus.MISSING_INPUT
    assert result.recommendation is None


def test_automation_preserves_reported_value_without_self_comparison():
    result = evaluate_automation_investment(_context(), "Able")

    evidence = {item.metric: item.value for item in result.evidence}
    assert result.status is DecisionStatus.MISSING_INPUT
    assert evidence["current_automation"] is None
    assert evidence["next_round_automation"] == Decimal("5")
    assert result.recommendation is None
    assert "separate current and next-round" in result.observations[0]


def test_plant_equipment_evidence_is_available_without_recommendation():
    result = evaluate_plant_equipment_evidence(_context(), Company.BALDWIN)

    evidence = {item.metric: item.value for item in result.evidence}
    assert result.status is DecisionStatus.AVAILABLE
    assert evidence["plant_and_equipment"] == Decimal("100")
    assert evidence["accumulated_depreciation"] == Decimal("20")
    assert evidence["depreciation"] == Decimal("10")
    assert result.recommendation is None


def test_plant_equipment_missing_evidence_is_explicit():
    result = evaluate_plant_equipment_evidence(
        _context(financials=False),
        Company.BALDWIN,
    )

    assert result.status is DecisionStatus.MISSING_INPUT
    assert result.recommendation is None


def test_investment_evidence_completeness_reports_missing_financial_fields():
    result = evaluate_investment_evidence_completeness(
        _context(financials=False),
        "Able",
        Company.BALDWIN,
    )

    assert result.status is DecisionStatus.MISSING_INPUT
    assert "plant_and_equipment" in result.observations[0]
    assert "accumulated_depreciation" in result.observations[0]
    assert "depreciation" in result.observations[0]


def test_investment_evidence_completeness_accepts_all_captured_fields():
    result = evaluate_investment_evidence_completeness(
        _context(),
        "Able",
        Company.BALDWIN,
    )

    assert result.status is DecisionStatus.AVAILABLE
    assert "complete" in result.observations[0]


def test_round_0_integration_uses_actual_reported_evidence():
    report = parse_courier_pdf(PDF_PATH)
    context = DecisionContext(report=report)

    product = report.product_by_name("Able")
    capacity = evaluate_capacity_investment(context, "Able")
    automation = evaluate_automation_investment(context, "Able")
    plant = evaluate_plant_equipment_evidence(context, Company.BALDWIN)

    capacity_evidence = {item.metric: item.value for item in capacity.evidence}
    automation_evidence = {item.metric: item.value for item in automation.evidence}
    plant_evidence = {item.metric: item.value for item in plant.evidence}

    assert capacity_evidence["next_round_capacity"] == product.capacity_next_round
    assert automation_evidence["next_round_automation"] == product.automation_level
    assert plant_evidence["plant_and_equipment"] == Decimal("113800")
    assert plant_evidence["accumulated_depreciation"] == Decimal("-37933")
