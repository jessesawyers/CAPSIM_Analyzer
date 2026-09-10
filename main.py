import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from capsim_analyzer.parser import parse_courier_pdf
from capsim_analyzer.analysis.segments import analyze_segments
from capsim_analyzer.analysis.market_share import analyze_market_share
from capsim_analyzer.analysis.products import analyze_products
from capsim_analyzer.analysis.production import analyze_production
from capsim_analyzer.analysis.finance import analyze_financials
from capsim_analyzer.enums import Company
from capsim_analyzer.forecasting.segments import (
    forecast_segment_demand_with_courier_growth,
)
from capsim_analyzer.forecasting.products import (
    forecast_product_sales_from_market_share,
)
from capsim_analyzer.decision.context import DecisionContext
from capsim_analyzer.decision.engine import evaluate_decisions


# Products we want to focus on in the user-facing report.
FOCUS_PRODUCTS = {"Bead", "Baker", "Bid", "Bold", "Buddy"}


def money(value):
    """Format a numeric value as currency."""
    if value is None:
        return "N/A"

    try:
        return f"${Decimal(str(value)):,.0f}"
    except Exception:
        return str(value)


def number(value):
    """Format a numeric value with commas."""
    if value is None:
        return "N/A"

    try:
        return f"{Decimal(str(value)):,.0f}"
    except Exception:
        return str(value)


def percent(value):
    """Format a percentage value."""
    if value is None:
        return "N/A"

    try:
        return f"{Decimal(str(value)):.1f}%"
    except Exception:
        return str(value)


def get_product(report, product_name):
    """Find a product in the Courier report by name."""
    for product in report.products:
        if product.name == product_name:
            return product
    return None


def get_product_observations(product, product_forecast):
    observations = []

    forecast_value = None
    if product_forecast is not None:
        forecast_value = getattr(product_forecast, "value", product_forecast)

    if product.plant_utilization_percent is not None:
        utilization = Decimal(str(product.plant_utilization_percent))

        if utilization > Decimal("100"):
            observations.append(
                (
                    "WARNING",
                    "Production capacity is under pressure.",
                    f"Plant utilization is {utilization:.1f}%, above available capacity."
                )
            )
        elif utilization >= Decimal("85"):
            observations.append(
                (
                    "WATCH",
                    "Production capacity is relatively high.",
                    f"Plant utilization is {utilization:.1f}%."
                )
            )

    if product.inventory_units is not None and product.units_sold:
        inventory = Decimal(str(product.inventory_units))
        sales = Decimal(str(product.units_sold))

        if inventory < sales * Decimal("0.10"):
            observations.append(
                (
                    "WARNING",
                    "Inventory is very low.",
                    f"Only {number(inventory)} units are in inventory compared with "
                    f"{number(sales)} units sold."
                )
            )

    if forecast_value is not None and product.units_sold:
        current_sales = Decimal(str(product.units_sold))
        forecast = Decimal(str(forecast_value))

        change = ((forecast - current_sales) / current_sales) * Decimal("100")

        if change >= Decimal("10"):
            observations.append(
                (
                    "OPPORTUNITY",
                    "Forecast demand is increasing.",
                    f"Forecast sales are {number(forecast)} units, "
                    f"{change:+.1f}% versus current sales."
                )
            )
        elif change <= Decimal("-10"):
            observations.append(
                (
                    "WATCH",
                    "Forecast demand is decreasing.",
                    f"Forecast sales are {number(forecast)} units, "
                    f"{change:+.1f}% versus current sales."
                )
            )

    return observations


def get_recommendation_product_name(recommendation):
    """
    Try to identify the product associated with a recommendation.

    The engine normally provides entity information. The fallback text
    search makes the display layer more tolerant of future changes.
    """
    entity_id = getattr(recommendation, "entity_id", None)

    if entity_id:
        for product_name in FOCUS_PRODUCTS:
            if product_name.lower() in str(entity_id).lower():
                return product_name

    text = " ".join(
        [
            str(getattr(recommendation, "action", "")),
            str(getattr(recommendation, "rationale", "")),
        ]
    ).lower()

    for product_name in FOCUS_PRODUCTS:
        if product_name.lower() in text:
            return product_name

    return None


def recommendation_topic(recommendation):
    """
    Give recommendations a simple human-readable topic so similar
    recommendations can be grouped together.
    """
    text = " ".join(
        [
            str(getattr(recommendation, "action", "")),
            str(getattr(recommendation, "rationale", "")),
        ]
    ).lower()

    if "market share" in text:
        return "MARKET SHARE"

    if "capacity" in text or "production" in text:
        return "PRODUCTION"

    if "promotion" in text or "awareness" in text or "accessibility" in text:
        return "MARKETING"

    if "position" in text or "perceptual" in text:
        return "POSITIONING"

    if "mtbf" in text:
        return "RELIABILITY"

    if "price" in text:
        return "PRICE"

    if "age" in text or "revision" in text:
        return "PRODUCT AGE"

    if "sales" in text or "forecast" in text:
        return "SALES"

    return "OTHER"


def print_focus_product(
    product,
    product_forecast,
    recommendations,
    market_share_analysis,
):
    """Print a concise but useful summary for one focus product."""

    print("\n" + "=" * 60)
    print(f"{product.name.upper()} — {product.company.value.upper()}")
    print("=" * 60)

    print("\nSEGMENT PERFORMANCE")
    print("-" * 40)

    print(f"Segment:             {product.segment.value}")
    print(f"Current sales:       {number(product.units_sold)}")

    company_metrics = getattr(
        market_share_analysis,
        "companies",
        {},
    ).get(product.company)

    actual_share = None
    potential_share = None

    if company_metrics is not None:
        actual_share = getattr(
            company_metrics,
            "actual_by_segment",
            {},
        ).get(product.segment)

        potential_share = getattr(
            company_metrics,
            "potential_by_segment",
            {},
        ).get(product.segment)

    # Get forecast information before displaying it.
    forecast_value = None
    forecast_status = None
    forecast_change = None

    if product_forecast is not None:
        forecast_value = getattr(product_forecast, "value", product_forecast)
        forecast_status = getattr(product_forecast, "status", None)

        if product.units_sold:
             forecast_change = (
                (Decimal(str(forecast_value)) - Decimal(str(product.units_sold)))
                / Decimal(str(product.units_sold))
            ) * Decimal("100")

    print(f"Forecast sales:      {number(forecast_value)}")

    if forecast_status is not None:
        print(
            f"Forecast status:     "
            f"{getattr(forecast_status, 'value', forecast_status)}"
        )

    if forecast_change is not None:
        print(f"Forecast change:     {forecast_change:+.1f}%")

    print(f"Segment share:       {percent(actual_share)}")
    print(f"Potential share:     {percent(potential_share)}")
    print("\nPRODUCT")
    print("-" * 40)
    print(f"Price:               {money(product.list_price)}")
    print(f"MTBF:                {number(product.mtbf)}")
    print(f"Age:                 {product.age_years} years")
    print(f"Material cost:       {money(product.material_cost)}")
    print(f"Labor cost:          {money(product.labor_cost)}")
    print(f"Contribution margin: {percent(product.contribution_margin_percent)}")

    print("\nOPERATIONS")
    print("-" * 40)

    print(f"Inventory:            {number(product.inventory_units)}")
    print(f"Capacity:             {number(product.capacity_next_round)}")
    print(f"Utilization:          {percent(product.plant_utilization_percent)}")
    print(f"Automation:           {product.automation_level}")

    observations = get_product_observations(
        product,
        product_forecast,
    )

    if observations:
        print("\nKEY OBSERVATIONS")
        print("-" * 40)

        for level, title, explanation in observations:
            symbol = {
                "WARNING": "⚠",
                "WATCH": "→",
                "OPPORTUNITY": "✓",
            }.get(level, "•")

            print(f"{symbol} {title}")
            print(f"  {explanation}")

    # Build practical decision-focus items from the product's
    # most relevant observations and recommendations.
    decision_focus = []

    if product.plant_utilization_percent is not None:
        utilization = Decimal(str(product.plant_utilization_percent))

        if utilization > Decimal("100"):
            decision_focus.append(
                (
                    "Review production capacity.",
                    f"Plant utilization is currently {utilization:.1f}%."
                )
            )
        elif utilization >= Decimal("85"):
            decision_focus.append(
                (
                    "Monitor production capacity.",
                    f"Plant utilization is currently {utilization:.1f}%."
                )
            )

    if product.inventory_units is not None and product.units_sold:
        inventory = Decimal(str(product.inventory_units))
        sales = Decimal(str(product.units_sold))

        if inventory < sales * Decimal("0.10"):
            decision_focus.append(
                (
                    "Review inventory levels.",
                    f"Only {number(inventory)} units are available "
                    f"against {number(sales)} units sold."
                )
            )

    if forecast_change is not None:
        if forecast_change >= Decimal("10"):
            decision_focus.append(
                (
                    "Prepare for higher demand.",
                    f"Forecast sales are {forecast_change:+.1f}% above "
                    "current sales."
                )
            )
        elif forecast_change <= Decimal("-10"):
            decision_focus.append(
                (
                    "Prepare for lower demand.",
                    f"Forecast sales are {forecast_change:+.1f}% below "
                    "current sales."
                )
            )

    # Add an engine recommendation if there is still room for another
    # useful decision item.
    for recommendation in recommendations:
        action = str(getattr(recommendation, "action", "")).strip()
        rationale = str(getattr(recommendation, "rationale", "")).strip()

        if not action:
            continue

        item = (action, rationale)

        if item in decision_focus:
            continue

        decision_focus.append(item)

        if len(decision_focus) >= 3:
            break

    print("\nDECISION FOCUS")
    print("-" * 40)

    if decision_focus:
        for action, rationale in decision_focus[:3]:
            print(f"  • {action}")

            if rationale:
                print(f"    Why: {rationale}")
    else:
        print("  • No specific decision focus was identified.")


def print_all_market_share(report, market_share_analysis):
    """
    Display actual and potential market share for every product.

    Market share is stored by company and segment, so each product
    uses the market-share values for its company within its segment.
    """
    print("\nALL-PRODUCT MARKET SHARE")
    print("-" * 40)

    companies = getattr(market_share_analysis, "companies", {})

    for product in report.products:
        company_metrics = companies.get(product.company)

        if company_metrics is None:
            print(f"{product.name:<12} N/A")
            continue

        actual_by_segment = getattr(
            company_metrics,
            "actual_by_segment",
            {},
        )

        potential_by_segment = getattr(
            company_metrics,
            "potential_by_segment",
            {},
        )

        actual = actual_by_segment.get(product.segment)
        potential = potential_by_segment.get(product.segment)

        print(
            f"{product.name:<12} "
            f"Actual: {percent(actual):>6}  "
            f"Potential: {percent(potential):>6}"
        )


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python main.py data/CourierC165051R0TBK0CA.PDF")
        return

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return

    print("\n" + "=" * 60)
    print("                 CAPSIM ANALYZER")
    print("=" * 60)

    print("\nReading Courier report...")
    report = parse_courier_pdf(pdf_path)

    print(f"Company reports loaded: {len(report.companies)}")
    print(f"Products analyzed:      {len(report.products)}")

    # ---------------------------------------------------------
    # ANALYSIS
    # ---------------------------------------------------------

    segment_analysis = analyze_segments(report)
    market_share_analysis = analyze_market_share(report)
    product_analysis = analyze_products(report)
    production_analysis = analyze_production(report)
    financial_analysis = analyze_financials(report)

    # ---------------------------------------------------------
    # FORECASTING
    # ---------------------------------------------------------

    segment_forecasts = forecast_segment_demand_with_courier_growth(report)

    product_forecasts = forecast_product_sales_from_market_share(
        (report,),
        segment_demand_forecasts=segment_forecasts,
    )

    # ---------------------------------------------------------
    # DECISION ENGINE
    # ---------------------------------------------------------

    context = DecisionContext(
        report=report,
        segment_analysis=segment_analysis,
        market_share_analysis=market_share_analysis,
        product_analysis=product_analysis,
        production_analysis=production_analysis,
        financial_analysis=financial_analysis,
        segment_demand_forecasts=segment_forecasts,
        product_sales_forecasts=product_forecasts,
    )

    decision_report = evaluate_decisions(context)

    # ---------------------------------------------------------
    # FORECAST SUMMARY
    # ---------------------------------------------------------

    print("\nFORECAST SUMMARY")
    print("-" * 40)

    for segment, forecast in segment_forecasts.items():
        forecast_value = getattr(forecast, "value", forecast)
        print(f"{segment.value:<15} {number(forecast_value)} units")

    # ---------------------------------------------------------
    # FOCUS PRODUCTS
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("                  FOCUS PRODUCTS")
    print("=" * 60)

    print(
        "\nThe analyzer calculates all products, but the decision report "
        "focuses on Bead, Baker, Bid, Bold, and Buddy."
    )

    recommendations_by_product = {
        product_name: []
        for product_name in FOCUS_PRODUCTS
    }

    for recommendation in decision_report.recommendations:
        product_name = get_recommendation_product_name(recommendation)

        if product_name in recommendations_by_product:
            recommendations_by_product[product_name].append(recommendation)

    # Keep the user's requested order.
    for product_name in ["Bead", "Baker", "Bid", "Bold", "Buddy"]:
        product = get_product(report, product_name)

        if product is None:
            print(f"\n{product_name.upper()}")
            print("-" * 40)
            print("Product was not found in this Courier report.")
            continue

        print_focus_product(
            product=product,
            product_forecast=product_forecasts.get(product_name),
            recommendations=recommendations_by_product[product_name],
            market_share_analysis=market_share_analysis,
        )

    # ---------------------------------------------------------
    # FINANCIAL SNAPSHOT
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("                 FINANCIAL SNAPSHOT")
    print("=" * 60)

    companies = getattr(financial_analysis, "companies", {})

    baldwin_financials = companies.get(Company.BALDWIN)

    if baldwin_financials:
        print(
            f"Cash:               "
            f"{money(getattr(baldwin_financials, 'cash', None))}"
        )
        print(
            f"Sales:              "
            f"{money(getattr(baldwin_financials, 'revenue', None))}"
        )
        print(
            f"Net profit:         "
            f"{money(getattr(baldwin_financials, 'net_profit', None))}"
        )
        print(
            f"EBIT:                "
            f"{money(getattr(baldwin_financials, 'ebit', None))}"
        )
        print(
            f"Contribution margin: "
            f"{money(getattr(baldwin_financials, 'contribution_margin', None))}"
        )
    else:
        print("Financial information is incomplete for Baldwin.")

    # ---------------------------------------------------------
    # FULL MARKET CALCULATION
    # ---------------------------------------------------------

    print_all_market_share(report, market_share_analysis)

    # ---------------------------------------------------------
    # ENGINE SUMMARY
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("                  REPORT SUMMARY")
    print("=" * 60)

    displayed_recommendations = 0

    for product_name in ["Bead", "Baker", "Bid", "Bold", "Buddy"]:
        displayed_recommendations += min(
        len(recommendations_by_product[product_name]),
        3,
    )

    print(f"Products analyzed:       {len(report.products)}")
    print(f"Focus products:           {len(FOCUS_PRODUCTS)}")
    print(f"Recommendations reviewed: {displayed_recommendations}")

    print(
    "\nThe analyzer evaluates all products and market data, "
    "then highlights the five selected focus products for "
    "decision-making."
)

    print(
    "Recommendations are review triggers based on the data available "
    "in the Courier report; they are not guaranteed actions."
)

    print("\n" + "=" * 60)
    print("                    COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()