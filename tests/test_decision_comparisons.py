from decimal import Decimal

from capsim_analyzer.decision.comparisons import (
    compare_actual_to_potential,
    compare_forecast_to_capacity,
    compare_forecast_to_current,
    compare_to_expected,
    compare_value_to_range,
)
from capsim_analyzer.decision.types import (
    CapacityPosition,
    ComparisonDirection,
    DecisionStatus,
    RangePosition,
)


def test_value_range_comparison():
    assert compare_value_to_range(Decimal("9"), Decimal("10"), Decimal("20")).position is RangePosition.BELOW
    assert compare_value_to_range(Decimal("15"), Decimal("10"), Decimal("20")).position is RangePosition.WITHIN
    assert compare_value_to_range(Decimal("21"), Decimal("10"), Decimal("20")).position is RangePosition.ABOVE
    assert compare_value_to_range(None, Decimal("10"), Decimal("20")).status is DecisionStatus.MISSING_INPUT
    assert compare_value_to_range(Decimal("15"), Decimal("20"), Decimal("10")).status is DecisionStatus.CONFLICTING_DATA


def test_expected_value_comparison_preserves_decimal():
    result = compare_to_expected(Decimal("10.125"), Decimal("10.000"))
    assert result.difference == Decimal("0.125")
    assert result.direction is ComparisonDirection.INCREASE
    assert isinstance(result.difference, Decimal)
    assert compare_to_expected(Decimal("10"), Decimal("10")).direction is ComparisonDirection.NO_CHANGE
    assert compare_to_expected(Decimal("9"), Decimal("10")).direction is ComparisonDirection.DECREASE
    assert compare_to_expected(None, Decimal("10")).status is DecisionStatus.MISSING_INPUT


def test_actual_potential_comparison():
    result = compare_actual_to_potential(Decimal("12.5"), Decimal("15.0"))
    assert result.gap == Decimal("2.5")
    assert result.direction is ComparisonDirection.INCREASE
    assert compare_actual_to_potential(Decimal("15"), Decimal("15")).direction is ComparisonDirection.NO_CHANGE
    assert compare_actual_to_potential(Decimal("16"), Decimal("15")).gap == Decimal("-1")
    assert compare_actual_to_potential(None, Decimal("15")).status is DecisionStatus.MISSING_INPUT
    assert compare_actual_to_potential(Decimal("15"), None).status is DecisionStatus.MISSING_INPUT


def test_forecast_current_comparison():
    increase = compare_forecast_to_current(Decimal("120"), Decimal("100"))
    decrease = compare_forecast_to_current(Decimal("80"), Decimal("100"))
    equal = compare_forecast_to_current(Decimal("100"), Decimal("100"))

    assert increase.difference == Decimal("20")
    assert increase.direction is ComparisonDirection.INCREASE
    assert increase.percent_change == Decimal("20")
    assert decrease.direction is ComparisonDirection.DECREASE
    assert equal.direction is ComparisonDirection.NO_CHANGE
    assert compare_forecast_to_current(None, Decimal("100")).status is DecisionStatus.MISSING_INPUT
    assert compare_forecast_to_current(Decimal("100"), None).status is DecisionStatus.MISSING_INPUT


def test_forecast_current_zero_denominator_is_explicit():
    result = compare_forecast_to_current(Decimal("10"), Decimal("0"))

    assert result.status is DecisionStatus.ZERO_DENOMINATOR
    assert result.difference == Decimal("10")
    assert result.percent_change is None


def test_forecast_capacity_comparison():
    exceeds = compare_forecast_to_capacity(Decimal("120.5"), Decimal("100"))
    exact = compare_forecast_to_capacity(Decimal("100"), Decimal("100"))
    headroom = compare_forecast_to_capacity(Decimal("80"), Decimal("100"))

    assert exceeds.gap == Decimal("20.5")
    assert exceeds.exceeds_capacity is True
    assert exceeds.position is CapacityPosition.EXCEEDS
    assert exact.exceeds_capacity is False
    assert exact.position is CapacityPosition.EXACT
    assert headroom.gap == Decimal("-20")
    assert headroom.position is CapacityPosition.HEADROOM
    assert compare_forecast_to_capacity(None, Decimal("100")).status is DecisionStatus.MISSING_INPUT
    assert compare_forecast_to_capacity(Decimal("100"), None).status is DecisionStatus.MISSING_INPUT


def test_comparison_helpers_are_deterministic():
    inputs = (Decimal("125.00"), Decimal("100.00"))

    assert compare_forecast_to_current(*inputs) == compare_forecast_to_current(*inputs)
    assert compare_forecast_to_capacity(*inputs) == compare_forecast_to_capacity(*inputs)
