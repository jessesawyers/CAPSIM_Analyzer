from __future__ import annotations

from typing import Any

from .types import (
    ActualPotentialComparison,
    CapacityPosition,
    ComparisonDirection,
    DecisionStatus,
    ExpectedValueComparison,
    ForecastCapacityComparison,
    ForecastCurrentComparison,
    RangeComparison,
    RangePosition,
)


def compare_value_to_range(
    value: Any,
    minimum: Any,
    maximum: Any,
) -> RangeComparison:
    if value is None or minimum is None or maximum is None:
        return RangeComparison(
            DecisionStatus.MISSING_INPUT,
            value,
            minimum,
            maximum,
            None,
        )
    if minimum > maximum:
        return RangeComparison(
            DecisionStatus.CONFLICTING_DATA,
            value,
            minimum,
            maximum,
            None,
        )
    position = (
        RangePosition.BELOW
        if value < minimum
        else RangePosition.ABOVE
        if value > maximum
        else RangePosition.WITHIN
    )
    return RangeComparison(
        DecisionStatus.AVAILABLE,
        value,
        minimum,
        maximum,
        position,
    )


def compare_to_expected(actual: Any, expected: Any) -> ExpectedValueComparison:
    if actual is None or expected is None:
        return ExpectedValueComparison(
            DecisionStatus.MISSING_INPUT,
            actual,
            expected,
            None,
            None,
        )
    difference = actual - expected
    return ExpectedValueComparison(
        DecisionStatus.AVAILABLE,
        actual,
        expected,
        difference,
        _direction(difference),
    )


def compare_actual_to_potential(
    actual: Any,
    potential: Any,
) -> ActualPotentialComparison:
    if actual is None or potential is None:
        return ActualPotentialComparison(
            DecisionStatus.MISSING_INPUT,
            actual,
            potential,
            None,
            None,
        )
    gap = potential - actual
    return ActualPotentialComparison(
        DecisionStatus.AVAILABLE,
        actual,
        potential,
        gap,
        _direction(gap),
    )


def compare_forecast_to_current(
    forecast: Any,
    current: Any,
) -> ForecastCurrentComparison:
    if forecast is None or current is None:
        return ForecastCurrentComparison(
            DecisionStatus.MISSING_INPUT,
            forecast,
            current,
            None,
            None,
            None,
        )
    difference = forecast - current
    if current == 0:
        return ForecastCurrentComparison(
            DecisionStatus.ZERO_DENOMINATOR,
            forecast,
            current,
            difference,
            _direction(difference),
            None,
        )
    return ForecastCurrentComparison(
        DecisionStatus.AVAILABLE,
        forecast,
        current,
        difference,
        _direction(difference),
        difference / current * 100,
    )


def compare_forecast_to_capacity(
    forecast: Any,
    capacity: Any,
) -> ForecastCapacityComparison:
    if forecast is None or capacity is None:
        return ForecastCapacityComparison(
            DecisionStatus.MISSING_INPUT,
            forecast,
            capacity,
            None,
            None,
            None,
        )
    gap = forecast - capacity
    if gap > 0:
        position = CapacityPosition.EXCEEDS
    elif gap == 0:
        position = CapacityPosition.EXACT
    else:
        position = CapacityPosition.HEADROOM
    return ForecastCapacityComparison(
        DecisionStatus.AVAILABLE,
        forecast,
        capacity,
        gap,
        gap > 0,
        position,
    )


def _direction(difference: Any) -> ComparisonDirection:
    if difference > 0:
        return ComparisonDirection.INCREASE
    if difference < 0:
        return ComparisonDirection.DECREASE
    return ComparisonDirection.NO_CHANGE
