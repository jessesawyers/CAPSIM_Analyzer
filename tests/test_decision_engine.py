from datetime import date
from decimal import Decimal
from dataclasses import replace
from pathlib import Path

from capsim_analyzer.analysis.finance import analyze_financials
from capsim_analyzer.analysis.market_share import analyze_market_share
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.engine import evaluate_decisions
from capsim_analyzer.decision.types import DecisionReport, DecisionStatus
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.types import ForecastStatus, ForecastValue
from capsim_analyzer.models import (
    BuyingCriterion,
    CompanyFinancials,
    CompanyMarketShare,
    CourierReport,
    MarketShareReport,
    PerceptualPosition,
    Product,
    ProductionRecord,
    SegmentProductSnapshot,
    SegmentReport,
)
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "CourierC165051R0TBK0CA.PDF"


def _context() -> DecisionContext:
    products = [
        Product(
            "Able",
            Company.ANDREWS,
            Segment.TRADITIONAL,
            PerceptualPosition(Decimal("5"), Decimal("15")),
            list_price=Decimal("25"),
            mtbf=16000,
            age_years=Decimal("2"),
            units_sold=100,
            inventory_units=20,
            capacity_next_round=150,
        ),
        Product(
            "Baker",
            Company.CHESTER,
            Segment.TRADITIONAL,
            PerceptualPosition(Decimal("5"), Decimal("15")),
            list_price=Decimal("25"),
            mtbf=16000,
            age_years=Decimal("2"),
            units_sold=90,
            inventory_units=20,
            capacity_next_round=150,
        ),
    ]
    criteria = [
        BuyingCriterion(
            1,
            "Ideal Position",
            {"performance": Decimal("5"), "size": Decimal("15")},
            Decimal("50"),
        ),
        BuyingCriterion(
            2,
            "Price",
            {"minimum": Decimal("20"), "maximum": Decimal("30")},
            Decimal("20"),
        ),
        BuyingCriterion(
            3,
            "Reliability",
            {"minimum": 14000, "maximum": 19000},
            Decimal("20"),
        ),
        BuyingCriterion(
            4,
            "Age",
            {"ideal_age_years": Decimal("2")},
            Decimal("10"),
        ),
    ]
    segment_report = SegmentReport(
        Segment.TRADITIONAL,
        100,
        100,
        Decimal("50"),
        Decimal("10"),
        buying_criteria=criteria,
        products=[
            SegmentProductSnapshot(
                "Able",
                market_share_percent=Decimal("10"),
                promotion_budget=Decimal("100"),
                customer_awareness_percent=Decimal("70"),
                sales_budget=Decimal("100"),
                customer_accessibility_percent=Decimal("60"),
                customer_survey_score=Decimal("30"),
            ),
            SegmentProductSnapshot(
                "Baker",
                market_share_percent=Decimal("8"),
                promotion_budget=Decimal("100"),
                customer_awareness_percent=Decimal("70"),
                sales_budget=Decimal("100"),
                customer_accessibility_percent=Decimal("60"),
                customer_survey_score=Decimal("30"),
            ),
        ],
    )
    report = CourierReport(
        "SIM01",
        1,
        date(2027, 12, 31),
        [Company.ANDREWS, Company.CHESTER],
        [Segment.TRADITIONAL],
        products=products,
        segment_reports=[segment_report],
        market_share=MarketShareReport(
            industry_unit_sales={},
            industry_units_demanded={},
            actual=[
                CompanyMarketShare(
                    Company.ANDREWS,
                    {Segment.TRADITIONAL: Decimal("10")},
                    Decimal("10"),
                ),
                CompanyMarketShare(
                    Company.CHESTER,
                    {Segment.TRADITIONAL: Decimal("8")},
                    Decimal("8"),
                ),
            ],
            potential=[
                CompanyMarketShare(
                    Company.ANDREWS,
                    {Segment.TRADITIONAL: Decimal("15")},
                    Decimal("15"),
                ),
                CompanyMarketShare(
                    Company.CHESTER,
                    {Segment.TRADITIONAL: Decimal("12")},
                    Decimal("12"),
                ),
            ],
        ),
        production=[
            ProductionRecord(
                Company.ANDREWS, "Able", Segment.TRADITIONAL, 100, 20, 150,
                Decimal("75"), Decimal("10"), Decimal("10"),
            ),
            ProductionRecord(
                Company.CHESTER, "Baker", Segment.TRADITIONAL, 90, 20, 150,
                Decimal("60"), Decimal("0"), Decimal("0"),
            ),
        ],
        company_financials=[
            CompanyFinancials(
                Company.ANDREWS,
                income_statement={
                    "sales": Decimal("200"),
                    "contribution_margin": Decimal("80"),
                    "net_profit": Decimal("20"),
                },
                balance_sheet={
                    "cash": Decimal("100"),
                    "current_debt": Decimal("10"),
                    "long_term_debt": Decimal("40"),
                    "total_equity": Decimal("100"),
                    "total_assets": Decimal("150"),
                    "total_liabilities": Decimal("50"),
                },
            ),
        ],
    )
    return DecisionContext(
        report=report,
        financial_analysis=analyze_financials(report),
        product_sales_forecasts={
            "Able": ForecastValue(
                Decimal("110"),
                ForecastStatus.AVAILABLE,
                "test",
                (1,),
                1,
                1,
                ("explicit test forecast",),
            ),
            "Baker": ForecastValue(
                Decimal("95"),
                ForecastStatus.AVAILABLE,
                "test",
                (1,),
                1,
                1,
                ("explicit test forecast",),
            ),
        },
    )


def test_evaluate_decisions_returns_decision_report():
    assert isinstance(evaluate_decisions(_context()), DecisionReport)


def test_engine_orchestrates_all_rule_groups_for_each_product_and_company():
    result = evaluate_decisions(_context())

    representative_rules = {
        ("product_positioning", "product"),
        ("forecast_sales_vs_current", "product"),
        ("promotion_awareness", "product"),
        ("cash_position", "company"),
        ("capacity_investment", "product"),
        ("automation_investment", "product"),
        ("plant_equipment_evidence", "company"),
        ("investment_evidence_completeness", "product"),
    }
    for rule_id, entity_type in representative_rules:
        ids = {
            rule.entity_id
            for rule in result.observations
            if rule.rule_id == rule_id and rule.entity_type == entity_type
        }
        expected = {"Able", "Baker"} if entity_type == "product" else {"Andrews", "Chester"}
        assert expected <= ids


def test_engine_preserves_results_recommendations_observations_and_evidence():
    result = evaluate_decisions(_context())

    assert result.observations
    assert result.recommendations == tuple(
        rule.recommendation
        for rule in result.observations
        if rule.recommendation is not None
    )
    assert any(rule.observations for rule in result.observations)
    assert any(rule.evidence for rule in result.observations)


def test_engine_preserves_blocked_results_and_data_quality_evidence():
    result = evaluate_decisions(_context())
    blocked_statuses = {
        DecisionStatus.MISSING_INPUT,
        DecisionStatus.INSUFFICIENT_DATA,
        DecisionStatus.CONFLICTING_DATA,
        DecisionStatus.UNSUPPORTED,
        DecisionStatus.ASSUMPTION_REQUIRED,
        DecisionStatus.ZERO_DENOMINATOR,
    }

    assert result.blocked_rules
    assert all(rule.status in blocked_statuses for rule in result.blocked_rules)
    assert result.data_quality_issues == tuple(
        evidence
        for rule in result.blocked_rules
        for evidence in rule.evidence
    )
    assert result.status is not DecisionStatus.AVAILABLE


def test_engine_orchestrates_investment_rules_for_each_product():
    result = evaluate_decisions(_context())

    for rule_id in ("capacity_investment", "automation_investment"):
        product_ids = {
            rule.entity_id
            for rule in result.observations
            if rule.rule_id == rule_id
        }
        assert product_ids == {"Able", "Baker"}


def test_engine_orchestrates_investment_rules_for_each_company():
    result = evaluate_decisions(_context())

    company_ids = {
        rule.entity_id
        for rule in result.observations
        if rule.rule_id == "plant_equipment_evidence"
    }
    assert company_ids == {"Andrews", "Chester"}


def test_engine_orchestrates_completeness_for_each_product_company_combination():
    context = _context()
    result = evaluate_decisions(context)
    completeness = [
        rule
        for rule in result.observations
        if rule.rule_id == "investment_evidence_completeness"
    ]

    assert len(completeness) == len(context.report.products) * len(
        context.report.companies
    )
    assert {
        rule.entity_id
        for rule in completeness
    } == {product.name for product in context.report.products}
    assert all(
        evidence.entity_type == "product"
        and evidence.entity_id == rule.entity_id
        for rule in completeness
        for evidence in rule.evidence
    )


def test_engine_preserves_investment_status_and_evidence():
    result = evaluate_decisions(_context())
    investment_rule_ids = {
        "capacity_investment",
        "automation_investment",
        "plant_equipment_evidence",
        "investment_evidence_completeness",
    }
    investment_results = [
        rule for rule in result.observations if rule.rule_id in investment_rule_ids
    ]

    assert investment_results
    assert all(rule.evidence for rule in investment_results)
    assert all(
        rule.status is DecisionStatus.MISSING_INPUT
        for rule in investment_results
        if rule.rule_id in {"capacity_investment", "automation_investment"}
    )


def test_engine_wires_market_share_potential_to_product_and_marketing_rules():
    context = _context()
    context = replace(
        context,
        market_share_analysis=analyze_market_share(context.report),
    )
    result = evaluate_decisions(context)

    product_gap = next(
        rule
        for rule in result.observations
        if rule.rule_id == "product_market_share_gap"
        and rule.entity_id == "Able"
    )
    marketing_gap = next(
        rule
        for rule in result.observations
        if rule.rule_id == "marketing_market_share_gap"
        and rule.entity_id == "Able"
    )

    product_evidence = {
        evidence.metric: evidence.value for evidence in product_gap.evidence
    }
    marketing_evidence = {
        evidence.metric: evidence.value for evidence in marketing_gap.evidence
    }
    assert product_gap.status is DecisionStatus.AVAILABLE
    assert marketing_gap.status is DecisionStatus.AVAILABLE
    assert product_evidence["potential_market_share"] == Decimal("15")
    assert marketing_evidence["potential_market_share"] == Decimal("15")


def test_engine_preserves_missing_market_share_potential_without_analysis():
    result = evaluate_decisions(_context())

    for rule_id in ("product_market_share_gap", "marketing_market_share_gap"):
        rule = next(
            rule
            for rule in result.observations
            if rule.rule_id == rule_id and rule.entity_id == "Able"
        )
        evidence = {
            item.metric: item.value for item in rule.evidence
        }
        assert rule.status is DecisionStatus.MISSING_INPUT
        assert evidence["potential_market_share"] is None


def test_engine_does_not_invent_investment_recommendations():
    result = evaluate_decisions(_context())
    investment_rule_ids = {
        "capacity_investment",
        "automation_investment",
        "plant_equipment_evidence",
        "investment_evidence_completeness",
    }

    assert all(
        rule.recommendation is None
        for rule in result.observations
        if rule.rule_id in investment_rule_ids
    )
    assert all(
        recommendation.category.name != "INVESTMENT"
        for recommendation in result.recommendations
    )


def test_round_0_integration_returns_known_product_and_company_observations():
    report = parse_courier_pdf(PDF_PATH)
    forecasts = {
        product.name: ForecastValue(
            Decimal(str(product.units_sold or 0)),
            ForecastStatus.AVAILABLE,
            "integration-test",
            (report.round_number,),
            1,
            1,
            ("explicit integration-test forecast",),
        )
        for product in report.products
    }
    result = evaluate_decisions(
        DecisionContext(
            report=report,
            financial_analysis=analyze_financials(report),
            market_share_analysis=analyze_market_share(report),
            product_sales_forecasts=forecasts,
        )
    )

    assert isinstance(result, DecisionReport)
    assert any(rule.entity_id == "Able" for rule in result.observations)
    assert any(rule.entity_id == Company.BALDWIN.value for rule in result.observations)
    assert any(
        rule.rule_id == "capacity_investment" and rule.entity_id == "Able"
        for rule in result.observations
    )
    assert any(
        rule.rule_id == "plant_equipment_evidence"
        and rule.entity_id == Company.BALDWIN.value
        for rule in result.observations
    )
    able = report.product_by_name("Able")
    potential = (
        analyze_market_share(report)
        .companies[able.company]
        .potential_by_segment[able.segment]
    )
    product_gap = next(
        rule
        for rule in result.observations
        if rule.rule_id == "product_market_share_gap"
        and rule.entity_id == able.name
    )
    evidence = {
        item.metric: item.value for item in product_gap.evidence
    }
    assert evidence["potential_market_share"] == potential
