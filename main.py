from itertools import product
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


# Company whose products should be highlighted in the user-facing report.
FOCUS_COMPANY = Company.BALDWIN


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


def get_focus_products(report):
    """
    Return the currently active products belonging to the focus company.

    Product membership is determined from the Courier report rather than
    from hardcoded product names, allowing products to be added or removed.
    """
    return [
        product
        for product in report.products
        if getattr(product, "company", None) == FOCUS_COMPANY
    ]


def get_product(report, product_name):
    """Find a product in the Courier report by name."""
    for product in report.products:
        if product.name == product_name:
            return product
    return None


def get_segment_product_snapshot(report, product_name):
    """Find the segment-analysis snapshot for a product by name."""
    for segment_report in report.segment_reports:
        for snapshot in segment_report.products:
            if snapshot.product_name == product_name:
                return snapshot
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


def get_marketing_observations(marketing_snapshot):
    """
    Identify conservative marketing-related review opportunities.

    These are review triggers, not guaranteed recommendations.
    They rely on marketing fields extracted from the Courier report.
    """
    observations = []

    if marketing_snapshot is None:
        return observations

    awareness = getattr(
        marketing_snapshot,
        "customer_awareness_percent",
        None,
    )

    accessibility = getattr(
        marketing_snapshot,
        "customer_accessibility_percent",
        None,
    )

    survey_score = getattr(
        marketing_snapshot,
        "customer_survey_score",
        None,
    )

    # Low awareness may indicate a promotion opportunity.
    if awareness is not None:
        awareness_value = Decimal(str(awareness))

        if awareness_value < Decimal("40"):
            observations.append(
                (
                    "MARKETING",
                    "Review promotion spending.",
                    (
                        f"Awareness is currently {awareness_value:.1f}%, "
                        "which may limit customer demand."
                    ),
                )
            )

    # Low accessibility may indicate a sales-budget/distribution issue.
    if accessibility is not None:
        accessibility_value = Decimal(str(accessibility))

        if accessibility_value < Decimal("40"):
            observations.append(
                (
                    "MARKETING",
                    "Review sales budget and accessibility.",
                    (
                        f"Accessibility is currently "
                        f"{accessibility_value:.1f}%, which may limit "
                        "product availability to customers."
                    ),
                )
            )

    # Very low survey scores may indicate poor product appeal,
    # positioning, or customer-perceived fit.
    if survey_score is not None:
        survey_value = Decimal(str(survey_score))

        if survey_value <= Decimal("5"):
            observations.append(
                (
                    "MARKETING",
                    "Review customer-perceived product fit.",
                    (
                        f"The customer survey score is "
                        f"{survey_value:.0f}, which may indicate weak "
                        "product appeal or positioning."
                    ),
                )
            )

    # If both awareness and accessibility are strong,
    # avoid automatically recommending more marketing.
    if awareness is not None and accessibility is not None:
        awareness_value = Decimal(str(awareness))
        accessibility_value = Decimal(str(accessibility))

        if (
            awareness_value >= Decimal("60")
            and accessibility_value >= Decimal("60")
        ):
            observations.append(
                (
                    "MARKETING",
                    "Marketing reach appears reasonably strong.",
                    (
                        "Awareness and accessibility are both at "
                        "relatively healthy levels."
                    ),
                )
            )

    return observations


def get_recommendation_product_name(recommendation, focus_product_names):
    """
    Try to identify the product associated with a recommendation.

    The engine normally provides entity information. The fallback text
    search makes the display layer more tolerant of future changes.
    """
    entity_id = getattr(recommendation, "entity_id", None)

    if entity_id:
        for product_name in focus_product_names:
            if product_name.lower() in str(entity_id).lower():
                return product_name

    text = " ".join(
        [
            str(getattr(recommendation, "action", "")),
            str(getattr(recommendation, "rationale", "")),
        ]
    ).lower()

    for product_name in focus_product_names:
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


def get_production_capacity_analysis(product, product_forecast):
    """
    Evaluate production capacity, utilization, and automation/labor conditions.

    This function intentionally separates:
    - physical capacity problems,
    - high utilization,
    - automation/labor-cost opportunities,
    - and normal production conditions.
    """

    capacity = product.capacity_next_round
    utilization = product.plant_utilization_percent
    automation = product.automation_level
    labor_cost = product.labor_cost

    forecast_demand = None

    if product_forecast is not None:
        forecast_demand = product_forecast.value

    observations = []

    # ---------------------------------------------------------
    # 1. Capacity compared with forecast demand
    # ---------------------------------------------------------

    if forecast_demand is not None and capacity is not None:
        capacity_gap = capacity - forecast_demand

        if capacity_gap < 0:
            observations.append(
                f"Capacity shortage: forecast demand exceeds listed capacity "
                f"by {number(abs(capacity_gap))} units."
            )

        elif capacity_gap <= max(100, capacity * 0.10):
            observations.append(
                f"Limited capacity headroom: forecast demand is only "
                f"{number(capacity_gap)} units below listed capacity."
            )

        else:
            observations.append(
                f"Forecast demand is approximately "
                f"{number(capacity_gap)} units below listed capacity."
            )

    # ---------------------------------------------------------
    # 2. Utilization interpretation
    # ---------------------------------------------------------

    if utilization is not None:
        if utilization >= 120:
            observations.append(
                "Utilization is critically high. Production capacity is under "
                "significant pressure."
            )

        elif utilization >= 90:
            observations.append(
                "Utilization is high. Monitor production pressure and future "
                "capacity requirements."
            )

        elif utilization <= 50:
            observations.append(
                "Current utilization is relatively low; immediate capacity "
                "expansion does not appear necessary."
            )

    # ---------------------------------------------------------
    # 3. Automation and labor-cost interpretation
    # ---------------------------------------------------------
    #
    # Automation is treated as a long-term labor-cost decision,
    # NOT as a solution to a physical capacity shortage.
    #
    # The tighter threshold avoids flagging every product with
    # moderately low automation.
    # ---------------------------------------------------------

    if automation is not None and labor_cost is not None:

        if automation <= 3 and labor_cost >= 9:
            observations.append(
                "Automation/labor opportunity: automation is relatively low "
                "while labor cost is high. Increasing automation may improve "
                "future margins, but does not directly increase production capacity."
            )

    # ---------------------------------------------------------
    # 4. Fallback if no meaningful concern was detected
    # ---------------------------------------------------------

    if not observations:
        observations.append(
            "No major production-capacity or labor-cost concern detected."
        )

    return observations


TOTAL_SIMULATION_ROUNDS = 6
AUTOMATION_COST_PER_CAPACITY = Decimal("4")
LABOR_SAVINGS_PER_AUTOMATION_POINT = Decimal("0.10")


def get_production_automation_analysis(
    product,
    product_forecast,
    current_round,
):
    """
    Evaluate whether automation deserves attention for the product.

    CAPSIM automation rules:
    - Automation ranges from 1.0 to 10.0.
    - Each additional automation point reduces labor cost by
      approximately 10%.
    - Each automation point costs $4 per unit of capacity.
    - Automation changes take a full year to take effect.

    ROI is estimated using:
        (labor savings * remaining rounds) / automation cost

    These are review triggers, not guaranteed decisions.
    """

    automation = product.automation_level
    labor_cost = product.labor_cost
    capacity = product.capacity_next_round

    forecast_demand = None
    if product_forecast is not None:
        forecast_demand = product_forecast.value

    observations = []

    if automation is None or labor_cost is None or capacity is None:
        return [
            "Automation analysis cannot be completed from the available data."
        ]

    if automation >= Decimal("10"):
        return [
            "Automation is already at the maximum level; no further increase is available."
        ]

    if forecast_demand is None:
        forecast_demand = product.units_sold

    if forecast_demand is None:
        return [
            "Automation priority cannot be determined without a production-volume estimate."
        ]

    automation = Decimal(str(automation))
    labor_cost = Decimal(str(labor_cost))
    capacity = Decimal(str(capacity))
    forecast_demand = Decimal(str(forecast_demand))

    remaining_rounds = max(
        0,
        TOTAL_SIMULATION_ROUNDS - current_round,
    )

    # CAPSIM charges $4 per unit of capacity for each
    # additional automation point.
    automation_cost = (
        capacity * AUTOMATION_COST_PER_CAPACITY
    )

    # CAPSIM estimates approximately 10% labor-cost savings
    # for each additional automation point.
    annual_labor_savings = (
        forecast_demand
        * labor_cost
        * LABOR_SAVINGS_PER_AUTOMATION_POINT
    )

    total_labor_savings = (
        annual_labor_savings
        * Decimal(str(remaining_rounds))
    )

    roi = None
    if automation_cost > 0:
        roi = (
            total_labor_savings
            / automation_cost
        ) * Decimal("100")

    # High production volume and meaningful labor cost make
    # automation more worthy of consideration.
    if forecast_demand >= Decimal("1000") and labor_cost >= Decimal("7"):
        observations.append(
            "Automation is worth evaluating due to high production volume and labor cost."
        )

        observations.append(
            f"A 1-level increase would cost approximately "
            f"${number(automation_cost)}."
        )

    elif forecast_demand >= Decimal("500") and labor_cost >= Decimal("8"):
        observations.append(
            "Automation may be worth evaluating due to production volume and labor cost."
        )

        observations.append(
            f"A 1-level increase would cost approximately "
            f"${number(automation_cost)}."
        )

    else:
        observations.append(
            "Automation is currently a low priority due to relatively low production volume."
        )

    # ROI is only meaningful when there are rounds remaining.
    if roi is not None and remaining_rounds > 0:
        observations.append(
            f"Estimated {remaining_rounds}-round labor savings are "
            f"approximately ${number(total_labor_savings)} "
            f"({roi:.1f}% ROI)."
        )

    # Capacity problems should take priority because automation
    # reduces labor cost but does not increase production capacity.
    if forecast_demand > capacity:
        observations.append(
            "Capacity pressure should be addressed first; automation does not increase capacity."
        )

    # High automation can make R&D repositioning more difficult.
    if automation >= Decimal("7"):
        observations.append(
            "Current automation is relatively high; consider the potential impact on future R&D repositioning."
        )

    return observations[:3]


def print_focus_product(
    product,
    product_forecast,
    recommendations,
    market_share_analysis,
    marketing_snapshot=None,
    current_round=0,
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
    print(f"Performance:         {product.perceptual_position.performance}")
    print(f"Size:                {product.perceptual_position.size}")
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


    production_observations = get_production_capacity_analysis(
        product,
        product_forecast,
    )

    print("\nPRODUCTION CAPACITY ANALYSIS")
    print("-" * 40)

    for observation in production_observations:
        print(f"- {observation}")


    automation_observations = get_production_automation_analysis(
        product,
        product_forecast,
        current_round,
    )

    print("\nPRODUCTION AUTOMATION ANALYSIS")
    print("-" * 40)
    for observation in automation_observations:
        print(f"- {observation}")

    
    print("\nMARKETING")
    print("-" * 40)

    print(
        f"Promotion budget:     "
        f"{money(getattr(marketing_snapshot, 'promotion_budget', None))}"
    )
    print(
        f"Sales budget:         "
        f"{money(getattr(marketing_snapshot, 'sales_budget', None))}"
    )
    print(
        f"Awareness:            "
        f"{percent(getattr(marketing_snapshot, 'customer_awareness_percent', None))}"
    )
    print(
        f"Accessibility:        "
        f"{percent(getattr(marketing_snapshot, 'customer_accessibility_percent', None))}"
    )
    print(
        f"Survey score:         "
        f"{number(getattr(marketing_snapshot, 'customer_survey_score', None))}"
    )


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

    
    marketing_observations = get_marketing_observations(
        marketing_snapshot,
    )

    if marketing_observations:
        print("\nMARKETING OBSERVATIONS")
        print("-" * 40)

        for _, title, explanation in marketing_observations:
            print(f"⚠ {title}")
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

    # Add marketing-related review items before engine recommendations.
    for category, title, explanation in marketing_observations:
        item = (title, explanation)

        if item in decision_focus:
            continue

        decision_focus.append(item)

        if len(decision_focus) >= 3:
            break


    if len(decision_focus) < 3:
        for _, title, explanation in marketing_observations:
            item = (title, explanation)

            if item in decision_focus:
                continue

            decision_focus.append(item)

            if len(decision_focus) >= 3:
                break


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
        print("  python main.py data/Week_0.PDF")
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
    focus_products = get_focus_products(report)
    focus_product_names = [product.name for product in focus_products]

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
    f"focuses on the currently active {FOCUS_COMPANY.value} products."
    )

    recommendations_by_product = {
        product_name: []
        for product_name in focus_product_names
    }

    for recommendation in decision_report.recommendations:
        product_name = get_recommendation_product_name(
            recommendation,
            focus_product_names,
        )

        if product_name in recommendations_by_product:
            recommendations_by_product[product_name].append(recommendation)

    for product in focus_products:
        product_name = product.name
        product = get_product(report, product_name)

        print_focus_product(
            product=product,
            product_forecast=product_forecasts.get(product_name),
            recommendations=recommendations_by_product[product_name],
            market_share_analysis=market_share_analysis,
            marketing_snapshot=get_segment_product_snapshot(
                report,
                product_name,
            ),
            current_round=report.round_number,
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

    for product_name in focus_product_names:
        displayed_recommendations += min(
        len(recommendations_by_product[product_name]),
        3,
    )

    print(f"Products analyzed:       {len(report.products)}")
    print(f"Focus products:           {len(focus_product_names)}")
    print(f"Recommendations reviewed: {displayed_recommendations}")

    print(
    "\nThe analyzer evaluates all products and market data, "
    f"then highlights the {len(focus_product_names)} currently active "
    f"{FOCUS_COMPANY.value} products for decision-making."
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