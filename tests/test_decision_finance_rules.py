from datetime import date
from decimal import Decimal
from dataclasses import replace
from pathlib import Path

from capsim_analyzer.analysis.finance import analyze_financials
from capsim_analyzer.analysis.history import analyze_history
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.finance_rules import (
    evaluate_cash_position,
    evaluate_debt_leverage,
    evaluate_financial_evidence_completeness,
    evaluate_financial_history,
    evaluate_profitability,
    evaluate_sales_contribution_margin,
)
from capsim_analyzer.decision.types import DecisionStatus
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import CompanyFinancials, CourierReport
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _report(financials=(), round_number=1):
    return CourierReport(
        simulation_id="SIM01",
        round_number=round_number,
        report_date=date(2027, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        company_financials=list(financials),
    )


def _financials(
    company=Company.BALDWIN,
    income=None,
    balance=None,
):
    return CompanyFinancials(
        company=company,
        income_statement=income or {},
        balance_sheet=balance or {},
    )


def _context(financials=(), *, history=None):
    report = _report(financials)
    return DecisionContext(
        report=report,
        financial_analysis=analyze_financials(report),
        history_analysis=history,
    )


def test_cash_is_informational_without_target_and_reviewable_with_explicit_target():
    context = _context([
        _financials(balance={"cash": Decimal("100")}),
    ])

    informational = evaluate_cash_position(
        context,
        Company.BALDWIN,
    )
    below_target = evaluate_cash_position(
        context,
        Company.BALDWIN,
        comparison_target=Decimal("150"),
    )

    assert informational.status is DecisionStatus.AVAILABLE
    assert informational.recommendation is None
    assert informational.evidence[0].value == Decimal("100")

    assert below_target.status is DecisionStatus.AVAILABLE
    assert below_target.recommendation is not None
    assert below_target.evidence[0].value == Decimal("100")
    assert below_target.evidence[1].value == Decimal("150")


def test_debt_leverage_reports_positive_debt_without_recommendation():
    context = _context([
        _financials(
            balance={
                "current_debt": Decimal("10"),
                "long_term_debt": Decimal("40"),
                "total_equity": Decimal("100"),
            }
        ),
    ])

    result = evaluate_debt_leverage(context, Company.BALDWIN)

    assert result.status is DecisionStatus.AVAILABLE
    assert result.recommendation is None
    assert result.evidence[0].value == Decimal("50")
    assert result.evidence[1].value == Decimal("100")
    assert result.evidence[2].value == Decimal("0.5")


def test_profitability_and_sales_margin_use_existing_analysis_values():
    context = _context([
        _financials(
            income={
                "sales": Decimal("200"),
                "contribution_margin": Decimal("80"),
                "net_profit": Decimal("20"),
            },
            balance={
                "cash": Decimal("100"),
                "total_equity": Decimal("100"),
            },
        ),
    ])

    profitability = evaluate_profitability(context, Company.BALDWIN)
    margin = evaluate_sales_contribution_margin(context, Company.BALDWIN)

    assert profitability.status is DecisionStatus.AVAILABLE
    assert profitability.recommendation is None
    assert profitability.evidence[0].value == Decimal("20")
    assert profitability.evidence[1].value == Decimal("10")

    assert margin.status is DecisionStatus.AVAILABLE
    assert margin.recommendation is None
    assert margin.evidence[0].value == Decimal("200")
    assert margin.evidence[1].value == Decimal("80")
    assert margin.evidence[2].value == Decimal("40")


def test_financial_history_reports_direction_with_sufficient_history():
    previous = _report(
        [
            _financials(
                income={"net_profit": Decimal("100")},
            ),
        ],
        round_number=0,
    )
    current = _report(
        [
            _financials(
                income={"net_profit": Decimal("125")},
            ),
        ],
        round_number=1,
    )
    history = analyze_history([previous, current])

    result = evaluate_financial_history(
        DecisionContext(
            report=current,
            history_analysis=history,
        ),
        Company.BALDWIN,
    )

    assert result.status is DecisionStatus.AVAILABLE
    assert any("increased" in observation for observation in result.observations)
    assert result.evidence[0].value == Decimal("100")
    assert result.evidence[1].value == Decimal("125")


def test_financial_history_requires_two_reports():
    context = _context([
        _financials(
            income={"net_profit": Decimal("125")},
        ),
    ])

    result = evaluate_financial_history(
        context,
        Company.BALDWIN,
    )

    assert result.status is DecisionStatus.INSUFFICIENT_DATA


def test_financial_evidence_completeness_identifies_missing_values():
    context = _context([
        _financials(
            income={"net_profit": Decimal("20")},
            balance={"cash": Decimal("100")},
        ),
    ])

    result = evaluate_financial_evidence_completeness(
        context,
        Company.BALDWIN,
    )

    assert result.status is DecisionStatus.MISSING_INPUT
    assert result.observations
    assert "total_debt" in result.observations[0]
    assert "total_equity" in result.observations[0]
    assert "sales" in result.observations[0]
    assert "contribution_margin" in result.observations[0]


def test_missing_financial_inputs_return_missing_input():
    context = _context([
        _financials(
            income={"net_profit": Decimal("20")},
        ),
    ])

    assert (
        evaluate_cash_position(context, Company.BALDWIN).status
        is DecisionStatus.MISSING_INPUT
    )
    assert (
        evaluate_debt_leverage(context, Company.BALDWIN).status
        is DecisionStatus.MISSING_INPUT
    )
    assert (
        evaluate_sales_contribution_margin(context, Company.BALDWIN).status
        is DecisionStatus.MISSING_INPUT
    )
    assert (
        evaluate_financial_evidence_completeness(
            context,
            Company.BALDWIN,
        ).status
        is DecisionStatus.MISSING_INPUT
    )


def test_round_0_baldwin_finance_integration():
    report = parse_courier_pdf(PDF_PATH)
    context = DecisionContext(
        report=report,
        financial_analysis=analyze_financials(report),
    )

    cash = evaluate_cash_position(context, Company.BALDWIN)
    profitability = evaluate_profitability(context, Company.BALDWIN)

    assert cash.status is DecisionStatus.AVAILABLE
    assert cash.evidence[0].value == Decimal("3434")

    assert profitability.status is DecisionStatus.AVAILABLE
    assert profitability.evidence[0].value == Decimal("4189")


def test_partial_financial_analysis_falls_back_to_raw_cash():
    report = _report([
        _financials(balance={"cash": Decimal("100")}),
    ])
    analysis = analyze_financials(report)
    partial = replace(
        analysis.companies[Company.BALDWIN],
        cash=None,
    )
    context = DecisionContext(
        report=report,
        financial_analysis=replace(
            analysis,
            companies={Company.BALDWIN: partial},
        ),
    )

    result = evaluate_cash_position(context, Company.BALDWIN)

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("100")


def test_partial_financial_analysis_falls_back_to_raw_net_profit():
    report = _report([
        _financials(income={"net_profit": Decimal("20")}),
    ])
    analysis = analyze_financials(report)
    partial = replace(
        analysis.companies[Company.BALDWIN],
        net_profit=None,
    )
    context = DecisionContext(
        report=report,
        financial_analysis=replace(
            analysis,
            companies={Company.BALDWIN: partial},
        ),
    )

    result = evaluate_profitability(context, Company.BALDWIN)

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("20")


def test_missing_financial_analysis_company_falls_back_to_raw_direct_values():
    report = _report([
        _financials(
            company=Company.BALDWIN,
            income={"net_profit": Decimal("20")},
        ),
    ])
    analysis = analyze_financials(_report())
    analysis = replace(
        analysis,
        companies={Company.ANDREWS: analysis.companies[Company.ANDREWS]},
    )
    context = DecisionContext(report=report, financial_analysis=analysis)

    result = evaluate_profitability(context, Company.BALDWIN)

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("20")


def test_non_none_financial_analysis_values_take_precedence():
    report = _report([
        _financials(balance={"cash": Decimal("100")}),
    ])
    analysis = analyze_financials(report)
    partial = replace(
        analysis.companies[Company.BALDWIN],
        cash=Decimal("125"),
    )
    context = DecisionContext(
        report=report,
        financial_analysis=replace(
            analysis,
            companies={Company.BALDWIN: partial},
        ),
    )

    result = evaluate_cash_position(context, Company.BALDWIN)

    assert result.status is DecisionStatus.AVAILABLE
    assert result.evidence[0].value == Decimal("125")


def test_partial_financial_fallback_does_not_reconstruct_derived_metrics():
    report = _report([
        _financials(
            income={"sales": Decimal("200")},
            balance={"total_equity": Decimal("100"), "long_term_debt": Decimal("40")},
        ),
    ])
    analysis = analyze_financials(report)
    partial = replace(
        analysis.companies[Company.BALDWIN],
        revenue=None,
        total_equity=None,
        total_debt=None,
        debt_to_equity=None,
    )
    context = DecisionContext(
        report=report,
        financial_analysis=replace(
            analysis,
            companies={Company.BALDWIN: partial},
        ),
    )

    leverage = evaluate_debt_leverage(context, Company.BALDWIN)

    assert leverage.status is DecisionStatus.MISSING_INPUT
    assert leverage.evidence[0].value is None
    assert leverage.evidence[1].value == Decimal("100")
    assert leverage.evidence[2].value is None
