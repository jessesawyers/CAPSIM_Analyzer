from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class DecisionStatus(str, Enum):
    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"
    MISSING_INPUT = "missing_input"
    CONFLICTING_DATA = "conflicting_data"
    UNSUPPORTED = "unsupported"
    ASSUMPTION_REQUIRED = "assumption_required"
    INFORMATIONAL = "informational"
    ZERO_DENOMINATOR = "zero_denominator"


class RecommendationCategory(str, Enum):
    PRODUCT = "product"
    PRODUCTION = "production"
    INVENTORY = "inventory"
    MARKETING = "marketing"
    INVESTMENT = "investment"
    FINANCE = "finance"
    DATA_QUALITY = "data_quality"


class RecommendationPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ComparisonDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    NO_CHANGE = "no_change"


class RangePosition(str, Enum):
    BELOW = "below"
    WITHIN = "within"
    ABOVE = "above"


class CapacityPosition(str, Enum):
    EXCEEDS = "exceeds"
    EXACT = "exact"
    HEADROOM = "headroom"


@dataclass(frozen=True)
class RangeComparison:
    status: DecisionStatus
    value: Any
    minimum: Any
    maximum: Any
    position: RangePosition | None


@dataclass(frozen=True)
class ExpectedValueComparison:
    status: DecisionStatus
    actual: Any
    expected: Any
    difference: Any
    direction: ComparisonDirection | None


@dataclass(frozen=True)
class ActualPotentialComparison:
    status: DecisionStatus
    actual: Any
    potential: Any
    gap: Any
    direction: ComparisonDirection | None


@dataclass(frozen=True)
class ForecastCurrentComparison:
    status: DecisionStatus
    forecast: Any
    current: Any
    difference: Any
    direction: ComparisonDirection | None
    percent_change: Any


@dataclass(frozen=True)
class ForecastCapacityComparison:
    status: DecisionStatus
    forecast: Any
    capacity: Any
    gap: Any
    exceeds_capacity: bool | None
    position: CapacityPosition | None


@dataclass(frozen=True)
class Evidence:
    kind: str
    metric: str
    entity_type: str
    entity_id: str
    value: Any
    unit: str | None
    source_rounds: tuple[int, ...]
    status: DecisionStatus
    explanation: str


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    category: RecommendationCategory
    priority: RecommendationPriority
    entity_type: str
    entity_id: str
    action: str
    rationale: str
    evidence: tuple[Evidence, ...]
    assumptions: tuple[str, ...]
    status: DecisionStatus


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: DecisionStatus
    entity_type: str
    entity_id: str
    observations: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    assumptions: tuple[str, ...]
    recommendation: Recommendation | None


@dataclass(frozen=True)
class DecisionReport:
    status: DecisionStatus
    observations: tuple[RuleResult, ...]
    recommendations: tuple[Recommendation, ...]
    blocked_rules: tuple[RuleResult, ...]
    data_quality_issues: tuple[Evidence, ...]
