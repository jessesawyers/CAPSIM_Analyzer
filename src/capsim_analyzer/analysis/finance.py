from __future__ import annotations

from decimal import Decimal

from ..enums import Company
from ..models import CompanyFinancials, CourierReport
from .types import FinancialAnalysis, FinancialMetrics


def analyze_financials(report: CourierReport) -> FinancialAnalysis:
    """Calculate financial facts from structured company financial statements."""
    source = {item.company: item for item in report.company_financials}
    companies = {
        company: _metrics(company, source.get(company))
        for company in report.companies
    }
    available = tuple(
        company for company, metrics in companies.items()
        if metrics.financials_available
    )
    return FinancialAnalysis(
        companies=companies,
        available_companies=available,
        incomplete_companies=tuple(
            company for company, metrics in companies.items()
            if not metrics.financials_available
        ),
    )


def _metrics(company: Company, financials: CompanyFinancials | None) -> FinancialMetrics:
    if financials is None:
        return FinancialMetrics(
            company=company,
            financials_available=False,
            revenue=None,
            direct_labor=None,
            direct_material=None,
            contribution_margin=None,
            contribution_margin_percent=None,
            ebit=None,
            ebit_margin=None,
            net_profit=None,
            net_profit_margin=None,
            cash=None,
            accounts_receivable=None,
            inventory=None,
            total_current_assets=None,
            current_liabilities=None,
            working_capital=None,
            current_ratio=None,
            debt_to_assets=None,
            inventory_to_current_assets=None,
            cash_to_current_assets=None,
            total_assets=None,
            accounts_payable=None,
            long_term_debt=None,
            common_stock=None,
            retained_earnings=None,
            current_debt=None,
            total_liabilities=None,
            total_equity=None,
            total_debt=None,
            debt_to_equity=None,
            balance_sheet_difference=None,
            balance_sheet_consistent=None,
            cash_flow={},
        )
        
    income = financials.income_statement
    balance = financials.balance_sheet

    total_current_assets = balance.get("total_current_assets")
    accounts_payable = balance.get("accounts_payable")
    current_debt = balance.get("current_debt")
    long_term_debt = balance.get("long_term_debt")

    current_liabilities = _sum_if_present(
        accounts_payable,
        current_debt,
    )

    working_capital = (
        None
        if total_current_assets is None or current_liabilities is None
        else total_current_assets - current_liabilities
    )

    current_ratio = _ratio(
        total_current_assets,
        current_liabilities,
    )

    total_equity = balance.get("total_equity")
    total_debt = _sum_if_present(current_debt, long_term_debt)

    assets = balance.get("total_assets")
    liabilities = balance.get("total_liabilities")
    balance_equity = balance.get("total_equity")

    debt_to_assets = _ratio(total_debt, assets)

    inventory_to_current_assets = _ratio(
        balance.get("inventory"),
        total_current_assets,
    )

    cash_to_current_assets = _ratio(
        balance.get("cash"),
        total_current_assets,
    )

    balance_difference = (
        None
        if assets is None or liabilities is None or balance_equity is None
        else assets - liabilities - balance_equity
    )
    
    return FinancialMetrics(
        company=company,
        financials_available=True,
        revenue=income.get("sales"),
        direct_labor=income.get("direct_labor"),
        direct_material=income.get("direct_material"),
        contribution_margin=income.get("contribution_margin"),
        contribution_margin_percent=_margin(income.get("contribution_margin"), income.get("sales")),
        ebit=income.get("ebit"),
        ebit_margin=_margin(income.get("ebit"), income.get("sales")),
        net_profit=income.get("net_profit"),
        net_profit_margin=_margin(income.get("net_profit"), income.get("sales")),
        cash=balance.get("cash"),
        accounts_receivable=balance.get("accounts_receivable"),
        inventory=balance.get("inventory"),
        total_current_assets=total_current_assets,
        current_liabilities=current_liabilities,
        working_capital=working_capital,
        current_ratio=current_ratio,
        debt_to_assets=debt_to_assets,
        inventory_to_current_assets=inventory_to_current_assets,
        cash_to_current_assets=cash_to_current_assets,
        total_assets=assets,
        accounts_payable=accounts_payable,
        long_term_debt=long_term_debt,
        common_stock=balance.get("common_stock"),
        retained_earnings=balance.get("retained_earnings"),
        current_debt=current_debt,
        total_liabilities=liabilities,
        total_equity=total_equity,
        total_debt=total_debt,
        debt_to_equity=_ratio(total_debt, total_equity),
        balance_sheet_difference=balance_difference,
        balance_sheet_consistent=None if balance_difference is None else balance_difference == 0,
        cash_flow=dict(financials.cash_flow_statement),
    )


def _margin(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    return numerator / denominator * Decimal("100")


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    return numerator / denominator


def _sum_if_present(first: Decimal | None, second: Decimal | None) -> Decimal | None:
    if first is None or second is None:
        return None
    return first + second
