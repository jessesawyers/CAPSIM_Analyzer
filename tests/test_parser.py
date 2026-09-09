from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "CourierC165051R0TBK0CA.PDF"


def test_parser_reads_courier_metadata():
    report = parse_courier_pdf(PDF_PATH)

    assert report.simulation_id == "C165051"
    assert report.round_number == 0
    assert report.report_date == date(2026, 12, 31)
    assert report.companies == list(Company)
    assert report.segments == list(Segment)


def test_parser_reads_all_production_rows():
    report = parse_courier_pdf(PDF_PATH)

    assert len(report.products) == 30
    assert len(report.production) == 30
    assert report.products[0].name == "Able"
    assert report.products[-1].name == "Fume"


def test_parser_reads_aft_production_data():
    report = parse_courier_pdf(PDF_PATH)
    aft = report.product_by_name("Aft")

    assert aft.company is Company.ANDREWS
    assert aft.segment is Segment.PERFORMANCE
    assert aft.perceptual_position.performance == Decimal("9.4")
    assert aft.perceptual_position.size == Decimal("15.5")
    assert aft.mtbf == 25000
    assert aft.list_price == Decimal("33.00")
    assert aft.units_sold == 358
    assert aft.inventory_units == 78
    assert aft.capacity_next_round == 600
    assert aft.plant_utilization_percent == Decimal("73")


def test_parser_reads_production_costs_and_capacity():
    report = parse_courier_pdf(PDF_PATH)
    able = report.product_by_name("Able")
    production = report.production[0]

    assert able.material_cost == Decimal("11.59")
    assert able.labor_cost == Decimal("7.49")
    assert able.contribution_margin_percent == Decimal("29")
    assert able.automation_level == Decimal("4.0")
    assert production.second_shift_percent == Decimal("0")
    assert production.overtime == Decimal("0")


def test_parser_reads_combined_second_shift_and_overtime_percentage():
    report = parse_courier_pdf(PDF_PATH)

    assert report.production[0].overtime == Decimal("0")
    assert report.production[1].overtime == Decimal("30")
    assert report.production[3].overtime == Decimal("0")


def test_parser_reads_segment_statistics():
    report = parse_courier_pdf(PDF_PATH)

    assert [(item.segment, item.total_industry_unit_demand, item.actual_industry_unit_sales,
              item.percent_of_total_industry, item.next_year_growth_rate_percent)
            for item in report.segment_reports] == [
        (Segment.TRADITIONAL, 7387, 7387, Decimal("32.4"), Decimal("9.2")),
        (Segment.LOW_END, 8960, 8960, Decimal("39.3"), Decimal("11.7")),
        (Segment.HIGH_END, 2554, 2554, Decimal("11.2"), Decimal("16.2")),
        (Segment.PERFORMANCE, 1915, 1915, Decimal("8.4"), Decimal("19.8")),
        (Segment.SIZE, 1984, 1984, Decimal("8.7"), Decimal("18.3")),
    ]


def test_parser_reads_segment_buying_criteria():
    report = parse_courier_pdf(PDF_PATH)
    traditional = report.segment_reports[0]

    assert [(item.rank, item.criterion, item.expectations, item.importance_percent)
            for item in traditional.buying_criteria] == [
        (1, "Age", {"ideal_age_years": Decimal("2.0")}, Decimal("47")),
        (2, "Price", {"minimum": Decimal("20.00"), "maximum": Decimal("30.00")}, Decimal("23")),
        (3, "Ideal Position", {"performance": Decimal("5.0"), "size": Decimal("15.0")}, Decimal("21")),
        (4, "Reliability", {"minimum": 14000, "maximum": 19000}, Decimal("9")),
    ]


def test_parser_reads_segment_product_snapshots():
    report = parse_courier_pdf(PDF_PATH)
    traditional = report.segment_reports[0]
    able = traditional.products[0]

    assert len(traditional.products) == 12
    assert able.product_name == "Able"
    assert able.market_share_percent == Decimal("13")
    assert able.units_sold == 961
    assert able.revision_date == date(2023, 11, 21)
    assert able.perceptual_position.performance == Decimal("5.5")
    assert able.perceptual_position.size == Decimal("14.5")
    assert able.list_price == Decimal("28.00")
    assert able.mtbf == 17500
    assert able.age_years == Decimal("3.10")
    assert able.promotion_budget == Decimal("1000")
    assert able.customer_awareness_percent == Decimal("55")
    assert able.sales_budget == Decimal("1000")
    assert able.customer_accessibility_percent == Decimal("54")
    assert able.customer_survey_score == Decimal("18")


def test_parser_reads_market_share_industry_totals():
    report = parse_courier_pdf(PDF_PATH)
    market_share = report.market_share

    assert market_share is not None
    assert market_share.industry_unit_sales == {
        Segment.TRADITIONAL: 7387,
        Segment.LOW_END: 8960,
        Segment.HIGH_END: 2554,
        Segment.PERFORMANCE: 1915,
        Segment.SIZE: 1984,
    }
    assert market_share.industry_units_demanded == market_share.industry_unit_sales


def test_parser_reads_actual_market_share_by_company():
    report = parse_courier_pdf(PDF_PATH)
    market_share = report.market_share

    assert market_share is not None
    assert [item.company for item in market_share.actual] == list(Company)
    andrews = market_share.actual[0]
    assert andrews.segment_percentages == {
        Segment.TRADITIONAL: Decimal("16.7"),
        Segment.LOW_END: Decimal("16.7"),
        Segment.HIGH_END: Decimal("16.7"),
        Segment.PERFORMANCE: Decimal("16.7"),
        Segment.SIZE: Decimal("16.7"),
    }
    assert andrews.total_percent == Decimal("16.7")


def test_parser_reads_potential_market_share_by_company():
    report = parse_courier_pdf(PDF_PATH)
    market_share = report.market_share

    assert market_share is not None
    assert [item.company for item in market_share.potential] == list(Company)
    ferris = market_share.potential[-1]
    assert ferris.segment_percentages[Segment.TRADITIONAL] == Decimal("16.7")
    assert ferris.total_percent == Decimal("16.7")


def test_parser_reads_round_0_balance_sheet():
    report = parse_courier_pdf(PDF_PATH)

    assert len(report.company_financials) == 1
    financials = report.company_financials[0]
    assert financials.company is Company.BALDWIN
    assert financials.balance_sheet == {
        "cash": Decimal("3434"),
        "accounts_receivable": Decimal("8307"),
        "inventory": Decimal("8617"),
        "total_current_assets": Decimal("20358"),
        "plant_and_equipment": Decimal("113800"),
        "accumulated_depreciation": Decimal("-37933"),
        "total_fixed_assets": Decimal("75867"),
        "total_assets": Decimal("96225"),
        "accounts_payable": Decimal("6583"),
        "current_debt": Decimal("0"),
        "long_term_debt": Decimal("41700"),
        "total_liabilities": Decimal("48283"),
        "common_stock": Decimal("18360"),
        "retained_earnings": Decimal("29582"),
        "total_equity": Decimal("47942"),
        "total_liabilities_and_equity": Decimal("96225"),
    }


def test_parser_reads_round_0_cash_flow_statement():
    report = parse_courier_pdf(PDF_PATH)
    cash_flow = report.company_financials[0].cash_flow_statement

    assert cash_flow["net_income_loss"] == Decimal("4189")
    assert cash_flow["accounts_payable"] == Decimal("3583")
    assert cash_flow["inventory"] == Decimal("-8617")
    assert cash_flow["accounts_receivable"] == Decimal("-307")
    assert cash_flow["net_cash_from_operations"] == Decimal("6434")
    assert cash_flow["dividends_paid"] == Decimal("-4000")
    assert cash_flow["net_cash_from_financing"] == Decimal("-4000")
    assert cash_flow["net_change_in_cash"] == Decimal("2434")
    assert cash_flow["closing_cash"] == Decimal("3434")


def test_parser_reads_round_0_income_statement_totals():
    report = parse_courier_pdf(PDF_PATH)
    income = report.company_financials[0].income_statement

    assert income["sales"] == Decimal("101073")
    assert income["direct_labor"] == Decimal("28932")
    assert income["direct_material"] == Decimal("42546")
    assert income["contribution_margin"] == Decimal("28561")
    assert income["ebit"] == Decimal("11996")
    assert income["net_profit"] == Decimal("4189")


def test_round_0_courier_report_contains_all_major_sections():
    report = parse_courier_pdf(PDF_PATH)

    assert (report.simulation_id, report.round_number, report.report_date) == (
        "C165051",
        0,
        date(2026, 12, 31),
    )
    assert report.companies == list(Company)
    assert report.segments == list(Segment)

    assert len(report.products) == 30
    assert len(report.production) == 30
    aft = report.product_by_name("Aft")
    assert aft.company is Company.ANDREWS
    assert aft.segment is Segment.PERFORMANCE
    assert aft.units_sold == 358
    assert report.production[3].product_name == "Aft"

    assert len(report.segment_reports) == 5
    traditional = next(
        item for item in report.segment_reports if item.segment is Segment.TRADITIONAL
    )
    assert traditional.total_industry_unit_demand == 7387
    assert traditional.buying_criteria[0].criterion == "Age"
    assert traditional.buying_criteria[0].importance_percent == Decimal("47")
    assert traditional.products[0].product_name == "Able"
    assert traditional.products[0].customer_survey_score == Decimal("18")

    assert report.market_share is not None
    assert report.market_share.industry_unit_sales[Segment.SIZE] == 1984
    assert report.market_share.actual[0].company is Company.ANDREWS
    assert report.market_share.actual[0].total_percent == Decimal("16.7")
    assert report.market_share.potential[-1].company is Company.FERRIS

    assert len(report.company_financials) == 1
    financials = report.company_financials[0]
    assert financials.company is Company.BALDWIN
    assert financials.balance_sheet["cash"] == Decimal("3434")
    assert financials.balance_sheet["accounts_receivable"] == Decimal("8307")
    assert financials.balance_sheet["inventory"] == Decimal("8617")
    assert financials.balance_sheet["total_assets"] == Decimal("96225")
    assert financials.balance_sheet["accounts_payable"] == Decimal("6583")
    assert financials.balance_sheet["long_term_debt"] == Decimal("41700")
    assert financials.balance_sheet["common_stock"] == Decimal("18360")
    assert financials.balance_sheet["retained_earnings"] == Decimal("29582")
    assert financials.income_statement["net_profit"] == Decimal("4189")
