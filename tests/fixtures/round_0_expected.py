from datetime import date
from decimal import Decimal

from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.models import (
    CompanyFinancials,
    CourierReport,
    PerceptualPosition,
    Product,
    SegmentReport,
)


def round_0_report() -> CourierReport:
    products = [
        Product("Able", Company.ANDREWS, Segment.TRADITIONAL,
                PerceptualPosition(Decimal("5.5"), Decimal("14.5")),
                date(2023, 11, 21), Decimal("3.1"), 17500, Decimal("28.00")),
        Product("Acre", Company.ANDREWS, Segment.LOW_END),
        Product("Adam", Company.ANDREWS, Segment.HIGH_END),
        Product("Aft", Company.ANDREWS, Segment.PERFORMANCE,
                PerceptualPosition(Decimal("9.4"), Decimal("15.5")),
                mtbf=25000, list_price=Decimal("33.00")),
        Product("Agape", Company.ANDREWS, Segment.SIZE),
        Product("Baker", Company.BALDWIN, Segment.TRADITIONAL),
        Product("Bead", Company.BALDWIN, Segment.LOW_END),
        Product("Bid", Company.BALDWIN, Segment.HIGH_END),
        Product("Bold", Company.BALDWIN, Segment.PERFORMANCE),
        Product("Buddy", Company.BALDWIN, Segment.SIZE),
        Product("Cake", Company.CHESTER, Segment.TRADITIONAL),
        Product("Cedar", Company.CHESTER, Segment.LOW_END),
        Product("Cid", Company.CHESTER, Segment.HIGH_END),
        Product("Coat", Company.CHESTER, Segment.PERFORMANCE),
        Product("Cure", Company.CHESTER, Segment.SIZE),
        Product("Daze", Company.DIGBY, Segment.TRADITIONAL),
        Product("Dell", Company.DIGBY, Segment.LOW_END),
        Product("Duck", Company.DIGBY, Segment.HIGH_END),
        Product("Dot", Company.DIGBY, Segment.PERFORMANCE),
        Product("Dune", Company.DIGBY, Segment.SIZE),
        Product("Eat", Company.ERIE, Segment.TRADITIONAL),
        Product("Ebb", Company.ERIE, Segment.LOW_END),
        Product("Echo", Company.ERIE, Segment.HIGH_END),
        Product("Edge", Company.ERIE, Segment.PERFORMANCE),
        Product("Egg", Company.ERIE, Segment.SIZE),
        Product("Fast", Company.FERRIS, Segment.TRADITIONAL),
        Product("Feat", Company.FERRIS, Segment.LOW_END),
        Product("Fist", Company.FERRIS, Segment.HIGH_END),
        Product("Foam", Company.FERRIS, Segment.PERFORMANCE),
        Product("Fume", Company.FERRIS, Segment.SIZE),
    ]
    segment_values = [
        (Segment.TRADITIONAL, 7387, Decimal("32.4"), Decimal("9.2")),
        (Segment.LOW_END, 8960, Decimal("39.3"), Decimal("11.7")),
        (Segment.HIGH_END, 2554, Decimal("11.2"), Decimal("16.2")),
        (Segment.PERFORMANCE, 1915, Decimal("8.4"), Decimal("19.8")),
        (Segment.SIZE, 1984, Decimal("8.7"), Decimal("18.3")),
    ]
    segments = [
        SegmentReport(segment, demand, demand, share, growth)
        for segment, demand, share, growth in segment_values
    ]
    financials = CompanyFinancials(
        company=Company.ANDREWS,
        balance_sheet={
            "cash": Decimal("3434"),
            "accounts_receivable": Decimal("8307"),
            "inventory": Decimal("8617"),
            "total_assets": Decimal("96225"),
            "accounts_payable": Decimal("6583"),
            "long_term_debt": Decimal("41700"),
            "common_stock": Decimal("18360"),
            "retained_earnings": Decimal("29582"),
        },
        income_statement={"net_profit": Decimal("4189")},
    )
    return CourierReport(
        simulation_id="C165051",
        round_number=0,
        report_date=date(2026, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        products=products,
        segment_reports=segments,
        company_financials=[financials],
    )
