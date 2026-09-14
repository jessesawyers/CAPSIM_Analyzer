from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.analysis.finance import analyze_financials
from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import CompanyFinancials, CourierReport
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _report(financials=()):
    return CourierReport(
        simulation_id="TEST01",
        round_number=1,
        report_date=date(2027, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        company_financials=list(financials),
    )


def _financials(
    company=Company.ANDREWS,
    income=None,
    balance=None,
    cash_flow=None,
):
    return CompanyFinancials(
        company=company,
        income_statement=income or {},
        balance_sheet=balance or {},
        cash_flow_statement=cash_flow or {},
    )


def test_financial_analysis_calculates_margins_debt_and_consistency():
    analysis = analyze_financials(
        _report(
            [_financials(
                income={
                    "sales": Decimal("200"),
                    "direct_labor": Decimal("50"),
                    "direct_material": Decimal("70"),
                    "contribution_margin": Decimal("80"),
                    "ebit": Decimal("40"),
                    "net_profit": Decimal("20"),
                },
                balance={
                    "cash": Decimal("10"),
                    "current_debt": Decimal("5"),
                    "long_term_debt": Decimal("25"),
                    "total_liabilities": Decimal("30"),
                    "total_equity": Decimal("70"),
                    "total_assets": Decimal("100"),
                },
                cash_flow={"net_change_in_cash": Decimal("3")},
            )]
        )
    )
    metrics = analysis.companies[Company.ANDREWS]

    assert metrics.revenue == Decimal("200")
    assert metrics.contribution_margin_percent == Decimal("40")
    assert metrics.ebit_margin == Decimal("20")
    assert metrics.net_profit_margin == Decimal("10")
    assert metrics.total_debt == Decimal("30")
    assert metrics.debt_to_equity == Decimal("3") / Decimal("7")
    assert metrics.balance_sheet_difference == Decimal("0")
    assert metrics.balance_sheet_consistent is True
    assert metrics.cash_flow["net_change_in_cash"] == Decimal("3")


def test_financial_analysis_handles_zero_denominators_and_missing_fields():
    analysis = analyze_financials(
        _report(
            [_financials(
                income={"sales": Decimal("0"), "net_profit": Decimal("10")},
                balance={"total_equity": Decimal("0"), "long_term_debt": Decimal("10")},
            )]
        )
    )
    metrics = analysis.companies[Company.ANDREWS]

    assert metrics.contribution_margin_percent is None
    assert metrics.ebit_margin is None
    assert metrics.net_profit_margin is None
    assert metrics.debt_to_equity is None
    assert metrics.balance_sheet_consistent is None
    assert metrics.cash is None


def test_financial_analysis_marks_partial_company_coverage():
    analysis = analyze_financials(_report())

    assert analysis.available_companies == ()
    assert set(analysis.incomplete_companies) == set(Company)
    assert analysis.companies[Company.BALDWIN].financials_available is False
    assert analysis.companies[Company.BALDWIN].net_profit is None


def test_financial_analysis_round_0_baldwin_values():
    report = parse_courier_pdf(PDF_PATH)
    analysis = analyze_financials(report)
    metrics = analysis.companies[Company.BALDWIN]

    assert metrics.financials_available is True
    assert metrics.revenue == Decimal("101073")
    assert metrics.direct_labor == Decimal("28932")
    assert metrics.direct_material == Decimal("42546")
    assert metrics.contribution_margin == Decimal("28561")
    assert metrics.ebit == Decimal("11996")
    assert metrics.net_profit == Decimal("4189")
    assert metrics.cash == Decimal("3434")
    assert metrics.accounts_receivable == Decimal("8307")
    assert metrics.inventory == Decimal("8617")
    assert metrics.total_assets == Decimal("96225")
    assert metrics.accounts_payable == Decimal("6583")
    assert metrics.long_term_debt == Decimal("41700")
    assert metrics.common_stock == Decimal("18360")
    assert metrics.retained_earnings == Decimal("29582")
    assert metrics.contribution_margin_percent == (
        Decimal("28561") / Decimal("101073") * Decimal("100")
    )
    assert metrics.net_profit_margin == (
        Decimal("4189") / Decimal("101073") * Decimal("100")
    )
    assert metrics.balance_sheet_consistent is True
    assert metrics.cash_flow["closing_cash"] == Decimal("3434")
