from datetime import date
from decimal import Decimal
from pathlib import Path

from capsim_analyzer.enums import Company, Segment
from capsim_analyzer.forecasting.products import (
    forecast_product_sales_from_market_share,
    forecast_product_sales_percentage_growth,
)
from capsim_analyzer.forecasting.segments import (
    forecast_segment_demand_with_courier_growth,
)
from capsim_analyzer.forecasting.types import ForecastStatus, ForecastValue
from capsim_analyzer.models import (
    CourierReport,
    PerceptualPosition,
    Product,
    SegmentProductSnapshot,
    SegmentReport,
)
from capsim_analyzer.parser import parse_courier_pdf


PDF_PATH = Path(__file__).parents[1] / "data" / "Week_0.PDF"


def _report(round_number, *, products=(), segment_reports=(), simulation_id="SIM01"):
    return CourierReport(
        simulation_id=simulation_id,
        round_number=round_number,
        report_date=date(2026 + round_number, 12, 31),
        companies=list(Company),
        segments=list(Segment),
        products=list(products),
        segment_reports=list(segment_reports),
    )


def _product(name, segment, units=None):
    return Product(
        name=name,
        company=Company.ANDREWS,
        segment=segment,
        perceptual_position=PerceptualPosition(),
        units_sold=units,
    )


def _segment(segment, demand, snapshot=None):
    return SegmentReport(
        segment=segment,
        total_industry_unit_demand=demand,
        actual_industry_unit_sales=demand,
        percent_of_total_industry=Decimal("50"),
        next_year_growth_rate_percent=Decimal("10"),
        products=[] if snapshot is None else [snapshot],
    )


def _share(name, share):
    return SegmentProductSnapshot(
        product_name=name,
        market_share_percent=share,
    )


def test_market_share_forecast_uses_explicit_segment_forecast():
    report = _report(
        1,
        products=[_product("Able", Segment.TRADITIONAL)],
        segment_reports=[
            _segment(
                Segment.TRADITIONAL,
                1000,
                _share("Able", Decimal("12.5")),
            )
        ],
    )
    demand = {
        Segment.TRADITIONAL: ForecastValue(
            Decimal("1234.56"),
            ForecastStatus.AVAILABLE,
            "test_segment_demand",
            (1,),
            1,
            1,
        )
    }

    result = forecast_product_sales_from_market_share([report], demand)["Able"]

    assert result.value == Decimal("154.32")
    assert result.method == "market_share_based_product_sales"
    assert result.source_rounds == (1,)
    assert result.status is ForecastStatus.AVAILABLE


def test_market_share_forecast_supports_multiple_segments_and_default_courier_growth():
    report = _report(
        0,
        products=[
            _product("Able", Segment.TRADITIONAL),
            _product("Aft", Segment.PERFORMANCE),
        ],
        segment_reports=[
            _segment(Segment.TRADITIONAL, 100, _share("Able", Decimal("10"))),
            _segment(Segment.PERFORMANCE, 200, _share("Aft", Decimal("25"))),
        ],
    )

    results = forecast_product_sales_from_market_share([report])

    assert results["Able"].value == Decimal("11.00")
    assert results["Aft"].value == Decimal("55.000")


def test_market_share_forecast_handles_missing_inputs():
    report = _report(
        1,
        products=[
            _product("MissingShare", Segment.TRADITIONAL),
            _product("MissingDemand", Segment.LOW_END),
        ],
        segment_reports=[
            _segment(Segment.TRADITIONAL, 100, _share("Other", Decimal("10"))),
        ],
    )
    results = forecast_product_sales_from_market_share([report])

    assert results["MissingShare"].status is ForecastStatus.MISSING_INPUT
    assert results["MissingDemand"].status is ForecastStatus.MISSING_INPUT


def test_historical_product_growth_forecast():
    previous = _report(
        0,
        products=[_product("Able", Segment.TRADITIONAL, 100)],
    )
    current = _report(
        1,
        products=[_product("Able", Segment.TRADITIONAL, 125)],
    )

    result = forecast_product_sales_percentage_growth([current, previous])["Able"]

    assert result.value == Decimal("156.25")
    assert result.method == "historical_product_percentage_growth"
    assert result.source_rounds == (0, 1)


def test_historical_growth_handles_missing_zero_and_insufficient_history():
    zero = _report(0, products=[_product("Able", Segment.TRADITIONAL, 0)])
    current = _report(1, products=[_product("Able", Segment.TRADITIONAL, 10)])
    zero_result = forecast_product_sales_percentage_growth([zero, current])["Able"]
    assert zero_result.status is ForecastStatus.ZERO_DENOMINATOR

    missing = _report(1, products=[_product("Able", Segment.TRADITIONAL, None)])
    missing_result = forecast_product_sales_percentage_growth([zero, missing])["Able"]
    assert missing_result.status is ForecastStatus.MISSING_INPUT

    one_round = forecast_product_sales_percentage_growth([current])["Able"]
    assert one_round.status is ForecastStatus.INSUFFICIENT_HISTORY


def test_historical_growth_reports_products_missing_from_one_round():
    previous = _report(
        0,
        products=[_product("Able", Segment.TRADITIONAL, 100)],
    )
    current = _report(
        1,
        products=[_product("Aft", Segment.PERFORMANCE, 50)],
    )

    results = forecast_product_sales_percentage_growth([previous, current])

    assert results["Able"].status is ForecastStatus.MISSING_INPUT
    assert results["Aft"].status is ForecastStatus.MISSING_INPUT


def test_product_forecasts_are_deterministic_and_do_not_mutate_reports():
    report = _report(
        0,
        products=[_product("Able", Segment.TRADITIONAL, 100)],
        segment_reports=[
            _segment(Segment.TRADITIONAL, 100, _share("Able", Decimal("10")))
        ],
    )
    before = report.products, report.segment_reports

    first = forecast_product_sales_from_market_share([report])
    second = forecast_product_sales_from_market_share([report])

    assert first == second
    assert (report.products, report.segment_reports) == before


def test_round_0_product_sales_forecasts_use_able_and_aft_data():
    report = parse_courier_pdf(PDF_PATH)
    demand = forecast_segment_demand_with_courier_growth(report)
    results = forecast_product_sales_from_market_share([report], demand)

    assert results["Able"].value == Decimal("1048.65852")
    assert results["Aft"].value == Decimal("390.0089")
    assert results["Able"].source_rounds == (0,)
    assert results["Aft"].status is ForecastStatus.AVAILABLE
