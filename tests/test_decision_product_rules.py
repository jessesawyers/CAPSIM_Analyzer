from datetime import date
from decimal import Decimal
from dataclasses import replace

from capsim_analyzer.analysis.history import analyze_history
from capsim_analyzer.analysis.products import analyze_products
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.product_rules import (
    evaluate_product_age,
    evaluate_product_market_share_gap,
    evaluate_product_market_share_history,
    evaluate_product_mtbf,
    evaluate_product_positioning,
    evaluate_product_price,
    evaluate_product_sales_forecast,
)
from capsim_analyzer.decision.types import DecisionStatus
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.types import ForecastStatus, ForecastValue
from capsim_analyzer.models import (
    BuyingCriterion,
    CourierReport,
    PerceptualPosition,
    Product,
    SegmentProductSnapshot,
    SegmentReport,
)


def _product(**kwargs):
    values = {
        "name": "Able",
        "company": Company.ANDREWS,
        "segment": Segment.TRADITIONAL,
        "perceptual_position": PerceptualPosition(Decimal("5"), Decimal("15")),
        "list_price": Decimal("25"),
        "mtbf": 16000,
        "age_years": Decimal("2"),
        "units_sold": 100,
    }
    values.update(kwargs)
    return Product(**values)


def _report(product=None, *, round_number=0, share=None, demand=100):
    product = product or _product()
    criteria = [
        BuyingCriterion(1, "Ideal Position", {"performance": Decimal("5"), "size": Decimal("15")}, Decimal("50")),
        BuyingCriterion(2, "Price", {"minimum": Decimal("20"), "maximum": Decimal("30")}, Decimal("20")),
        BuyingCriterion(3, "Reliability", {"minimum": 14000, "maximum": 19000}, Decimal("20")),
        BuyingCriterion(4, "Age", {"ideal_age_years": Decimal("2")}, Decimal("10")),
    ]
    snapshot = SegmentProductSnapshot(product.name, market_share_percent=share)
    segment = SegmentReport(
        Segment.TRADITIONAL,
        demand,
        demand,
        Decimal("100"),
        Decimal("10"),
        buying_criteria=criteria,
        products=[snapshot],
    )
    return CourierReport(
        "SIM01",
        round_number,
        date(2026 + round_number, 12, 31),
        list(Company),
        list(Segment),
        products=[product],
        segment_reports=[segment],
    )


def _context(report, forecast=None):
    forecasts = {} if forecast is None else {"Able": forecast}
    return DecisionContext(report=report, product_sales_forecasts=forecasts)


def test_positioning_rule_reports_match_and_difference():
    matching = evaluate_product_positioning(_context(_report()), "Able")
    different = evaluate_product_positioning(
        _context(_report(_product(perceptual_position=PerceptualPosition(Decimal("6"), Decimal("14"))))),
        "Able",
    )

    assert matching.status is DecisionStatus.AVAILABLE
    assert "matches" in matching.observations[0]
    assert different.recommendation is not None
    assert "reviewed" in different.recommendation.action
    assert different.evidence[1].value == Decimal("6")


def test_price_mtbf_and_age_rules_use_reported_expectations():
    price = evaluate_product_price(_context(_report(_product(list_price=Decimal("35")))), "Able")
    mtbf = evaluate_product_mtbf(_context(_report(_product(mtbf=12000))), "Able")
    age = evaluate_product_age(_context(_report(_product(age_years=Decimal("3")))), "Able")

    assert "above" in price.observations[0]
    assert "below" in mtbf.observations[0]
    assert "increase" in age.observations[0]
    assert price.recommendation is not None


def test_rules_report_missing_inputs():
    missing = _context(_report(_product(list_price=None, mtbf=None, age_years=None)))
    assert evaluate_product_price(missing, "Able").status is DecisionStatus.MISSING_INPUT
    assert evaluate_product_mtbf(missing, "Able").status is DecisionStatus.MISSING_INPUT
    assert evaluate_product_age(missing, "Able").status is DecisionStatus.MISSING_INPUT
    assert evaluate_product_positioning(_context(_report(_product(perceptual_position=PerceptualPosition()))), "Able").status is DecisionStatus.MISSING_INPUT


def test_market_share_gap_requires_comparable_potential_value():
    context = _context(_report(share=Decimal("10")))
    missing = evaluate_product_market_share_gap(context, "Able")
    gap = evaluate_product_market_share_gap(
        context,
        "Able",
        actual=Decimal("10"),
        potential=Decimal("15"),
    )

    assert missing.status is DecisionStatus.MISSING_INPUT
    assert gap.status is DecisionStatus.AVAILABLE
    assert gap.recommendation is not None
    assert gap.evidence[1].value == Decimal("15")


def test_market_share_gap_falls_back_to_snapshot_when_analysis_value_is_missing():
    report = _report(share=Decimal("10"))
    analysis = analyze_products(report)
    metrics = replace(analysis.products["Able"], market_share_percent=None)
    context = DecisionContext(
        report=report,
        product_analysis=replace(analysis, products={"Able": metrics}),
    )

    result = evaluate_product_market_share_gap(
        context,
        "Able",
        potential=Decimal("15"),
    )

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("10")


def test_market_share_gap_preserves_non_none_analysis_precedence():
    report = _report(share=Decimal("10"))
    analysis = analyze_products(report)
    metrics = replace(analysis.products["Able"], market_share_percent=Decimal("12"))
    context = DecisionContext(
        report=report,
        product_analysis=replace(analysis, products={"Able": metrics}),
    )

    result = evaluate_product_market_share_gap(
        context,
        "Able",
        potential=Decimal("15"),
    )

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("12")


def test_historical_market_share_direction_and_insufficient_history():
    first = _report(share=Decimal("10"), round_number=0)
    second = _report(share=Decimal("12"), round_number=1)
    context = _context(second)
    context = DecisionContext(report=second, history_analysis=analyze_history([second, first]))

    result = evaluate_product_market_share_history(context, "Able")
    assert result.status is DecisionStatus.AVAILABLE
    assert "increased" in result.observations[0]

    assert evaluate_product_market_share_history(_context(second), "Able").status is DecisionStatus.INSUFFICIENT_DATA


def test_sales_forecast_rule_propagates_forecast_and_direction():
    forecast = ForecastValue(
        Decimal("125"),
        ForecastStatus.AVAILABLE,
        "test_method",
        (0,),
        1,
        1,
        ("explicit test assumption",),
    )
    result = evaluate_product_sales_forecast(_context(_report(), forecast), "Able")

    assert result.status is DecisionStatus.AVAILABLE
    assert "increase" in result.observations[0]
    assert result.evidence[2].value == "test_method"
    assert result.assumptions == ("explicit test assumption",)
    assert result.recommendation is not None


def test_sales_forecast_recommends_for_increase_and_decrease_but_not_no_change():
    increase = evaluate_product_sales_forecast(
        _context(_report(_product(units_sold=100)), ForecastValue(
            Decimal("125"),
            ForecastStatus.AVAILABLE,
            "test_method",
            (0,),
            1,
            1,
            (),
        )),
        "Able",
    )
    decrease = evaluate_product_sales_forecast(
        _context(_report(_product(units_sold=100)), ForecastValue(
            Decimal("75"),
            ForecastStatus.AVAILABLE,
            "test_method",
            (0,),
            1,
            1,
            (),
        )),
        "Able",
    )
    no_change = evaluate_product_sales_forecast(
        _context(_report(_product(units_sold=100)), ForecastValue(
            Decimal("100"),
            ForecastStatus.AVAILABLE,
            "test_method",
            (0,),
            1,
            1,
            (),
        )),
        "Able",
    )

    assert increase.recommendation is not None
    assert decrease.recommendation is not None
    assert no_change.recommendation is None
    assert no_change.observations


def test_product_rules_are_deterministic_and_do_not_mutate_report():
    context = _context(_report())
    first = evaluate_product_price(context, "Able")
    second = evaluate_product_price(context, "Able")

    assert first == second
    assert context.report.products[0].name == "Able"
