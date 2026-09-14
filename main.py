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


def ratio(value):
    """Format a ratio for concise CLI output."""
    if value is None:
        return "N/A"

    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return str(value)


def get_financial_observations(financials):
    """
    Convert financial metrics into concise, decision-oriented observations.

    These are interpretation/review triggers, not guaranteed decisions.
    """

    observations = []

    if financials is None:
        return observations

    current_ratio = getattr(financials, "current_ratio", None)
    working_capital = getattr(financials, "working_capital", None)
    cash_to_current_assets = getattr(
        financials,
        "cash_to_current_assets",
        None,
    )
    debt_to_assets = getattr(financials, "debt_to_assets", None)
    debt_to_equity = getattr(financials, "debt_to_equity", None)
    current_debt = getattr(financials, "current_debt", None)
    long_term_debt = getattr(financials, "long_term_debt", None)
    inventory_to_current_assets = getattr(
        financials,
        "inventory_to_current_assets",
        None,
    )
    net_profit_margin = getattr(
        financials,
        "net_profit_margin",
        None,
    )
    contribution_margin_percent = getattr(
        financials,
        "contribution_margin_percent",
        None,
    )

    # ---------------------------------------------------------
    # Liquidity
    # ---------------------------------------------------------

    if current_ratio is not None:
        current_ratio = Decimal(str(current_ratio))

        if current_ratio >= Decimal("2"):
            observations.append(
                (
                    "POSITIVE",
                    "Strong short-term liquidity.",
                    (
                        f"Current assets substantially exceed current "
                        f"liabilities, with a current ratio of "
                        f"{ratio(current_ratio)}."
                    ),
                )
            )

        elif current_ratio < Decimal("1"):
            observations.append(
                (
                    "WARNING",
                    "Short-term liquidity is a concern.",
                    (
                        f"The current ratio is only {ratio(current_ratio)}, "
                        "so current liabilities exceed current assets."
                    ),
                )
            )

        else:
            observations.append(
                (
                    "WATCH",
                    "Short-term liquidity is relatively tight.",
                    (
                        f"The current ratio is {ratio(current_ratio)}, "
                        "leaving less short-term financial flexibility."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Working capital
    # ---------------------------------------------------------

    if working_capital is not None:
        working_capital = Decimal(str(working_capital))

        if working_capital > 0:
            observations.append(
                (
                    "POSITIVE",
                    "Working capital is positive.",
                    (
                        f"Baldwin has {money(working_capital)} in "
                        "working capital to support ongoing operations."
                    ),
                )
            )

        elif working_capital < 0:
            observations.append(
                (
                    "WARNING",
                    "Working capital is negative.",
                    (
                        f"Current liabilities exceed current assets by "
                        f"{money(abs(working_capital))}."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Cash position
    # ---------------------------------------------------------

    if cash_to_current_assets is not None:
        cash_to_current_assets = Decimal(str(cash_to_current_assets))

        cash_percent = cash_to_current_assets * Decimal("100")

        if cash_to_current_assets >= Decimal("0.50"):
            observations.append(
                (
                    "POSITIVE",
                    "Cash position is strong.",
                    (
                        f"Cash represents {cash_percent:.1f}% of current "
                        "assets, providing substantial liquidity for "
                        "near-term operating needs."
                    ),
                )
            )

        elif cash_to_current_assets < Decimal("0.20"):
            observations.append(
                (
                    "WATCH",
                    "Cash reserves are relatively limited.",
                    (
                        f"Cash represents only {cash_percent:.1f}% of "
                        "current assets, so major spending decisions "
                        "should be evaluated carefully."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Debt / leverage
    # ---------------------------------------------------------

    if debt_to_assets is not None:
        debt_to_assets = Decimal(str(debt_to_assets))

        if debt_to_assets >= Decimal("0.60"):
            observations.append(
                (
                    "WARNING",
                    "Debt leverage is relatively high.",
                    (
                        f"Debt represents {debt_to_assets * Decimal('100'):.1f}% "
                        "of total assets, so additional borrowing should "
                        "be evaluated carefully."
                    ),
                )
            )

        elif debt_to_assets <= Decimal("0.40"):
            observations.append(
                (
                    "POSITIVE",
                    "Debt levels appear manageable.",
                    (
                        f"Debt represents {debt_to_assets * Decimal('100'):.1f}% "
                        "of total assets."
                    ),
                )
            )

        else:
            observations.append(
                (
                    "WATCH",
                    "Debt levels deserve monitoring.",
                    (
                        f"Debt represents {debt_to_assets * Decimal('100'):.1f}% "
                        "of total assets."
                    ),
                )
            )

    if debt_to_equity is not None:
        debt_to_equity = Decimal(str(debt_to_equity))

        if debt_to_equity >= Decimal("1.5"):
            observations.append(
                (
                    "WARNING",
                    "Debt is high relative to equity.",
                    (
                        f"Debt is {ratio(debt_to_equity)}x total equity, "
                        "which may limit flexibility for additional financing."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Debt structure
    # ---------------------------------------------------------

    if (
        current_debt is not None
        and long_term_debt is not None
    ):
        current_debt = Decimal(str(current_debt))
        long_term_debt = Decimal(str(long_term_debt))

        if current_debt == 0 and long_term_debt > 0:
            observations.append(
                (
                    "POSITIVE",
                    "Existing debt is primarily long-term.",
                    (
                        "There is currently no current debt, reducing "
                        "near-term repayment pressure."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Inventory position
    # ---------------------------------------------------------

    if inventory_to_current_assets is not None:
        inventory_to_current_assets = Decimal(
            str(inventory_to_current_assets)
        )

        inventory_percent = (
            inventory_to_current_assets * Decimal("100")
        )

        if inventory_to_current_assets >= Decimal("0.40"):
            observations.append(
                (
                    "WATCH",
                    "A large portion of current assets is tied up in inventory.",
                    (
                        f"Inventory represents {inventory_percent:.1f}% "
                        "of current assets. Production decisions should "
                        "be checked against expected demand."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Profitability
    # ---------------------------------------------------------

    if net_profit_margin is not None:
        net_profit_margin = Decimal(str(net_profit_margin))

        if net_profit_margin >= Decimal("10"):
            observations.append(
                (
                    "POSITIVE",
                    "Profitability is strong.",
                    (
                        f"Net profit margin is {net_profit_margin:.1f}%, "
                        "indicating healthy conversion of sales into profit."
                    ),
                )
            )

        elif net_profit_margin < Decimal("0"):
            observations.append(
                (
                    "WARNING",
                    "The company is currently unprofitable.",
                    (
                        f"Net profit margin is "
                        f"{net_profit_margin:.1f}%."
                    ),
                )
            )

        elif net_profit_margin < Decimal("5"):
            observations.append(
                (
                    "WARNING",
                    "Profitability is relatively weak.",
                    (
                        f"Net profit margin is "
                        f"{net_profit_margin:.1f}%, "
                        "so major spending decisions should be evaluated "
                        "carefully against expected returns."
                    ),
                )
            )

        else:
            observations.append(
                (
                    "WATCH",
                    "Profitability is positive but modest.",
                    (
                        f"Net profit margin is "
                        f"{net_profit_margin:.1f}%."
                    ),
                )
            )

    # ---------------------------------------------------------
    # Overall investment implication
    # ---------------------------------------------------------

    liquidity_supports_investment = (
        current_ratio is not None
        and current_ratio >= Decimal("2")
        and working_capital is not None
        and working_capital > 0
    )

    leverage_is_manageable = (
        debt_to_assets is not None
        and debt_to_assets < Decimal("0.60")
    )

    profitable = (
        net_profit_margin is not None
        and net_profit_margin > 0
    )

    if (
        liquidity_supports_investment
        and leverage_is_manageable
        and profitable
    ):
        observations.append(
            (
                "IMPLICATION",
                "Financial position appears capable of supporting near-term investment.",
                (
                    "Liquidity is healthy, leverage is manageable, and the "
                    "company is profitable. Spending decisions should still "
                    "be evaluated against expected operational returns."
                ),
            )
        )

    elif (
        liquidity_supports_investment
        and profitable
    ):
        observations.append(
            (
                "IMPLICATION",
                "Some near-term investment appears financially supportable.",
                (
                    "Liquidity and profitability provide some flexibility, "
                    "but leverage or another financial factor warrants "
                    "additional caution."
                ),
            )
        )

    return observations


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
    """
    Return concise, measurable product-level observations.

    Production-capacity details are handled separately by
    get_production_and_automation_analysis().
    """

    observations = []

    # ---------------------------------------------------------
    # Inventory
    # ---------------------------------------------------------

    if product.inventory_units is not None and product.units_sold:
        inventory = Decimal(str(product.inventory_units))
        sales = Decimal(str(product.units_sold))

        if inventory < sales * Decimal("0.10"):
            observations.append(
                (
                    "WARNING",
                    "Inventory is very low.",
                    f"Only {number(inventory)} units are in inventory "
                    f"compared with {number(sales)} units sold.",
                )
            )

    # ---------------------------------------------------------
    # Forecast trend
    # ---------------------------------------------------------

    forecast_value = None

    if product_forecast is not None:
        forecast_value = getattr(
            product_forecast,
            "value",
            product_forecast,
        )

    if forecast_value is not None and product.units_sold:
        current_sales = Decimal(str(product.units_sold))
        forecast = Decimal(str(forecast_value))

        if current_sales != 0:
            change = (
                (forecast - current_sales)
                / current_sales
            ) * Decimal("100")

            if change >= Decimal("10"):
                observations.append(
                    (
                        "OPPORTUNITY",
                        "Forecast demand is increasing.",
                        f"Forecast sales are {number(forecast)} units, "
                        f"{change:+.1f}% versus current sales.",
                    )
                )

            elif change <= Decimal("-10"):
                observations.append(
                    (
                        "WATCH",
                        "Forecast demand is decreasing.",
                        f"Forecast sales are {number(forecast)} units, "
                        f"{change:+.1f}% versus current sales.",
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


def get_production_and_automation_analysis(product, product_forecast):
    """
    Provide concise production-capacity and automation guidance.

    Capacity increases physical production capability.
    Automation reduces labor cost but does not increase capacity.
    """

    capacity = product.capacity_next_round
    utilization = product.plant_utilization_percent
    automation = product.automation_level
    labor_cost = product.labor_cost

    forecast_demand = None

    if product_forecast is not None:
        forecast_demand = getattr(
            product_forecast,
            "value",
            product_forecast,
        )

    if forecast_demand is None:
        forecast_demand = product.units_sold

    observations = []

    if capacity is None:
        return [
            "Production-capacity analysis cannot be completed "
            "from the available data."
        ]

    capacity = Decimal(str(capacity))

    if forecast_demand is not None:
        forecast_demand = Decimal(str(forecast_demand))

    if utilization is not None:
        utilization = Decimal(str(utilization))

    if automation is not None:
        automation = Decimal(str(automation))

    if labor_cost is not None:
        labor_cost = Decimal(str(labor_cost))

    # ---------------------------------------------------------
    # CAPSIM production cost formulas
    # ---------------------------------------------------------

    cost_per_capacity_unit = None
    cost_to_double_capacity = None
    cost_for_one_automation_level = None

    if automation is not None:
        cost_per_capacity_unit = (
            Decimal("6") + (Decimal("4") * automation)
        )

        cost_to_double_capacity = (
            capacity * cost_per_capacity_unit
        )

    cost_for_one_automation_level = capacity * Decimal("4")

    # ---------------------------------------------------------
    # Capacity interpretation
    # ---------------------------------------------------------

    if forecast_demand is not None:
        capacity_gap = capacity - forecast_demand

        if capacity_gap < 0:
            observations.append(
                f"Capacity shortage: {number(abs(capacity_gap))} units."
            )

        elif capacity_gap <= max(
            Decimal("100"),
            capacity * Decimal("0.10"),
        ):
            observations.append(
                f"Capacity headroom: {number(capacity_gap)} units."
            )

        else:
            observations.append(
                f"Forecast demand: {number(capacity_gap)} units."
            )

    # ---------------------------------------------------------
    # Utilization interpretation
    # ---------------------------------------------------------

    if utilization is not None:
        if utilization >= Decimal("120"):
            observations.append(
                "Utilization is critically high; capacity expansion "
                "should be prioritized."
            )

        elif utilization >= Decimal("90"):
            observations.append(
                "Utilization is high; monitor future capacity requirements."
            )

        elif utilization <= Decimal("50"):
            observations.append(
                "Current utilization is relatively low; immediate capacity "
                "expansion does not appear necessary."
            )

    # ---------------------------------------------------------
    # Automation interpretation
    # ---------------------------------------------------------

    if automation is not None:

        if automation >= Decimal("10"):
            observations.append(
                "Automation is already at the maximum level."
            )

        elif (
            forecast_demand is not None
            and forecast_demand >= Decimal("1000")
            and labor_cost is not None
            and labor_cost >= Decimal("7")
        ):
            observations.append(
                "Automation may be worth evaluating because of high "
                "production volume and labor cost."
            )

        elif (
            forecast_demand is not None
            and forecast_demand >= Decimal("500")
            and labor_cost is not None
            and labor_cost >= Decimal("8")
        ):
            observations.append(
                "Automation may be worth considering as a future "
                "labor-cost reduction."
            )

        elif (
            labor_cost is not None
            and labor_cost >= Decimal("9")
            and automation <= Decimal("3")
        ):
            observations.append(
                "Automation may improve future labor costs, but current "
                "production volume does not make it an immediate priority."
            )

    # ---------------------------------------------------------
    # Upgrade costs
    # ---------------------------------------------------------

    observations.append("---")

    if cost_per_capacity_unit is not None:
        observations.append(
            f"Adding 100 units of capacity would cost approximately "
            f"${number(cost_per_capacity_unit * Decimal('100'))}."
        )

    if automation is not None and automation < Decimal("10"):
        observations.append(
            f"A 1.0-level automation increase would cost approximately "
            f"${number(cost_for_one_automation_level)}."
        )

    # ---------------------------------------------------------
    # Capacity priority over automation
    # ---------------------------------------------------------

    if (
        forecast_demand is not None
        and forecast_demand > capacity
    ):
        observations.append(
            "Capacity expansion should be addressed before automation; "
            "automation reduces labor cost but does not increase capacity."
        )

    return observations


def is_useful_display_recommendation(recommendation):
    """
    Filter out vague or redundant recommendations from the
    product-level Decision Focus display.
    """

    action = str(
        getattr(recommendation, "action", "")
    ).strip().lower()

    rationale = str(
        getattr(recommendation, "rationale", "")
    ).strip().lower()

    combined = f"{action} {rationale}"

    vague_terms = [
        "positioning should be reviewed",
        "age and positioning should be reviewed",
        "whether positioning",
        "whether age",
    ]

    if any(term in combined for term in vague_terms):
        return False

    return True


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
        forecast_value = product_forecast.value
        forecast_status = product_forecast.status

        if forecast_value is not None and product.units_sold:
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


    production_observations = get_production_and_automation_analysis(
        product,
        product_forecast,
    )

    print("\nPRODUCTION & AUTOMATION ANALYSIS")
    print("-" * 40)

    for observation in production_observations:
        if observation == "---":
            print("-" * 40)
        else:
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

    # ---------------------------------------------------------
    # DECISION FOCUS
    # ---------------------------------------------------------

    decision_focus = []

    # Capacity-related priorities
    if product.capacity_next_round is not None:
        capacity = Decimal(str(product.capacity_next_round))

        if forecast_value is not None:
            forecast_demand = Decimal(str(forecast_value))
            capacity_gap = capacity - forecast_demand

            if capacity_gap < 0:
                decision_focus.append(
                    (
                        "Prioritize capacity expansion.",
                        f"Forecast demand exceeds listed capacity by "
                        f"{number(abs(capacity_gap))} units."
                    )
                )

            elif capacity_gap <= max(100, capacity * Decimal("0.10")):
                decision_focus.append(
                    (
                        "Monitor capacity closely.",
                        f"Forecast demand is only {number(capacity_gap)} "
                        f"units below listed capacity."
                    )
                )

    # Inventory-related priorities
    if product.inventory_units is not None and product.units_sold:
        inventory = Decimal(str(product.inventory_units))
        sales = Decimal(str(product.units_sold))

        if inventory < sales * Decimal("0.10"):
            decision_focus.append(
                (
                    "Protect inventory levels.",
                    f"Only {number(inventory)} units are available "
                    f"against {number(sales)} units sold."
                )
            )

    # Forecast-related priorities
    if forecast_change is not None:
        if forecast_change >= Decimal("10"):
            decision_focus.append(
                (
                    "Prepare for higher demand.",
                    f"Forecast sales are {forecast_change:+.1f}% "
                    f"above current sales."
                )
            )

        elif forecast_change <= Decimal("-10"):
            decision_focus.append(
                (
                    "Prepare for lower demand.",
                    f"Forecast sales are {forecast_change:+.1f}% "
                    f"below current sales."
                )
            )
            

    # Marketing-related priorities
    for _, title, explanation in marketing_observations:
        marketing_item = (title, explanation)

        if marketing_item not in decision_focus:
            decision_focus.append(marketing_item)

    
    print("\nDECISION FOCUS")
    print("-" * 40)

    if decision_focus:
        for action, rationale in decision_focus:
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
    # FINANCIAL POSITION & HEALTH
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("              FINANCIAL POSITION & HEALTH")
    print("=" * 60)

    companies = getattr(financial_analysis, "companies", {})
    baldwin_financials = companies.get(Company.BALDWIN)

    if baldwin_financials:
        print("\nBALANCE SHEET")
        print("-" * 40)

        print(
            f"Cash:                    "
            f"{money(getattr(baldwin_financials, 'cash', None))}"
        )
        print(
            f"Accounts receivable:     "
            f"{money(getattr(baldwin_financials, 'accounts_receivable', None))}"
        )
        print(
            f"Inventory:               "
            f"{money(getattr(baldwin_financials, 'inventory', None))}"
        )
        print(
            f"Accounts payable:        "
            f"{money(getattr(baldwin_financials, 'accounts_payable', None))}"
        )
        print(
            f"Current debt:            "
            f"{money(getattr(baldwin_financials, 'current_debt', None))}"
        )
        print(
            f"Long-term debt:          "
            f"{money(getattr(baldwin_financials, 'long_term_debt', None))}"
        )
        print(
            f"Total debt:              "
            f"{money(getattr(baldwin_financials, 'total_debt', None))}"
        )
        print(
            f"Total assets:            "
            f"{money(getattr(baldwin_financials, 'total_assets', None))}"
        )
        print(
            f"Total equity:            "
            f"{money(getattr(baldwin_financials, 'total_equity', None))}"
        )

        print("\nFINANCIAL HEALTH METRICS")
        print("-" * 40)

        print(
            f"Working capital:         "
            f"{money(getattr(baldwin_financials, 'working_capital', None))}"
        )
        print(
            f"Current ratio:           "
            f"{ratio(getattr(baldwin_financials, 'current_ratio', None))}"
        )
        print(
            f"Debt / equity:           "
            f"{ratio(getattr(baldwin_financials, 'debt_to_equity', None))}"
        )
        print(
            f"Debt / assets:           "
            f"{percent(getattr(baldwin_financials, 'debt_to_assets', None) * Decimal('100') if getattr(baldwin_financials, 'debt_to_assets', None) is not None else None)}"
        )
        print(
            f"Inventory / current assets: "
            f"{percent(getattr(baldwin_financials, 'inventory_to_current_assets', None) * Decimal('100') if getattr(baldwin_financials, 'inventory_to_current_assets', None) is not None else None)}"
        )
        print(
            f"Cash / current assets:   "
            f"{percent(getattr(baldwin_financials, 'cash_to_current_assets', None) * Decimal('100') if getattr(baldwin_financials, 'cash_to_current_assets', None) is not None else None)}"
        )

        print("\nPROFITABILITY")
        print("-" * 40)

        print(
            f"Sales:                   "
            f"{money(getattr(baldwin_financials, 'revenue', None))}"
        )
        print(
            f"Contribution margin:     "
            f"{money(getattr(baldwin_financials, 'contribution_margin', None))}"
        )
        print(
            f"EBIT:                    "
            f"{money(getattr(baldwin_financials, 'ebit', None))}"
        )
        print(
            f"Net profit:              "
            f"{money(getattr(baldwin_financials, 'net_profit', None))}"
        )
        print(
            f"Net profit margin:       "
            f"{percent(getattr(baldwin_financials, 'net_profit_margin', None))}"
        )

        financial_observations = get_financial_observations(
            baldwin_financials,
        )

        if financial_observations:
            print("\nFINANCIAL OBSERVATIONS")
            print("-" * 40)

            for level, title, explanation in financial_observations:
                symbol = {
                    "POSITIVE": "✓",
                    "WARNING": "⚠",
                    "WATCH": "→",
                    "IMPLICATION": "→",
                }.get(level, "•")

                print(f"{symbol} {title}")
                print(f"  {explanation}")

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