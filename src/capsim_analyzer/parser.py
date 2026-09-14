from __future__ import annotations

import re
import shutil
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .enums import Company, Segment
from .models import (
    BuyingCriterion,
    CompanyMarketShare,
    CompanyFinancials,
    CourierReport,
    MarketShareReport,
    PerceptualPosition,
    Product,
    ProductionRecord,
    SegmentProductSnapshot,
    SegmentReport,
)


_COMPANIES = list(Company)
_SEGMENTS = list(Segment)
_SEGMENT_BY_CODE = {
    "Trad": Segment.TRADITIONAL,
    "Low": Segment.LOW_END,
    "High": Segment.HIGH_END,
    "Pfmn": Segment.PERFORMANCE,
    "Size": Segment.SIZE,
}
_SEGMENT_BY_NAME = {segment.value: segment for segment in Segment}
_ROW = re.compile(
    r"^(?P<name>[A-Za-z]+)\s+(?P<segment>Trad|Low|High|Pfmn|Size)\s+"
    r"(?P<units>[\d,]+)\s+(?P<inventory>[\d,]+)\s+"
    r"(?P<revision>\d{1,2}/\d{1,2}/\d{4})\s+(?P<age>\d+(?:\.\d+)?)\s+"
    r"(?P<mtbf>\d+)\s+(?P<performance>\d+(?:\.\d+)?)\s+"
    r"(?P<size>\d+(?:\.\d+)?)\s+\$(?P<price>[\d.]+)\s+"
    r"\$(?P<material>[\d.]+)\s+\$(?P<labor>[\d.]+)\s+"
    r"(?P<margin>\d+)%\s+(?P<shift>\d+)%\s+"
    r"(?P<automation>\d+(?:\.\d+)?)\s+(?P<capacity>[\d,]+)\s+"
    r"(?P<utilization>\d+)%$"
)
_SEGMENT_PRODUCT_ROW = re.compile(
    r"^(?P<name>[A-Za-z]+)\s+(?P<share>\d+)%\s+(?P<units>[\d,]+)\s+"
    r"(?P<revision>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?:(?P<stock_out>YES)\s+)?"
    r"(?P<performance>\d+(?:\.\d+)?)\s+"
    r"(?P<size>\d+(?:\.\d+)?)\s+\$(?P<price>[\d.]+)\s+(?P<mtbf>\d+)\s+"
    r"(?P<age>\d+(?:\.\d+)?)\s+\$(?P<promotion>[\d,]+)\s+"
    r"(?P<awareness>\d+)%\s+\$(?P<sales>[\d,]+)\s+"
    r"(?P<accessibility>\d+)%\s+(?P<survey>\d+)$"
)


def parse_courier_pdf(path: str | Path, *, pdftotext_executable: str | None = None) -> CourierReport:
    """Parse Courier metadata, Segment Analysis, and Production Analysis."""
    text = _extract_table_text(Path(path), pdftotext_executable)
    simulation_id, round_number, report_date = _parse_metadata(text)
    products, production = _parse_production(text)
    segment_reports = _parse_segment_analysis(text)
    market_share = _parse_market_share(text)
    company_financials = _parse_financial_statements(text)
    return CourierReport(
        simulation_id=simulation_id,
        round_number=round_number,
        report_date=report_date,
        companies=_COMPANIES.copy(),
        segments=_SEGMENTS.copy(),
        products=products,
        segment_reports=segment_reports,
        market_share=market_share,
        production=production,
        company_financials=company_financials,
    )


def _extract_table_text(path: Path, executable: str | None) -> str:
    return _extract_page_text(path, executable, layout=False)


def _extract_page_text(
    path: Path,
    executable: str | None,
    *,
    layout: bool,
    page: int | None = None,
) -> str:
    command = executable or shutil.which("pdftotext")
    if command is None:
        raise RuntimeError("pdftotext is required to parse Courier PDFs")
    mode = "-layout" if layout else "-raw"
    page_args = ["-f", str(page), "-l", str(page)] if page is not None else []
    result = subprocess.run(
        [command, "-q", mode, *page_args, str(path), "-"],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _parse_segment_analysis(text: str) -> list[SegmentReport]:
    reports: list[SegmentReport] = []
    section_pattern = re.compile(
        r"(?P<name>Traditional|Low End|High End|Performance|Size) Segment Analysis"
        r"(?P<body>.*?)(?=CAPSTONE|$)",
        re.DOTALL,
    )
    for match in section_pattern.finditer(text):
        segment = _SEGMENT_BY_NAME[match.group("name")]
        body = match.group("body")
        demand = _required_integer(body, r"Total Industry Unit Demand\s+([\d,]+)")
        sales = _required_integer(body, r"Actual Industry Unit Sales\s+\|?([\d,]+)")
        share = _required_decimal(body, r"Segment % of Total Industry\s+\|?([\d.]+)%")
        growth = _required_decimal(body, r"Next Year's Segment Growth Rate\s+\|?([\d.]+)%")
        reports.append(
            SegmentReport(
                segment=segment,
                total_industry_unit_demand=demand,
                actual_industry_unit_sales=sales,
                percent_of_total_industry=share,
                next_year_growth_rate_percent=growth,
                buying_criteria=_parse_buying_criteria(body),
                products=_parse_segment_products(body),
            )
        )
    if len(reports) != len(_SEGMENTS):
        raise ValueError(f"expected {len(_SEGMENTS)} segment reports, found {len(reports)}")
    return reports


def _parse_buying_criteria(body: str) -> list[BuyingCriterion]:
    criteria: list[BuyingCriterion] = []
    for match in re.finditer(
        r"^(?P<rank>[1-4])\.\s+(?P<criterion>Age|Price|Ideal Position|Reliability)\s+"
        r"(?P<expectation>.+?)\s+(?P<importance>\d+)%\r?$",
        body,
        re.MULTILINE,
    ):
        criterion = match.group("criterion")
        expectation = match.group("expectation")
        if criterion == "Age":
            expectations = {"ideal_age_years": _required_decimal(expectation, r"Ideal Age = ([\d.]+)")}
        elif criterion == "Price":
            low, high = re.search(r"\$([\d.]+) - ([\d.]+)", expectation).groups()
            expectations = {"minimum": Decimal(low), "maximum": Decimal(high)}
        elif criterion == "Ideal Position":
            position = re.search(r"Pfmn ([\d.]+) Size ([\d.]+)", expectation)
            if position is None:
                raise ValueError(f"invalid ideal position expectation: {expectation}")
            expectations = {
                "performance": Decimal(position.group(1)),
                "size": Decimal(position.group(2)),
            }
        else:
            minimum, maximum = re.search(r"MTBF (\d+)-(\d+)", expectation).groups()
            expectations = {"minimum": int(minimum), "maximum": int(maximum)}
        criteria.append(
            BuyingCriterion(
                rank=int(match.group("rank")),
                criterion=criterion,
                expectations=expectations,
                importance_percent=Decimal(match.group("importance")),
            )
        )
    if len(criteria) != 4:
        raise ValueError(f"expected four buying criteria, found {len(criteria)}")
    return criteria


def _parse_segment_products(body: str) -> list[SegmentProductSnapshot]:
    products: list[SegmentProductSnapshot] = []
    for line in body.splitlines():
        match = _SEGMENT_PRODUCT_ROW.match(line.strip())
        if match:
            row = match.groupdict()
            products.append(
                SegmentProductSnapshot(
                    product_name=row["name"],
                    market_share_percent=Decimal(row["share"]),
                    units_sold=_integer(row["units"]),
                    revision_date=datetime.strptime(row["revision"], "%m/%d/%Y").date(),
                    perceptual_position=PerceptualPosition(
                        Decimal(row["performance"]),
                        Decimal(row["size"]),
                    ),
                    list_price=Decimal(row["price"]),
                    mtbf=int(row["mtbf"]),
                    age_years=Decimal(row["age"]),
                    promotion_budget=Decimal(row["promotion"].replace(",", "")),
                    customer_awareness_percent=Decimal(row["awareness"]),
                    sales_budget=Decimal(row["sales"].replace(",", "")),
                    customer_accessibility_percent=Decimal(row["accessibility"]),
                    customer_survey_score=Decimal(row["survey"]),
                )
            )
    if not products:
        raise ValueError("segment report contains no product snapshots")
    return products


def _required_integer(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"required integer not found: {pattern}")
    return _integer(match.group(1))


def _required_decimal(text: str, pattern: str) -> Decimal:
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"required decimal not found: {pattern}")
    return Decimal(match.group(1))


def _parse_market_share(raw_text: str) -> MarketShareReport:
    start = raw_text.index("Market Share")
    end = raw_text.index("CAPSTONE", start)
    section = raw_text[start:end]
    industry_match = re.search(
        r"Industry Unit Sales\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)"
        r"\s+Units Demanded\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)",
        section,
    )
    if industry_match is None:
        raise ValueError("Market Share industry totals could not be parsed")
    values = [int(value.replace(",", "")) for value in industry_match.groups()]
    industry_sales = dict(zip(_SEGMENTS, values[:5], strict=True))
    industry_demand = dict(zip(_SEGMENTS, values[6:11], strict=True))

    totals = [
        re.findall(r"[\d.]+%", line)
        for line in section.splitlines()
        if line.startswith("Total ")
    ]
    if len(totals) != len(_COMPANIES) or any(len(values) != 12 for values in totals):
        raise ValueError("Market Share company totals could not be parsed")
    actual = []
    potential = []
    for company, values in zip(_COMPANIES, totals, strict=True):
        actual.append(
            CompanyMarketShare(
                company,
                dict(zip(_SEGMENTS, (_decimal_percent(value) for value in values[:5]), strict=True)),
                _decimal_percent(values[5]),
            )
        )
        potential.append(
            CompanyMarketShare(
                company,
                dict(zip(_SEGMENTS, (_decimal_percent(value) for value in values[6:11]), strict=True)),
                _decimal_percent(values[11]),
            )
        )
    return MarketShareReport(
        industry_unit_sales=industry_sales,
        industry_units_demanded=industry_demand,
        actual=actual,
        potential=potential,
    )


def _decimal_percent(value: str) -> Decimal:
    return Decimal(value.rstrip("%"))


def _parse_financial_statements(text: str) -> list[CompanyFinancials]:
    match = re.search(
        r"Annual Report\s+Annual Report\s+(?P<company>Andrews|Baldwin|Chester|Digby|Erie|Ferris)"
        r".*?(?=CAPSTONE|$)",
        text,
        re.DOTALL,
    )

    if match is None:
        raise ValueError("Annual Report financial statements could not be parsed")

    section = match.group(0)
    company = Company(match.group("company"))

    return [
        CompanyFinancials(
            company=company,
            cash_flow_statement=_parse_cash_flow_statement(section),
            balance_sheet=_parse_balance_sheet(section),
            income_statement=_parse_income_statement(section),
        )
    ]


def _parse_balance_sheet(section: str) -> dict[str, Decimal | None]:
    labels = {
        "Cash": "cash",
        "Accounts Receivable": "accounts_receivable",
        "Account Receivable": "accounts_receivable",
        "Inventory": "inventory",
        "Total Current Assets": "total_current_assets",
        "Plant and equipment": "plant_and_equipment",
        "Plant & Equipment": "plant_and_equipment",
        "Accumulated Depreciation": "accumulated_depreciation",
        "Total Fixed Assets": "total_fixed_assets",
        "Total Assets": "total_assets",
        "Accounts Payable": "accounts_payable",
        "Current Debt": "current_debt",
        "Long Term Debt": "long_term_debt",
        "Total Liabilities": "total_liabilities",
        "Common Stock": "common_stock",
        "Retained Earnings": "retained_earnings",
        "Total Equity": "total_equity",
        "Total Liabilities & Owners Equity": "total_liabilities_and_equity",
        "Total Liab. & O. Equity": "total_liabilities_and_equity",
    }

    return _parse_current_year_labeled_amounts(section, labels)


def _parse_cash_flow_statement(section: str) -> dict[str, Decimal | None]:
    start = section.index("Cash Flow Statement")

    income_statement_match = re.search(
        r"\d{4} Income Statement",
        section[start:],
    )

    if income_statement_match is None:
        raise ValueError("Income Statement heading could not be found")

    end = start + income_statement_match.start()
    section = section[start:end]

    labels = {
        "Net Income(Loss)": "net_income_loss",
        "Depreciation": "depreciation",
        "Extraordinary gains/losses/writeoffs": (
            "extraordinary_gains_losses_writeoffs"
        ),
        "Accounts Payable": "accounts_payable",
        "Inventory": "inventory",
        "Accounts Receivable": "accounts_receivable",
        "Net cash from operation": "net_cash_from_operations",
        "Net cash from operations": "net_cash_from_operations",
        "Plant Improvements": "plant_improvements",
        "Plant improvements(net)": "plant_improvements",
        "Dividends paid": "dividends_paid",
        "Sales of common stock": "sales_of_common_stock",
        "Purchase of common stock": "purchase_of_common_stock",
        "Cash from long term debt": "cash_from_long_term_debt",
        "Cash from long term debt issued": "cash_from_long_term_debt",
        "Retirement of long term debt": "retirement_of_long_term_debt",
        "Early retirement of long term debt": "retirement_of_long_term_debt",
        "Change in current debt(net)": "change_in_current_debt",
        "Net cash from financing activities": "net_cash_from_financing",
        "Net change in cash position": "net_change_in_cash",
        "Closing cash position": "closing_cash",
    }

    return _parse_current_year_labeled_amounts(section, labels)


def _parse_income_statement(section: str) -> dict[str, Decimal | None]:
    income_statement_match = re.search(
        r"\d{4} Income Statement",
        section,
    )

    if not income_statement_match:
        raise ValueError("Income Statement section not found")

    section = section[income_statement_match.start():]

    labels = {
        "Sales": "sales",
        "Direct Labor": "direct_labor",
        "Direct Material": "direct_material",
        "Inventory Carry": "inventory_carry",
        "Total Variable": "total_variable",
        "Contribution Margin": "contribution_margin",
        "Depreciation": "depreciation",
        "SG&A: R&D": "sga_rd",
        "Promotions": "promotions",
        "Admin": "admin",
        "Total Period": "total_period",
        "Net Margin": "net_margin",
        "Other": "other",
        "EBIT": "ebit",
        "Short Term Interest": "short_term_interest",
        "Long Term Interest": "long_term_interest",
        "Taxes": "taxes",
        "Profit Sharing": "profit_sharing",
        "Net Profit": "net_profit",
    }

    values: dict[str, Decimal | None] = {}

    for label, key in labels.items():
        matches = re.findall(
            rf"^{re.escape(label)}\s+(.+)$",
            section,
            re.MULTILINE,
        )

        if not matches:
            continue

        # "Sales" appears twice in the income statement:
        # the first occurrence is total product sales,
        # while the later occurrence is the SG&A sales expense.
        target = matches[0] if label == "Sales" else matches[-1]

        amounts = re.findall(
            r"\(?\$[\d,]+\)?",
            target,
        )

        if amounts:
            values[key] = _money(amounts[-1])

    return values


def _parse_current_year_labeled_amounts(
    section: str,
    labels: dict[str, str],
) -> dict[str, Decimal | None]:
    values: dict[str, Decimal | None] = {}

    for label, key in labels.items():
        matches = re.findall(
            rf"^{re.escape(label)}\s+(.+)$",
            section,
            re.MULTILINE,
        )

        if not matches:
            continue

        amounts = re.findall(
            r"\(?\$[\d,]+\)?",
            matches[0],
        )

        if amounts:
            values[key] = _money(amounts[0])

    missing = [
        key
        for key in set(labels.values())
        if key not in values
    ]

    if missing:
        raise ValueError(
            f"financial statement values missing: {', '.join(sorted(missing))}"
        )

    return values


def _money(value: str) -> Decimal:
    negative = value.startswith("(") and value.endswith(")")
    digits = value.strip("()$").replace(",", "")

    amount = Decimal(digits)

    return -amount if negative else amount


def _parse_metadata(text: str) -> tuple[str, int, date]:
    simulation_match = re.search(r"\b([A-Z]\d{6})\b", text)
    round_match = re.search(r"Round:\s*(\d+)", text)
    date_match = re.search(r"Dec\.\s*31,\s*\n?\s*(\d{4})", text)
    if not (simulation_match and round_match and date_match):
        raise ValueError("Courier metadata could not be parsed")
    return (
        simulation_match.group(1),
        int(round_match.group(1)),
        date(int(date_match.group(1)), 12, 31),
    )


def _parse_production(text: str) -> tuple[list[Product], list[ProductionRecord]]:
    start = text.index("Production Analysis")
    end = text.index("CAPSTONE", start)
    rows = [_ROW.match(line.strip()) for line in text[start:end].splitlines()]
    parsed = [match.groupdict() for match in rows if match]
    if len(parsed) != 30:
        raise ValueError(f"expected 30 production rows, found {len(parsed)}")

    products: list[Product] = []
    production: list[ProductionRecord] = []
    for index, row in enumerate(parsed):
        company = _COMPANIES[index // 5]
        segment = _SEGMENT_BY_CODE[row["segment"]]
        product = Product(
            name=row["name"],
            company=company,
            segment=segment,
            perceptual_position=PerceptualPosition(
                Decimal(row["performance"]),
                Decimal(row["size"]),
            ),
            revision_date=datetime.strptime(row["revision"], "%m/%d/%Y").date(),
            age_years=Decimal(row["age"]),
            mtbf=int(row["mtbf"]),
            list_price=Decimal(row["price"]),
            material_cost=Decimal(row["material"]),
            labor_cost=Decimal(row["labor"]),
            contribution_margin_percent=Decimal(row["margin"]),
            units_sold=_integer(row["units"]),
            inventory_units=_integer(row["inventory"]),
            capacity_next_round=_integer(row["capacity"]),
            plant_utilization_percent=Decimal(row["utilization"]),
            automation_level=Decimal(row["automation"]),
        )
        products.append(product)
        production.append(
            ProductionRecord(
                company=company,
                product_name=product.name,
                primary_segment=segment,
                units_sold=product.units_sold,
                inventory_units=product.inventory_units,
                capacity_next_round=product.capacity_next_round,
                plant_utilization_percent=product.plant_utilization_percent,
                second_shift_percent=Decimal(row["shift"]),
                overtime=Decimal(row["shift"]),
                automation_level=product.automation_level,
            )
        )
    return products, production


def _integer(value: str) -> int:
    return int(value.replace(",", ""))
